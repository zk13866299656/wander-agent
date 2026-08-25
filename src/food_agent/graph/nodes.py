from __future__ import annotations

import asyncio
import logging

from food_agent.config import settings
from food_agent.graph.state import GraphState
from food_agent.llm.client import complete_with_retry
from food_agent.memory.extract import extract_preferences
from food_agent.models.schemas import ParsedRequest, Poi, RecommendationCard
from food_agent.ranking.scorer import rank
from food_agent.storage.db import get_session, upsert_preference
from food_agent.tools.amap import geocode
from food_agent.tools.registry import get_enabled_tools

logger = logging.getLogger(__name__)


def parse_node(state: GraphState) -> dict:
    msgs = [
        {"role": "system",
         "content": "你是需求解析器。若用户是在对上一轮推荐结果追问/调整（如「太贵了」「换一家」「便宜点」），置 is_followup=true。"},
        {"role": "user", "content": state["user_input"]},
    ]
    parsed = complete_with_retry(msgs, response_format=ParsedRequest)
    # 经纬度来源优先级：LLM 已给 > 浏览器定位（state）> 高德地理编码
    lnglat = parsed.lnglat
    if lnglat is None:
        lnglat = state.get("lnglat")
    if lnglat is None and parsed.location:
        lnglat = geocode(parsed.location, settings.amap_api_key)
    if lnglat is not None and parsed.lnglat != lnglat:
        parsed = parsed.model_copy(update={"lnglat": lnglat})
    return {"parsed": parsed}


def retrieve_node(state: GraphState) -> dict:
    parsed: ParsedRequest = state["parsed"]
    tools = get_enabled_tools()
    poi_tool = tools.get("poi")
    coros = [_search_rag(parsed)]          # 向量召回：独立源，永远执行
    if poi_tool is not None and parsed.lnglat is not None:
        coros.append(_search_poi(poi_tool, parsed))
    chunks = asyncio.run(_gather(coros))
    pois: list[Poi] = [p for chunk in chunks for p in chunk]
    return {"pois": pois}


async def _gather(coros: list) -> list:
    return await asyncio.gather(*coros)


async def _search_poi(poi_tool, parsed):
    try:
        return poi_tool.search(parsed.categories[0] if parsed.categories else "",
                               parsed.lnglat, 3000, parsed.categories)
    except Exception:
        logger.warning("POI 检索失败，降级为空", exc_info=True)
        return []


async def _search_rag(parsed):
    from food_agent.rag.store import VectorStore
    try:
        return VectorStore().search(" ".join(parsed.categories), k=5)
    except Exception:  # noqa: BLE001
        return []


def extract_node(state: GraphState) -> dict:
    # 结构化抽取：把散乱 POI 统一成候选。MVP 直接透传（POI 已结构化），
    # 多源 WebSearch 结果合并的抽取逻辑在 Task 12 补。
    return {"pois": state["pois"]}


def rank_node(state: GraphState) -> dict:
    candidates = rank(state["pois"], state["parsed"], top_k=10)
    return {"candidates": candidates}


def card_node(state: GraphState) -> dict:
    cards = [
        RecommendationCard(id=c.id, source=c.source, name=c.name, rating=c.rating,
                           avg_price=c.avg_price, distance_m=c.distance_m,
                           tags=c.tags, score=c.score, reasons=c.reasons)
        for c in state["candidates"]
    ]
    return {"cards": cards}


def memory_node(state: GraphState) -> dict:
    # 偏好记忆写入：extract 抽取 + upsert 持久化；失败仅记日志、降级不影响主链路。
    try:
        prefs = extract_preferences(state["user_input"])
        if prefs:
            session = get_session()
            try:
                for p in prefs:
                    upsert_preference(session, p)
            finally:
                session.close()
    except Exception:
        logger.warning("memory_node 偏好记忆写入失败", exc_info=True)
    return {}

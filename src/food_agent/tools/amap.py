from __future__ import annotations

import httpx

from food_agent.models.schemas import Poi
from food_agent.tools.base import PoiSearchTool

AMAP_AROUND_URL = "https://restapi.amap.com/v5/place/around"
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"

def map_category_to_types(categories: list[str]) -> list[str]:
    """品类关键词 → 高德 types 分类码。MVP 由 LLM 在解析阶段直接产出 amap_types，
    这里仅作兜底（返回空表示不传 types、改用 keywords）。"""
    return []

def _to_float(value) -> float | None:
    """非数字字符串（如 "N/A"）或空值兜底返回 None，避免 ValueError 中断整个 search。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _clamp_rating(value: float | None) -> float | None:
    """rating 钳制到 [0, 5]：None 透传，越界值收敛到边界，避免单个 POI 炸掉整次 search。"""
    if value is None:
        return None
    return min(5.0, max(0.0, value))

def geocode(address: str, api_key: str) -> tuple[float, float] | None:
    """地名 → 经纬度（高德地理编码）。无 Key / 地址为空 / 请求失败 / 无结果均返回 None，不抛异常。"""
    if not api_key or not address:
        return None
    try:
        resp = httpx.get(AMAP_GEOCODE_URL, params={"key": api_key, "address": address}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError:
        return None
    if data.get("status") != "1":
        return None
    geocodes = data.get("geocodes") or []
    if not geocodes:
        return None
    loc = geocodes[0].get("location") or ""
    parts = loc.split(",")
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def build_amap_params(lnglat: tuple[float, float], types: list[str], keywords: str,
                      radius: int) -> dict:
    params = {
        "location": f"{lnglat[0]},{lnglat[1]}",
        "keywords": keywords,
        "radius": radius,
        "sortrule": "weight",
    }
    if types:
        params["types"] = "|".join(types)
    return params

class AmapPoiSearch(PoiSearchTool):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, location: tuple[float, float], radius: int,
               categories: list[str]) -> list[Poi]:
        types = map_category_to_types(categories)
        params = build_amap_params(location, types, keywords=query, radius=radius)
        params["key"] = self.api_key
        resp = httpx.get(AMAP_AROUND_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return []
        pois: list[Poi] = []
        for item in data.get("pois", []):
            loc = item.get("location") or ""
            parts = loc.split(",")
            if len(parts) != 2:
                continue
            try:
                lng, lat = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            biz = item.get("biz_ext") or {}
            pois.append(Poi(
                id=item["id"], name=item["name"], address=item.get("address"),
                category=item.get("type"),
                rating=_clamp_rating(_to_float(biz.get("rating"))),
                avg_price=_to_float(biz.get("cost")),
                source="amap", lnglat=(lng, lat),
            ))
        return pois

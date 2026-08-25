from __future__ import annotations

import chromadb
import httpx

from food_agent.config import settings
from food_agent.models.schemas import Poi


class SiliconFlowEmbedding:
    """SiliconFlow 远程 embedding（BAAI/bge-m3），实现 Chroma EmbeddingFunction 接口。

    刻意不继承 EmbeddingFunction Protocol：其 __init_subclass__ 会把 __call__ 的返回
    归一化成 numpy 数组，这里保持原样返回 list[list[float]]。配置来自全局 settings，
    声明为 legacy 即可（无需 Chroma 持久化 embedding 配置）。
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def name() -> str:
        return "siliconflow"

    @staticmethod
    def is_legacy() -> bool:
        return True

    def __call__(self, input: list[str]) -> list[list[float]]:
        resp = httpx.post(
            "https://api.siliconflow.cn/v1/embeddings",
            json={"model": settings.siliconflow_embedding_model, "input": input},
            headers={"Authorization": f"Bearer {settings.siliconflow_api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        return [d["embedding"] for d in resp.json()["data"]]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)


class VectorStore:
    """Chroma 本地持久化。embedding 用 SiliconFlow 远程；未配置时用 Chroma 默认。
    冷启动（无历史数据）search 返回空列表，不影响主链路。"""

    def __init__(self):
        self._client = chromadb.PersistentClient(path=settings.chroma_dir)
        kwargs: dict = {}
        if settings.siliconflow_api_key:
            kwargs["embedding_function"] = SiliconFlowEmbedding()
        self._collection = self._client.get_or_create_collection(name="favorites", **kwargs)

    def add_pois(self, pois: list[Poi]) -> None:
        if not pois:
            return
        self._collection.upsert(
            ids=[p.id for p in pois],
            documents=[f"{p.name} {p.category or ''} {' '.join(p.tags)}" for p in pois],
            metadatas=[_poi_metadata(p) for p in pois],
        )

    def search(self, query: str, k: int = 5) -> list[Poi]:
        if self._collection is None or self._collection.count() == 0:
            return []
        res = self._collection.query(query_texts=[query], n_results=k)
        pois: list[Poi] = []
        for poi_id, meta in zip(res["ids"][0], res["metadatas"][0]):
            if meta is None:
                continue
            pois.append(_poi_from_metadata(poi_id, meta))
        return pois


def _poi_metadata(p: Poi) -> dict:
    """Poi → Chroma 元数据。Chroma 只接受标量且不接受 None，tags 以逗号拼接存字符串；
    数值字段为 None 时直接省略（回查时 `.get()` 缺省即还原为 None）。"""
    meta = {
        "name": p.name,
        "address": p.address or "",
        "category": p.category or "",
        "source": p.source,
        "tags": ",".join(p.tags),
    }
    for key in ("rating", "review_count", "avg_price", "distance_m"):
        value = getattr(p, key)
        if value is not None:
            meta[key] = value
    return meta


def _poi_from_metadata(poi_id: str, meta: dict) -> Poi:
    """Chroma 元数据 → Poi，把逗号拼接的 tags 还原成 list。"""
    return Poi(
        id=poi_id,
        name=meta["name"],
        address=meta.get("address") or None,
        category=meta.get("category") or None,
        rating=meta.get("rating"),
        review_count=meta.get("review_count"),
        avg_price=meta.get("avg_price"),
        distance_m=meta.get("distance_m"),
        tags=[t for t in (meta.get("tags") or "").split(",") if t],
        source=meta.get("source") or "amap",
    )

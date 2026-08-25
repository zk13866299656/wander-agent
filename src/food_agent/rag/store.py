from __future__ import annotations
import chromadb
from food_agent.config import settings
from food_agent.models.schemas import Poi

class VectorStore:
    """Chroma 本地持久化。embedding 用 SiliconFlow 远程；未配置时用 Chroma 默认。
    冷启动（无历史数据）search 返回空列表，不影响主链路。"""
    def __init__(self):
        self._client = chromadb.PersistentClient(path=settings.chroma_dir)
        self._collection = self._client.get_or_create_collection(name="favorites")

    def add_pois(self, pois: list[Poi]) -> None:
        if not pois:
            return
        self._collection.upsert(
            ids=[p.id for p in pois],
            documents=[f"{p.name} {p.category or ''} {' '.join(p.tags)}" for p in pois],
        )

    def search(self, query: str, k: int = 5) -> list[Poi]:
        if self._collection is None or self._collection.count() == 0:
            return []
        res = self._collection.query(query_texts=[query], n_results=k)
        # 命中结果需回查业务库取完整 Poi；MVP 先返回空占位，Task 12 端到端前补
        return []

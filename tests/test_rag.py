from unittest.mock import patch

from food_agent.config import settings
from food_agent.rag.store import SiliconFlowEmbedding, VectorStore


def test_empty_store_returns_empty(monkeypatch):
    store = VectorStore.__new__(VectorStore)  # 跳过 __init__，不连真实 Chroma
    monkeypatch.setattr(store, "_collection", None, raising=False)
    assert store.search("日料", k=5) == []


def test_search_reconstructs_pois_from_metadata(monkeypatch):
    store = VectorStore.__new__(VectorStore)
    meta = {
        "id": "p1",
        "name": "某日料",
        "category": "日料",
        "rating": 4.5,
        "review_count": 100,
        "avg_price": 120.0,
        "distance_m": 1000,
        "source": "amap",
        "tags": "标签1,标签2",
    }

    class FakeCollection:
        def count(self):
            return 1

        def query(self, query_texts, n_results):
            assert query_texts == ["日料"]
            assert n_results == 5
            return {"ids": [["p1"]], "metadatas": [[meta]]}

    monkeypatch.setattr(store, "_collection", FakeCollection(), raising=False)
    pois = store.search("日料", k=5)
    assert len(pois) == 1
    p = pois[0]
    assert p.id == "p1"
    assert p.name == "某日料"
    assert p.category == "日料"
    assert p.rating == 4.5
    assert p.review_count == 100
    assert p.avg_price == 120.0
    assert p.distance_m == 1000
    assert p.source == "amap"
    assert p.tags == ["标签1", "标签2"]


def test_siliconflow_embedding_request(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": [0.1, 0.2, 0.3]},
                             {"embedding": [0.4, 0.5, 0.6]}]}

    monkeypatch.setattr(settings, "siliconflow_api_key", "test-key")
    monkeypatch.setattr(settings, "siliconflow_embedding_model", "BAAI/bge-m3")

    with patch("food_agent.rag.store.httpx.post", return_value=FakeResponse()) as post:
        embeddings = SiliconFlowEmbedding()(["你好", "世界"])

    assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    post.assert_called_once()
    assert post.call_args.args[0] == "https://api.siliconflow.cn/v1/embeddings"
    kwargs = post.call_args.kwargs
    assert kwargs["json"] == {"model": "BAAI/bge-m3", "input": ["你好", "世界"]}
    assert kwargs["headers"] == {"Authorization": "Bearer test-key"}

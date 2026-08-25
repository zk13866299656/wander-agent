from food_agent.rag.store import VectorStore

def test_empty_store_returns_empty(monkeypatch):
    store = VectorStore.__new__(VectorStore)  # 跳过 __init__，不连真实 Chroma
    monkeypatch.setattr(store, "_collection", None, raising=False)
    assert store.search("日料", k=5) == []

from unittest.mock import patch

from langgraph.checkpoint.sqlite import SqliteSaver

from food_agent.graph.build import build_graph
from food_agent.models.schemas import ParsedRequest, Poi


class FakeVectorStore:
    def search(self, query, k=5):
        return []


def test_full_flow_with_mocked_tools(tmp_path):
    req = ParsedRequest(location="杭州西湖", categories=["日料"], lnglat=(120.15, 30.28))
    poi = Poi(id="1", name="某日料", rating=4.5, review_count=100,
              avg_price=120, distance_m=1000, source="amap")

    class FakePoiTool:
        def search(self, query, location, radius, categories):
            return [poi]

    with patch("food_agent.graph.nodes.complete_with_retry", return_value=req), \
         patch("food_agent.graph.nodes.extract_preferences", return_value=[]), \
         patch("food_agent.graph.nodes.get_enabled_tools", return_value={"poi": FakePoiTool()}), \
         patch("food_agent.rag.store.VectorStore", return_value=FakeVectorStore()), \
         SqliteSaver.from_conn_string(str(tmp_path / "ckpt.sqlite")) as ckpt:
        graph = build_graph(ckpt)
        result = graph.invoke(
            {"user_input": "杭州西湖附近日料"},
            {"configurable": {"thread_id": "t1"}},
        )
    assert len(result["cards"]) == 1
    assert result["cards"][0].name == "某日料"

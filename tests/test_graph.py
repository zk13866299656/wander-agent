from unittest.mock import patch

from langgraph.checkpoint.sqlite import SqliteSaver

from food_agent.graph.build import build_graph, route_after_parse
from food_agent.graph.nodes import parse_node
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


def test_retrieve_degrades_when_poi_tool_raises(tmp_path):
    """POI 检索抛异常时降级：不炸主链路，仅 RAG 结果（此处为空）→ cards 空。"""
    req = ParsedRequest(location="杭州西湖", categories=["日料"], lnglat=(120.15, 30.28))

    class RaisingPoiTool:
        def search(self, query, location, radius, categories):
            raise RuntimeError("amap 限流")

    with patch("food_agent.graph.nodes.complete_with_retry", return_value=req), \
         patch("food_agent.graph.nodes.extract_preferences", return_value=[]), \
         patch("food_agent.graph.nodes.get_enabled_tools",
               return_value={"poi": RaisingPoiTool()}), \
         patch("food_agent.rag.store.VectorStore", return_value=FakeVectorStore()), \
         SqliteSaver.from_conn_string(str(tmp_path / "ckpt.sqlite")) as ckpt:
        graph = build_graph(ckpt)
        result = graph.invoke(
            {"user_input": "杭州西湖附近日料"},
            {"configurable": {"thread_id": "t1"}},
        )
    assert result["cards"] == []


def test_rag_runs_without_poi_tool(tmp_path):
    """无 Amap（poi tool 缺失）时向量召回仍应执行，返回 RAG 结果。"""
    req = ParsedRequest(location="杭州西湖", categories=["日料"], lnglat=(120.15, 30.28))
    known_poi = Poi(id="r1", name="RAG召回店", source="rag")

    class FakeVectorStoreWithPoi:
        def search(self, query, k=5):
            return [known_poi]

    with patch("food_agent.graph.nodes.complete_with_retry", return_value=req), \
         patch("food_agent.graph.nodes.extract_preferences", return_value=[]), \
         patch("food_agent.graph.nodes.get_enabled_tools", return_value={}), \
         patch("food_agent.rag.store.VectorStore", return_value=FakeVectorStoreWithPoi()), \
         SqliteSaver.from_conn_string(str(tmp_path / "ckpt.sqlite")) as ckpt:
        graph = build_graph(ckpt)
        result = graph.invoke(
            {"user_input": "杭州西湖附近日料"},
            {"configurable": {"thread_id": "t1"}},
        )
    assert any(p.id == "r1" and p.name == "RAG召回店" for p in result["pois"])


def test_followup_keyword_routes_to_rank():
    """追问关键词兜底：LLM 未判 is_followup 时，有候选可复用则关键词路由到 rank。"""
    parsed = ParsedRequest(location="杭州西湖", is_followup=False)
    pois = [Poi(id="1", name="某日料", source="amap")]
    # 有候选可复用 → 关键词兜底路由到 rank
    assert route_after_parse({"parsed": parsed, "user_input": "换一家便宜点的", "pois": pois}) == "rank"
    # 有候选但无关键词 → 正常检索
    assert route_after_parse({"parsed": parsed, "user_input": "杭州西湖日料", "pois": pois}) == "retrieve"


def test_followup_keyword_not_misrouted_on_first_turn():
    """首轮消息即使含「便宜/换」等词、无候选可复用，也不应误判为追问。"""
    parsed = ParsedRequest(location="杭州西湖", is_followup=False)
    assert route_after_parse({"parsed": parsed, "user_input": "杭州便宜的日料"}) == "retrieve"
    assert route_after_parse({"parsed": parsed, "user_input": "换一家近点的"}) == "retrieve"


def test_parse_node_geocodes_location_when_lnglat_missing():
    """LLM 未给出 lnglat 时，用地名走地理编码补齐坐标。"""
    req = ParsedRequest(location="杭州西湖", categories=["日料"], lnglat=None)
    with patch("food_agent.graph.nodes.complete_with_retry", return_value=req), \
         patch("food_agent.graph.nodes.geocode", return_value=(120.15, 30.28)):
        out = parse_node({"user_input": "杭州西湖附近日料"})
    assert out["parsed"].lnglat == (120.15, 30.28)


def test_parse_node_keeps_lnglat_when_present():
    """LLM 已给 lnglat 时不再触发地理编码。"""
    req = ParsedRequest(location="杭州西湖", categories=["日料"], lnglat=(120.15, 30.28))
    with patch("food_agent.graph.nodes.complete_with_retry", return_value=req), \
         patch("food_agent.graph.nodes.geocode") as mk_geo:
        out = parse_node({"user_input": "杭州西湖附近日料"})
    assert out["parsed"].lnglat == (120.15, 30.28)
    mk_geo.assert_not_called()

from food_agent.tools.amap import AmapPoiSearch, build_amap_params, map_category_to_types

def test_map_category_to_types_falls_back_to_keywords():
    # 不认识「日料」分类码时返回空，靠 keywords 兜底
    assert map_category_to_types(["日料"]) == []

def test_build_amap_params_uses_keywords_when_no_types():
    params = build_amap_params(lnglat=(120.15, 30.28), types=[], keywords="日料", radius=3000)
    assert params["location"] == "120.15,30.28"
    assert params["keywords"] == "日料"
    assert params["radius"] == 3000
    assert "types" not in params or params["types"] == ""

def test_amap_search_parses_response(monkeypatch):
    class FakeResp:
        def json(self):
            return {"status": "1", "pois": [
                {"id": "1", "name": "某日料", "biz_ext": {"rating": "4.5", "cost": "120"},
                 "location": "120.15,30.28", "type": "日料店"}
            ]}
        def raise_for_status(self):
            return None
    def fake_get(*a, **k):
        return FakeResp()
    monkeypatch.setattr("food_agent.tools.amap.httpx.get", fake_get)
    tool = AmapPoiSearch(api_key="test")
    pois = tool.search(query="日料", location=(120.15, 30.28), radius=3000, categories=["日料"])
    assert pois[0].name == "某日料" and pois[0].rating == 4.5 and pois[0].source == "amap"

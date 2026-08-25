from food_agent.config import settings
from food_agent.tools.registry import get_enabled_tools

def test_web_search_absent_without_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "")
    monkeypatch.setattr(settings, "amap_api_key", "test")
    assert "web" not in get_enabled_tools()

def test_web_search_present_with_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test")
    monkeypatch.setattr(settings, "amap_api_key", "")
    assert "web" in get_enabled_tools()

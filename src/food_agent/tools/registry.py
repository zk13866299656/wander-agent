from food_agent.config import settings
from food_agent.tools.amap import AmapPoiSearch
from food_agent.tools.web import TavilySearch

def get_enabled_tools() -> dict:
    tools: dict = {}
    if settings.amap_api_key:
        tools["poi"] = AmapPoiSearch(settings.amap_api_key)
    if settings.tavily_api_key:
        tools["web"] = TavilySearch(settings.tavily_api_key)
    return tools

from __future__ import annotations
import httpx
from food_agent.tools.base import SearchResult, WebSearchTool

class TavilySearch(WebSearchTool):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str) -> list[SearchResult]:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": self.api_key, "query": query, "max_results": 5},
            timeout=10,
        )
        resp.raise_for_status()
        return [
            SearchResult(title=r["title"], url=r["url"], snippet=r.get("content", ""))
            for r in resp.json().get("results", [])
        ]

class DuckDuckGoSearch(WebSearchTool):
    def search(self, query: str) -> list[SearchResult]:
        return []  # 免费但国内可能不通，默认返回空并标注降级

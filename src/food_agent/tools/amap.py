from __future__ import annotations
import httpx
from food_agent.models.schemas import Poi
from food_agent.tools.base import PoiSearchTool

AMAP_AROUND_URL = "https://restapi.amap.com/v5/place/around"

def map_category_to_types(categories: list[str]) -> list[str]:
    """品类关键词 → 高德 types 分类码。MVP 由 LLM 在解析阶段直接产出 amap_types，
    这里仅作兜底（返回空表示不传 types、改用 keywords）。"""
    return []

def build_amap_params(lnglat: tuple[float, float], types: list[str], keywords: str,
                      radius: int) -> dict:
    params = {
        "location": f"{lnglat[0]},{lnglat[1]}",
        "keywords": keywords,
        "radius": radius,
        "sortrule": "weight",
    }
    if types:
        params["types"] = "|".join(types)
    return params

class AmapPoiSearch(PoiSearchTool):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, location: tuple[float, float], radius: int,
               categories: list[str]) -> list[Poi]:
        types = map_category_to_types(categories)
        params = build_amap_params(location, types, keywords=query, radius=radius)
        params["key"] = self.api_key
        resp = httpx.get(AMAP_AROUND_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return []
        pois: list[Poi] = []
        for item in data.get("pois", []):
            biz = item.get("biz_ext") or {}
            lng, lat = item["location"].split(",")
            pois.append(Poi(
                id=item["id"], name=item["name"], address=item.get("address"),
                category=item.get("type"),
                rating=float(biz["rating"]) if biz.get("rating") else None,
                avg_price=float(biz["cost"]) if biz.get("cost") else None,
                source="amap", lnglat=(float(lng), float(lat)),
            ))
        return pois

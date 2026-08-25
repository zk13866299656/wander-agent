from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from food_agent.models.schemas import Poi

class PoiSearchTool(ABC):
    @abstractmethod
    def search(self, query: str, location: tuple[float, float], radius: int,
               categories: list[str]) -> list[Poi]: ...

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

class WebSearchTool(ABC):
    @abstractmethod
    def search(self, query: str) -> list[SearchResult]: ...

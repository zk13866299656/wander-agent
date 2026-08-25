from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class PreferenceKey(str, Enum):
    DIET_TABOO = "diet_taboo"
    BUDGET = "budget"
    TASTE = "taste"

class ParsedRequest(BaseModel):
    """需求解析节点输出"""
    location: str
    lnglat: tuple[float, float] | None = None
    categories: list[str] = Field(default_factory=list)
    amap_types: list[str] = Field(default_factory=list)
    budget_max: float | None = Field(default=None, ge=0)
    diet_taboos: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    is_followup: bool = False

    @field_validator("lnglat")
    @classmethod
    def _check_lnglat(cls, v):
        if v is not None and not (-180 <= v[0] <= 180 and -90 <= v[1] <= 90):
            raise ValueError("lnglat 越界")
        return v

class Poi(BaseModel):
    id: str
    name: str
    address: str | None = None
    category: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    avg_price: float | None = Field(default=None, ge=0)
    distance_m: float | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list)
    source: str
    lnglat: tuple[float, float] | None = None

class Candidate(Poi):
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)

class RecommendationCard(BaseModel):
    id: str
    source: str
    name: str
    rating: float | None
    avg_price: float | None
    distance_m: float | None
    tags: list[str]
    score: float
    reasons: list[str]

class Preference(BaseModel):
    key: PreferenceKey
    value: str
    weight: float = 1.0

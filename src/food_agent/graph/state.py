from __future__ import annotations

from typing import TypedDict

from food_agent.models.schemas import Candidate, ParsedRequest, Poi, RecommendationCard


class GraphState(TypedDict, total=False):
    user_input: str
    lnglat: tuple[float, float] | None
    parsed: ParsedRequest
    pois: list[Poi]
    candidates: list[Candidate]
    cards: list[RecommendationCard]

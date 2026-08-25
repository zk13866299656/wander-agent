from __future__ import annotations
import math
from food_agent.models.schemas import Candidate, ParsedRequest, Poi

WEIGHTS = {"rating": 0.30, "heat": 0.20, "distance": 0.20, "budget": 0.15, "preference": 0.15}
NEUTRAL_RATING = 2.5   # 无评分时的中性分（0-5 中点）
MAX_DISTANCE_M = 5000  # 距离衰减上限

def _text(p: Poi) -> str:
    return f"{p.name} {p.category or ''} {' '.join(p.tags)}"

def _rating_score(p: Poi) -> float:
    if p.rating is not None:
        return p.rating / 5.0
    if p.review_count is not None:
        return _heat_score(p)
    return NEUTRAL_RATING / 5.0

def _heat_score(p: Poi) -> float:
    if p.review_count is None:
        return 0.0
    return min(math.log10(p.review_count + 1) / 5.0, 1.0)

def _distance_score(p: Poi) -> float:
    if p.distance_m is None:
        return 0.5
    return max(0.0, 1.0 - p.distance_m / MAX_DISTANCE_M)

def _budget_score(p: Poi, req: ParsedRequest) -> float:
    if req.budget_max is None or req.budget_max <= 0 or p.avg_price is None:
        return 1.0
    if p.avg_price <= req.budget_max:
        return 1.0
    return max(0.0, 1.0 - (p.avg_price - req.budget_max) / req.budget_max)

def _preference_score(p: Poi, req: ParsedRequest) -> float:
    if not req.preferences:
        return 1.0
    text = _text(p)
    hits = sum(1 for pref in req.preferences if pref in text)
    return hits / len(req.preferences)

def score_candidate(p: Poi, req: ParsedRequest) -> Candidate:
    score = (
        WEIGHTS["rating"] * _rating_score(p)
        + WEIGHTS["heat"] * _heat_score(p)
        + WEIGHTS["distance"] * _distance_score(p)
        + WEIGHTS["budget"] * _budget_score(p, req)
        + WEIGHTS["preference"] * _preference_score(p, req)
    )
    if req.diet_taboos:
        text = _text(p)
        if any(t in text for t in req.diet_taboos):
            score *= 0.3
    return Candidate(**p.model_dump(), score=round(score, 4))

def rank(pois: list[Poi], req: ParsedRequest, top_k: int = 10) -> list[Candidate]:
    cands = [score_candidate(p, req) for p in pois]
    cands.sort(key=lambda c: c.score, reverse=True)
    return cands[:top_k]

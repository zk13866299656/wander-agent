from food_agent.models.schemas import ParsedRequest, Poi
from food_agent.ranking.scorer import rank, score_candidate, WEIGHTS

def _poi(name, rating=None, review_count=None, avg_price=None, distance_m=None, tags=None):
    return Poi(id=name, name=name, source="amap", rating=rating,
               review_count=review_count, avg_price=avg_price,
               distance_m=distance_m, tags=tags or [])

def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

def test_higher_rating_wins():
    req = ParsedRequest(location="x")
    a = _poi("a", rating=4.5, review_count=100, distance_m=1000)
    b = _poi("b", rating=3.0, review_count=100, distance_m=1000)
    assert rank([a, b], req)[0].name == "a"

def test_missing_rating_uses_neutral_not_zero():
    req = ParsedRequest(location="x")
    p = _poi("p", rating=None, review_count=None, distance_m=None)
    s = score_candidate(p, req).score
    assert s > 0  # 无评分给中性分，不直接淘汰

def test_over_budget_penalized():
    req = ParsedRequest(location="x", budget_max=100)
    cheap = _poi("cheap", rating=4.0, review_count=50, avg_price=80, distance_m=1000)
    dear = _poi("dear", rating=4.0, review_count=50, avg_price=300, distance_m=1000)
    assert rank([cheap, dear], req)[0].name == "cheap"

def test_preference_match_boosts():
    req = ParsedRequest(location="x", preferences=["性价比高"])
    hit = _poi("hit", rating=4.0, review_count=50, distance_m=1000, tags=["性价比高"])
    miss = _poi("miss", rating=4.0, review_count=50, distance_m=1000, tags=[])
    assert rank([hit, miss], req)[0].name == "hit"

def test_top_k_limit():
    req = ParsedRequest(location="x")
    pois = [_poi(str(i), rating=4.0, distance_m=1000) for i in range(20)]
    assert len(rank(pois, req, top_k=5)) == 5

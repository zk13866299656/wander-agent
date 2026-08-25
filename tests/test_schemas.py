import pytest
from pydantic import ValidationError
from food_agent.models.schemas import ParsedRequest, Poi, Preference, PreferenceKey

def test_parsed_request_defaults():
    req = ParsedRequest(location="杭州西湖")
    assert req.categories == [] and req.is_followup is False and req.budget_max is None

def test_parsed_request_rejects_bad_lnglat():
    with pytest.raises(ValidationError):
        ParsedRequest(location="x", lnglat=(999, 0))

def test_poi_rating_bounds():
    with pytest.raises(ValidationError):
        Poi(id="1", name="x", source="amap", rating=6.0)

def test_preference_key_is_closed_enum():
    p = Preference(key=PreferenceKey.DIET_TABOO, value="不吃辣")
    assert p.key == PreferenceKey.DIET_TABOO

from food_agent.memory.extract import extract_preferences
from food_agent.models.schemas import Preference, PreferenceKey


def test_extract_preferences_parses_closed_keys(monkeypatch):
    class FakePrefs:
        def __init__(self):
            self.prefs = [Preference(key=PreferenceKey.DIET_TABOO, value="不吃辣")]

    monkeypatch.setattr(
        "food_agent.memory.extract.complete_with_retry",
        lambda msgs, response_format: FakePrefs(),
    )
    out = extract_preferences("我不吃辣，预算 100 以内")
    assert out[0].value == "不吃辣"

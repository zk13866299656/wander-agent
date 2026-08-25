from __future__ import annotations

from pydantic import BaseModel, Field

from food_agent.llm.client import complete_with_retry
from food_agent.models.schemas import Preference


class PreferenceList(BaseModel):
    prefs: list[Preference] = Field(default_factory=list)


_SYSTEM = (
    "从用户这句话里抽取可复用的饮食偏好，只输出封闭类型："
    "diet_taboo（口味禁忌）、budget（预算）、taste（口味偏好）。没有则不输出该项。"
)


def extract_preferences(user_text: str) -> list[Preference]:
    msgs = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_text},
    ]
    result = complete_with_retry(msgs, response_format=PreferenceList)
    return result.prefs

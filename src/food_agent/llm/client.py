from __future__ import annotations

import time

from langchain_openai import ChatOpenAI

from food_agent.config import settings


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.2,
    )


def complete_with_retry(messages, response_format=None, retries=3):
    """带重试的 LLM 调用。response_format 传 Pydantic 类时返回结构化对象，否则返回 str。"""
    llm = build_llm()
    last: Exception | None = None
    for attempt in range(retries):
        try:
            if response_format is not None:
                return llm.with_structured_output(response_format).invoke(messages)
            return llm.invoke(messages).content
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(2**attempt)
    raise last

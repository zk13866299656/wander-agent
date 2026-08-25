from __future__ import annotations

import json
import time

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from food_agent.config import settings


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.2,
    )


def _inject_json_schema(messages: list[dict], schema_model: type[BaseModel]) -> list[dict]:
    """把输出 schema 注入 system 提示词。

    DeepSeek v4 的 json_object 模式不在 API 层接收 schema，只能靠提示词约束输出形状；
    且提示词必须出现 "json" 一词才会接受 response_format=json_object。
    """
    schema_json = json.dumps(schema_model.model_json_schema(), ensure_ascii=False)
    instruction = (
        "只输出一个 json 对象，不要输出任何额外文字或 Markdown 代码块。"
        "字段名与类型必须严格符合以下 JSON Schema：\n" + schema_json
    )
    if messages and messages[0].get("role") == "system":
        first = dict(messages[0])
        first["content"] = f"{first['content']}\n\n{instruction}"
        return [first] + list(messages[1:])
    return [{"role": "system", "content": instruction}] + list(messages)


def complete_with_retry(messages, response_format=None, retries=3):
    """带重试的 LLM 调用。response_format 传 Pydantic 类时返回结构化对象，否则返回 str。"""
    llm = build_llm()
    last: Exception | None = None
    for attempt in range(retries):
        try:
            if response_format is not None:
                msgs = _inject_json_schema(messages, response_format)
                return llm.with_structured_output(response_format, method="json_mode").invoke(msgs)
            return llm.invoke(messages).content
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(2**attempt)
    raise last

from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from food_agent.llm.client import complete_with_retry


def test_retry_on_failure():
    with patch("food_agent.llm.client.build_llm") as mk:
        mk.return_value.invoke.side_effect = [
            RuntimeError("x"),
            RuntimeError("y"),
            SimpleNamespace(content="ok"),
        ]
        out = complete_with_retry([{"role": "user", "content": "hi"}], retries=3)
        assert out == "ok"
        assert mk.return_value.invoke.call_count == 3


def test_structured_output_path():
    class DummyFormat(BaseModel):
        name: str

    with patch("food_agent.llm.client.build_llm") as mk:
        structured_llm = mk.return_value.with_structured_output.return_value
        structured_llm.invoke.return_value = SimpleNamespace(name="parsed")
        out = complete_with_retry(
            [{"role": "user", "content": "hi"}],
            response_format=DummyFormat,
        )
        assert out.name == "parsed"
        mk.return_value.with_structured_output.assert_called_once_with(
            DummyFormat, method="json_mode"
        )
        mk.return_value.invoke.assert_not_called()
        # schema 注入：首条 system 消息含 "json" 关键词与字段名
        sent = structured_llm.invoke.call_args.args[0]
        assert sent[0]["role"] == "system"
        assert "json" in sent[0]["content"]
        assert "name" in sent[0]["content"]

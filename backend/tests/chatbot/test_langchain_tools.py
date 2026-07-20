# backend/tests/chatbot/test_langchain_tools.py
import json
import pytest


def test_build_tool_schemas_returns_list():
    from backend.services.chatbot.langchain_tools import build_tool_schemas
    schemas = build_tool_schemas()
    assert isinstance(schemas, list)
    assert len(schemas) >= 16
    names = [s["function"]["name"] for s in schemas]
    assert "get_asset_price" in names
    assert "search_web" in names
    assert "get_portfolio_summary" in names


def test_build_tool_schemas_openai_format():
    from backend.services.chatbot.langchain_tools import build_tool_schemas
    schemas = build_tool_schemas()
    for schema in schemas:
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


def test_execute_tool_call_unknown_tool():
    from backend.services.chatbot.langchain_tools import execute_tool_call
    result = execute_tool_call("unknown_tool", {}, "Bearer test")
    parsed = json.loads(result)
    assert "error" in parsed or "reply" in parsed


def test_execute_tool_call_blocked_order_tool():
    from backend.services.chatbot.langchain_tools import execute_tool_call
    with pytest.raises(Exception):
        execute_tool_call("place_order", {}, "Bearer test")

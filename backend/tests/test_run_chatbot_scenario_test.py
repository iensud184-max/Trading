import pytest
from backend.scripts.run_chatbot_scenario_test import make_test_interceptor, evaluate_scenario

def test_interceptor_captures_arguments():
    captured = []
    def dummy_tool(auth_header, message, **kwargs):
        return {"success": True}
    
    wrapped = make_test_interceptor(dummy_tool, captured)
    wrapped("Bearer test", "msg", exchange="COINONE", query="BTC")
    
    assert len(captured) == 1
    assert captured[0]["exchange"] == "COINONE"
    assert captured[0]["query"] == "BTC"

def test_evaluate_scenario_passes_on_exact_match():
    captured = {"tool_name": "get_asset_price", "arguments": {"query": "BTC", "exchange": "COINONE"}}
    expected = {"tool_name": "get_asset_price", "arguments": {"query": "BTC", "exchange": "COINONE"}}
    result = evaluate_scenario(captured, expected)
    assert result["status"] == "PASS"

def test_evaluate_scenario_fails_on_mismatch():
    captured = {"tool_name": "get_asset_price", "arguments": {"query": "XRP", "exchange": "COINONE"}}
    expected = {"tool_name": "get_asset_price", "arguments": {"query": "BTC", "exchange": "COINONE"}}
    result = evaluate_scenario(captured, expected)
    assert result["status"] == "FAIL"

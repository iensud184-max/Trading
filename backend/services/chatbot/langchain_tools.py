"""LangGraph tool wrappers around existing tool_registry functions."""
import json
import logging
from typing import Any

from backend.services.chatbot.function_calling import FUNCTION_SCHEMAS
from backend.services.chatbot.safety_guard import enforce_tool_safety
from backend.services.chatbot import tool_registry

logger = logging.getLogger(__name__)

_TOOL_FUNCTION_MAP: dict[str, Any] = {
    "get_home_market_rankings": tool_registry.get_home_market_rankings,
    "get_portfolio_summary": tool_registry.get_portfolio_summary,
    "add_watchlist_item": tool_registry.add_watchlist_item,
    "remove_watchlist_item": tool_registry.remove_watchlist_item,
    "get_holdings": tool_registry.get_holdings,
    "search_trade_history": tool_registry.search_trade_history,
    "list_open_orders": tool_registry.list_open_orders,
    "get_exchange_rate": tool_registry.get_exchange_rate,
    "get_asset_krw_conversion": tool_registry.get_asset_krw_conversion,
    "get_market_calendar": tool_registry.get_market_calendar,
    "get_asset_price": tool_registry.get_asset_price,
    "get_asset_orderbook": tool_registry.get_asset_orderbook,
    "get_asset_candles": tool_registry.get_asset_candles,
    "get_crypto_market_context": tool_registry.get_crypto_market_context,
    "get_asset_outlook": tool_registry.get_asset_outlook,
    "search_web": tool_registry.search_web,
}


def build_tool_schemas() -> list[dict]:
    """Return OpenAI-compatible tool schemas for LLM bind_tools."""
    return [
        {"type": "function", "function": schema}
        for schema in FUNCTION_SCHEMAS
    ]


def _build_tool_message(tool_name: str, arguments: dict, fallback_text: str) -> str:
    """Build the query message string for a tool call, matching chat_service patterns."""
    query = str(arguments.get("query") or fallback_text).strip()
    if tool_name in {"search_web", "add_watchlist_item", "get_asset_outlook", "remove_watchlist_item"}:
        return query
    if tool_name == "get_crypto_market_context":
        return f"{query} 코인 분석해줘"
    if tool_name == "get_asset_price":
        return f"{query} 현재가 알려줘"
    if tool_name == "get_asset_orderbook":
        return f"{query} 호가 알려줘"
    if tool_name == "get_asset_candles":
        return f"{query} 캔들 흐름 알려줘"
    if tool_name == "get_market_calendar":
        date = str(arguments.get("date") or "").strip()
        market_country = str(arguments.get("market_country") or "").strip().upper()
        market_text = "한국장" if market_country == "KR" else "미국장" if market_country == "US" else ""
        return " ".join(part for part in [date, market_text, "장 운영 여부 알려줘"] if part)
    if tool_name == "get_exchange_rate":
        base = str(arguments.get("base_currency") or "").strip()
        quote = str(arguments.get("quote_currency") or "KRW").strip()
        return f"{base}/{quote} 환율 알려줘".strip()
    if tool_name == "get_home_market_rankings":
        asset_type = str(arguments.get("asset_type") or "").upper()
        asset_text = "코인" if asset_type == "CRYPTO" else "국내주식" if asset_type == "STOCK" else ""
        ranking = arguments.get("ranking") or "상승률"
        return f"{asset_text} {ranking} 순위"
    if tool_name == "search_trade_history":
        parts = ["거래내역"]
        if arguments.get("symbol"):
            parts.append(str(arguments["symbol"]))
        return " ".join(parts)
    if tool_name == "list_open_orders":
        parts = ["미체결 주문"]
        if arguments.get("symbol"):
            parts.append(str(arguments["symbol"]))
        return " ".join(parts)
    if tool_name == "get_asset_krw_conversion":
        quantity = arguments.get("quantity")
        quantity_text = f"{quantity}주" if quantity else ""
        return " ".join(part for part in [query, quantity_text, "원화로 계산해줘"] if part)
    return query


def execute_tool_call(tool_name: str, arguments: dict, auth_header: str) -> str:
    """Execute a tool call and return the result as a JSON string.

    Raises SafetyGuardError for blocked tools (e.g., place_order).
    """
    enforce_tool_safety(tool_name, arguments)

    tool_func = _TOOL_FUNCTION_MAP.get(tool_name)
    if not tool_func:
        return json.dumps(
            {"reply": f"'{tool_name}' 도구를 찾을 수 없습니다.", "data": {"error": "unknown_tool"}},
            ensure_ascii=False,
        )

    tool_message = _build_tool_message(tool_name, arguments, "")
    try:
        result = tool_func(auth_header, tool_message, **arguments)
    except Exception as error:
        logger.exception("Tool execution failed: tool=%s", tool_name)
        return json.dumps(
            {"reply": f"도구 실행 중 오류가 발생했습니다: {str(error)[:200]}", "data": {"error": "tool_error"}},
            ensure_ascii=False,
        )

    if not isinstance(result, dict):
        return json.dumps({"reply": str(result or ""), "data": {}}, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False, default=str)

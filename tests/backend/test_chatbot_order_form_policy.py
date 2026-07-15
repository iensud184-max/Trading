import importlib

import pytest

from backend.services.chatbot import chat_service
from backend.services.chatbot import tool_registry
from backend.services.chatbot.chat_service import ChatbotService


def _build_service() -> ChatbotService:
    return ChatbotService()


def test_plain_order_returns_order_form_action_without_proposal(monkeypatch):
    service = _build_service()
    monkeypatch.setattr(
        chat_service,
        "run_chatbot_tool",
        lambda *args, **kwargs: {
            "reply": "주문 제안이 생성되었습니다.",
            "data": {"source": "TRADE_PROPOSAL"},
        },
    )

    result = service.reply("코인원 XRP 10개 800원에 사줘", user_id=None, auth_header=None)

    assert result["meta"]["tool_result"]["source"] == "ORDER_FORM_REDIRECT"
    assert result["actions"][0]["type"] == "open_order_form"
    assert result["actions"][0]["prefill"] == {
        "exchange": "COINONE",
        "symbol_query": "XRP",
        "side": "BUY",
        "quantity": 10.0,
        "order_type": "LIMIT",
        "price": 800.0,
    }


def test_order_form_policy_does_not_guess_unmentioned_fields():
    policy = importlib.import_module("backend.services.chatbot.order_form_policy")

    result = policy.build_order_form_redirect("삼성전자 10주 사줘")

    assert result is not None
    assert result["data"]["prefill"] == {
        "symbol_query": "삼성전자",
        "side": "BUY",
        "quantity": 10.0,
    }


def test_structured_order_keeps_existing_proposal_path(monkeypatch):
    service = _build_service()
    expected = {"reply": "구조화 주문 제안", "actions": [], "data": {"source": "STRUCTURED_ORDER"}}
    monkeypatch.setattr(
        service,
        "_create_proposal_from_structured",
        lambda auth_header, user_id, structured_order: expected,
    )

    result = service.reply(
        "[주문 폼 전송]",
        user_id="user-1",
        auth_header="Bearer test",
        structured_order={
            "is_structured_order": True,
            "exchange": "TOSS",
            "broker_env": "REAL",
            "symbol_query": "삼성전자",
            "side": "BUY",
            "quantity": 1,
            "order_type": "LIMIT",
            "price": 70000,
        },
    )

    assert result == expected


@pytest.mark.parametrize(
    "message",
    [
        "삼성전자 10주 사줘",
        "XRP 전량 팔아줘",
        "1번 추천 종목 매수 제안해줘",
        "비트코인 조건매도 등록해줘",
    ],
)
def test_all_plain_order_messages_are_redirected_to_form(message):
    policy = importlib.import_module("backend.services.chatbot.order_form_policy")

    result = policy.build_order_form_redirect(message)

    assert result is not None
    assert result["data"]["source"] == "ORDER_FORM_REDIRECT"


def test_investment_question_does_not_open_order_form():
    policy = importlib.import_module("backend.services.chatbot.order_form_policy")

    assert policy.build_order_form_redirect("비트코인 지금 살까?") is None


def test_direct_tool_routing_cannot_create_plain_order(monkeypatch):
    monkeypatch.setattr(
        tool_registry,
        "_resolve_symbol",
        lambda auth_header, query: {
            "symbol": "005930",
            "display_name": "삼성전자",
            "asset_type": "STOCK_KR",
            "market": "KR",
        },
    )
    monkeypatch.setattr(tool_registry, "_is_plain_order_requiring_confirmation", lambda message, parsed: False)
    monkeypatch.setattr(
        tool_registry,
        "create_trade_proposal_from_message",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("일반 도구 라우팅에서 제안 생성 금지")),
    )

    result = tool_registry.run_chatbot_tool("Bearer test", "삼성전자 10주 사줘")

    assert result is not None
    assert result["data"]["source"] == "ORDER_FORM_REDIRECT"


@pytest.mark.parametrize("pending_action", ["trade_order_confirmation", "trade_proposal_retry"])
def test_legacy_pending_order_confirmation_redirects_to_form(monkeypatch, pending_action):
    service = _build_service()
    monkeypatch.setattr(
        tool_registry,
        "create_trade_proposal_from_message",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("기존 대기 작업에서 제안 생성 금지")),
    )

    result = service._run_pending_action(
        pending_action,
        "Bearer test",
        "응 진행해줘",
        {"message": "삼성전자 10주 사줘"},
    )

    assert result is not None
    assert result["data"]["source"] == "ORDER_FORM_REDIRECT"

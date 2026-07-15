import importlib

from backend.services.chatbot import chat_service
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

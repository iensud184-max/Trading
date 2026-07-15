from backend.services.chatbot.order_parser import parse_order_intent


def _build_prefill(intent) -> dict:
    prefill = {}
    if intent.symbol_query:
        prefill["symbol_query"] = intent.symbol_query
    if intent.side:
        prefill["intent"] = intent.side
    if intent.quantity is not None:
        prefill["quantity"] = intent.quantity
    if intent.price is not None:
        prefill["price"] = intent.price
        prefill["order_type"] = "LIMIT"
    elif intent.order_type:
        prefill["order_type"] = intent.order_type
    if intent.broker_env:
        prefill["broker_env"] = intent.broker_env
    return prefill


def build_order_form_redirect(message: str) -> dict | None:
    intent = parse_order_intent(message)
    if not intent.is_order_request:
        return None
    prefill = _build_prefill(intent)

    return {
        "reply": "주문은 매매 요청 폼에서 계좌, 종목, 수량, 가격을 직접 확인한 뒤 진행할 수 있습니다.",
        "actions": [
            {
                "type": "open_order_form",
                "label": "매매 요청 열기",
                "prefill": prefill,
            },
        ],
        "data": {
            "source": "ORDER_ENTRY_REQUIRED",
            "prefill": prefill,
        },
    }

from backend.services.chatbot.order_parser import ParsedOrderIntent, parse_order_intent


def build_order_form_redirect(message: str) -> dict | None:
    intent = parse_order_intent(message)
    if not intent.is_order_request:
        return None

    prefill = _build_prefill(message, intent)
    return {
        "reply": (
            "주문은 매매 요청 폼에서 내용을 확인한 뒤 진행할 수 있어요.\n"
            "인식한 내용은 임시 입력값이므로 거래소, 수량, 가격을 다시 확인해 주세요."
        ),
        "actions": [
            {
                "type": "open_order_form",
                "label": "매매 요청 열기",
                "prefill": prefill,
            }
        ],
        "data": {
            "source": "ORDER_FORM_REDIRECT",
            "prefill": prefill,
        },
    }


def _build_prefill(message: str, intent: ParsedOrderIntent) -> dict:
    prefill = {}
    exchange = _detect_explicit_exchange(message)
    if exchange:
        prefill["exchange"] = exchange
    if intent.broker_env:
        prefill["broker_env"] = intent.broker_env
    if intent.symbol_query:
        prefill["symbol_query"] = intent.symbol_query
    if intent.side:
        prefill["side"] = intent.side
    if intent.quantity is not None and intent.quantity > 0:
        prefill["quantity"] = intent.quantity
    if intent.price is not None and intent.price > 0:
        prefill["order_type"] = "LIMIT"
        prefill["price"] = intent.price
    elif "시장가" in str(message or ""):
        prefill["order_type"] = "MARKET"
    return prefill


def _detect_explicit_exchange(message: str) -> str:
    text = str(message or "")
    upper_text = text.upper()
    if "코인원" in text or "COINONE" in upper_text:
        return "COINONE"
    if "바이낸스" in text or "BINANCE" in upper_text:
        return "BINANCE"
    if "한국투자" in text or "한투" in text or "KIS" in upper_text:
        return "KIS"
    if "토스" in text or "TOSS" in upper_text:
        return "TOSS"
    return ""

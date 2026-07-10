from backend.app import app
from backend.routes import trade
from backend.routes.trade import (
    _claim_trade_proposal_for_execution,
    _exceeds_real_order_limit,
)


def _safe_precheck(**overrides):
    payload = {
        "reference_price": 800.0,
        "estimated_amount": 8000.0,
        "estimated_amount_krw": 8000.0,
        "exceeds_real_order_limit": False,
        "is_market_closed": False,
        "futures_real_blocked": False,
        "insufficient_permission": False,
        "insufficient_cash": False,
        "insufficient_holding": False,
    }
    payload.update(overrides)
    return payload


class FakeOrderClient:
    def __init__(self):
        self.place_order_calls = 0

    def place_order(self, **kwargs):
        self.place_order_calls += 1
        return {
            "status": "OPEN",
            "order_id": "order-1",
            "client_order_id": "client-1",
            "raw": {},
        }


class TossClient(FakeOrderClient):
    def get_exchange_rate(self):
        return 1500.0

    def get_balance(self):
        return {
            "available_cash": 10000.0,
            "available_cash_details": {
                "components": [
                    {"currency": "USD", "cash_buying_power": 10000.0},
                ],
            },
            "holdings": [],
        }


def test_real_order_limit_applies_only_to_real_orders():
    assert _exceeds_real_order_limit("REAL", 100001) is True
    assert _exceeds_real_order_limit("REAL", 100000) is False
    assert _exceeds_real_order_limit("MOCK", 5000000) is False


def test_claim_trade_proposal_returns_none_after_first_claim(monkeypatch):
    calls = []

    def fake_query(auth_header, endpoint, method="GET", json_data=None, params=None):
        assert endpoint == "rpc/claim_trade_proposal_for_execution"
        calls.append(json_data["p_proposal_id"])
        if len(calls) == 1:
            return [{"id": "proposal-1", "status": "APPROVED"}]
        return []

    monkeypatch.setattr("backend.routes.trade.query_supabase", fake_query)

    assert _claim_trade_proposal_for_execution("Bearer test", "proposal-1")["status"] == "APPROVED"
    assert _claim_trade_proposal_for_execution("Bearer test", "proposal-1") is None


def test_same_proposal_is_sent_to_exchange_only_once(monkeypatch):
    order_client = FakeOrderClient()
    claims = iter([
        {"id": "proposal-1", "status": "APPROVED"},
        None,
    ])
    proposal = {
        "id": "proposal-1",
        "status": "PENDING",
        "exchange": "COINONE",
        "symbol": "XRP",
        "side": "BUY",
        "ord_type": "LIMIT",
        "price": 800,
        "volume": 10,
        "broker_env": "MOCK",
    }

    monkeypatch.setattr(trade, "get_user_id_from_header", lambda auth_header: ("user-1", "token"))
    monkeypatch.setattr(trade, "_load_user_trade_proposal", lambda *args: dict(proposal))
    monkeypatch.setattr(trade, "_load_user_exchange_record", lambda *args: ({}, "access", "secret"))
    monkeypatch.setattr(trade, "_build_precheck_payload", lambda **kwargs: _safe_precheck())
    monkeypatch.setattr(trade, "_claim_trade_proposal_for_execution", lambda *args: next(claims))
    monkeypatch.setattr(trade, "_build_exchange_client", lambda *args: order_client)
    monkeypatch.setattr(trade, "_patch_trade_proposal", lambda *args, **kwargs: None)

    client = app.test_client()
    first = client.post(
        "/api/trade/proposal/approve",
        headers={"Authorization": "Bearer test"},
        json={"proposal_id": "proposal-1"},
    )
    second = client.post(
        "/api/trade/proposal/approve",
        headers={"Authorization": "Bearer test"},
        json={"proposal_id": "proposal-1"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert order_client.place_order_calls == 1


def test_manual_real_order_limit_blocks_before_exchange_order(monkeypatch):
    order_client = FakeOrderClient()
    monkeypatch.setattr(trade, "get_user_id_from_header", lambda auth_header: ("user-1", "token"))
    monkeypatch.setattr(trade, "_load_user_exchange_record", lambda *args: ({}, "access", "secret"))
    monkeypatch.setattr(
        trade,
        "_build_precheck_payload",
        lambda **kwargs: _safe_precheck(
            estimated_amount=100001.0,
            estimated_amount_krw=100001.0,
            exceeds_real_order_limit=True,
        ),
    )
    monkeypatch.setattr(trade, "_build_exchange_client", lambda *args: order_client)
    monkeypatch.setattr(trade, "_insert_trade_proposal_with_schema_fallback", lambda *args: None)

    response = app.test_client().post(
        "/api/trade/order",
        headers={"Authorization": "Bearer test"},
        json={
            "exchange": "COINONE",
            "symbol": "XRP",
            "action": "BUY",
            "order_type": "LIMIT",
            "price": 100001,
            "quantity": 1,
            "broker_env": "REAL",
        },
    )

    assert response.status_code == 400
    assert "100,000원" in response.get_json()["message"]
    assert order_client.place_order_calls == 0


def test_toss_us_precheck_converts_order_amount_to_krw(monkeypatch):
    order_client = TossClient()
    monkeypatch.setattr(trade, "_build_exchange_client", lambda *args: order_client)
    monkeypatch.setattr(trade, "is_us_market_open", lambda client: True)

    precheck = trade._build_precheck_payload(
        exchange="TOSS",
        symbol="AAPL",
        action="BUY",
        order_type="LIMIT",
        quantity=1,
        price=70,
        broker_env="REAL",
        record={},
        access_key="access",
        secret_key="secret",
    )

    assert precheck["currency"] == "USD"
    assert precheck["estimated_amount_krw"] == 105000
    assert precheck["exceeds_real_order_limit"] is True


def test_toss_us_real_order_limit_blocks_before_exchange_order(monkeypatch):
    order_client = TossClient()
    monkeypatch.setattr(trade, "get_user_id_from_header", lambda auth_header: ("user-1", "token"))
    monkeypatch.setattr(trade, "_load_user_exchange_record", lambda *args: ({}, "access", "secret"))
    monkeypatch.setattr(trade, "_build_exchange_client", lambda *args: order_client)
    monkeypatch.setattr(trade, "is_us_market_open", lambda client: True)
    monkeypatch.setattr(trade, "_insert_trade_proposal_with_schema_fallback", lambda *args: None)

    response = app.test_client().post(
        "/api/trade/order",
        headers={"Authorization": "Bearer test"},
        json={
            "exchange": "TOSS",
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "LIMIT",
            "price": 70,
            "quantity": 1,
            "broker_env": "REAL",
        },
    )

    assert response.status_code == 400
    assert "100,000원" in response.get_json()["message"]
    assert order_client.place_order_calls == 0

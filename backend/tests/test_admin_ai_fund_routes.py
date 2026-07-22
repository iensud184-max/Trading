import pytest
from backend.app import app
import backend.routes.admin_ai_fund as admin_ai_fund_route


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_get_ai_fund_configs_requires_auth(client):
    res = client.get("/api/admin/ai-fund/configs")
    assert res.status_code == 401


def test_kill_switch_requires_auth(client):
    res = client.post("/api/admin/ai-fund/kill-switch", json={"exchange_type": "coinone"})
    assert res.status_code == 401


def test_upsert_ai_fund_config_rejects_canary_without_positive_limit(client):
    res = client.post(
        "/api/admin/ai-fund/configs",
        headers={"Authorization": "Bearer test-token"},
        json={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "exchange_type": "coinone",
            "operation_mode": "CANARY",
            "canary_max_order_amount": 0,
        },
    )

    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_upsert_ai_fund_config_normalizes_operation_mode_and_forwards_upsert_header(client, monkeypatch):
    captured = {}

    def fake_query(endpoint, method="GET", json_data=None, params=None, extra_headers=None):
        captured.update(
            endpoint=endpoint,
            method=method,
            json_data=json_data,
            params=params,
            extra_headers=extra_headers,
        )
        return [{"id": "config-1"}]

    monkeypatch.setattr(admin_ai_fund_route, "safe_query_supabase_as_service_role", fake_query)
    res = client.post(
        "/api/admin/ai-fund/configs",
        headers={"Authorization": "Bearer test-token"},
        json={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "exchange_type": "coinone",
            "operation_mode": "canary",
            "canary_max_order_amount": 10000,
        },
    )

    assert res.status_code == 200
    assert captured["json_data"]["operation_mode"] == "CANARY"
    assert captured["extra_headers"] == {"Prefer": "resolution=merge-duplicates"}

import pytest
from backend.app import app


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

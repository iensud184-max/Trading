import pytest
from flask import Flask
from backend.routes import transfer

AUTH = {"Authorization": "Bearer test-token"}

class MockBinanceClient:
    def __init__(self):
        self.transfers = []
        self.should_raise_value_error = False
        self.should_raise_exception = False

    def transfer_internal(self, type: str, amount: float, asset: str = "USDT") -> dict:
        if self.should_raise_value_error:
            raise ValueError("Mocked value error from transfer_internal")
        if self.should_raise_exception:
            raise Exception("Mocked general exception from transfer_internal")
        self.transfers.append({
            "type": type,
            "amount": amount,
            "asset": asset
        })
        return {
            "transaction_id": "mock-tx-12345"
        }

@pytest.fixture
def mock_client():
    return MockBinanceClient()

@pytest.fixture
def app_client(monkeypatch, mock_client):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="flask-secret")
    
    # Mock auth decoding
    monkeypatch.setattr(transfer, "get_user_id_from_header", lambda _header: ("user-123", "test-token"))
    
    # Mock load exchange client
    def load_client(auth_header, user_id, exchange):
        if exchange == "BINANCE":
            return mock_client
        raise ValueError(f"Unknown exchange {exchange}")
        
    monkeypatch.setattr(transfer, "_load_exchange_client", load_client)
    
    app.register_blueprint(transfer.transfer_bp)
    return app.test_client()

def test_internal_transfer_requires_authorization(app_client):
    response = app_client.post("/api/transfer/binance/internal", json={"direction": "MAIN_UMFUTURE", "amount": 100})
    assert response.status_code == 401
    assert response.get_json() == {"success": False, "message": "인증 헤더가 누락되었습니다."}

def test_internal_transfer_invalid_direction(app_client):
    # Missing direction
    response = app_client.post("/api/transfer/binance/internal", json={"amount": 100}, headers=AUTH)
    assert response.status_code == 400
    assert "direction" in response.get_json()["message"]

    # Invalid direction string
    response = app_client.post("/api/transfer/binance/internal", json={"direction": "SPOT_FUTURE", "amount": 100}, headers=AUTH)
    assert response.status_code == 400
    assert "direction" in response.get_json()["message"]

def test_internal_transfer_invalid_amount(app_client):
    # Missing amount
    response = app_client.post("/api/transfer/binance/internal", json={"direction": "MAIN_UMFUTURE"}, headers=AUTH)
    assert response.status_code == 400
    assert "이체 수량" in response.get_json()["message"]

    # Non-numeric amount (string)
    response = app_client.post("/api/transfer/binance/internal", json={"direction": "MAIN_UMFUTURE", "amount": "abc"}, headers=AUTH)
    assert response.status_code == 400
    assert "이체 수량" in response.get_json()["message"]

    # Zero amount
    response = app_client.post("/api/transfer/binance/internal", json={"direction": "MAIN_UMFUTURE", "amount": 0}, headers=AUTH)
    assert response.status_code == 400
    assert "이체 수량" in response.get_json()["message"]

    # Negative amount
    response = app_client.post("/api/transfer/binance/internal", json={"direction": "MAIN_UMFUTURE", "amount": -10.5}, headers=AUTH)
    assert response.status_code == 400
    assert "이체 수량" in response.get_json()["message"]

    # Boolean amount
    response = app_client.post("/api/transfer/binance/internal", json={"direction": "MAIN_UMFUTURE", "amount": True}, headers=AUTH)
    assert response.status_code == 400
    assert "이체 수량" in response.get_json()["message"]

def test_internal_transfer_success_main_to_umfuture(app_client, mock_client):
    response = app_client.post(
        "/api/transfer/binance/internal", 
        json={"direction": "MAIN_UMFUTURE", "amount": 50.5}, 
        headers=AUTH
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert json_data["message"] == "바이낸스 내부 이체 성공"
    assert json_data["data"]["transaction_id"] == "mock-tx-12345"
    
    assert len(mock_client.transfers) == 1
    assert mock_client.transfers[0] == {
        "type": "MAIN_UMFUTURE",
        "amount": 50.5,
        "asset": "USDT"
    }

def test_internal_transfer_success_umfuture_to_main(app_client, mock_client):
    response = app_client.post(
        "/api/transfer/binance/internal", 
        json={"direction": "UMFUTURE_MAIN", "amount": 100}, 
        headers=AUTH
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert json_data["data"]["transaction_id"] == "mock-tx-12345"
    
    assert len(mock_client.transfers) == 1
    assert mock_client.transfers[0] == {
        "type": "UMFUTURE_MAIN",
        "amount": 100.0,
        "asset": "USDT"
    }

def test_internal_transfer_value_error_from_client(app_client, mock_client):
    mock_client.should_raise_value_error = True
    response = app_client.post(
        "/api/transfer/binance/internal", 
        json={"direction": "MAIN_UMFUTURE", "amount": 100}, 
        headers=AUTH
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert "Mocked value error" in response.get_json()["message"]

def test_internal_transfer_general_exception_from_client(app_client, mock_client):
    mock_client.should_raise_exception = True
    response = app_client.post(
        "/api/transfer/binance/internal", 
        json={"direction": "MAIN_UMFUTURE", "amount": 100}, 
        headers=AUTH
    )
    assert response.status_code == 500
    json_data = response.get_json()
    assert json_data["success"] is False
    assert "바이낸스 내부 이체 실패" in json_data["error"]["title"]
    assert "Mocked general exception" in json_data["error"]["raw_message"]

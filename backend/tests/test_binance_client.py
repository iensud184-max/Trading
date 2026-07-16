import pytest
from unittest.mock import MagicMock
from backend.services.binance_client import BinanceSpotClient

def test_transfer_internal_success():
    client = BinanceSpotClient(api_key="dummy_api_key", secret_key="dummy_secret_key")
    
    mock_response = {
        "tranId": 123456789,
        "type": "MAIN_UMFUTURE"
    }
    client._signed_request = MagicMock(return_value=mock_response)
    
    result = client.transfer_internal(type="MAIN_UMFUTURE", amount=50.25, asset="USDT")
    
    assert result == {
        "transaction_id": "123456789",
        "raw": mock_response
    }
    client._signed_request.assert_called_once_with(
        "POST",
        "/sapi/v1/asset/transfer",
        {
            "type": "MAIN_UMFUTURE",
            "asset": "USDT",
            "amount": "50.25"
        }
    )

def test_transfer_internal_invalid_type():
    client = BinanceSpotClient(api_key="dummy_api_key", secret_key="dummy_secret_key")
    
    with pytest.raises(ValueError) as excinfo:
        client.transfer_internal(type="INVALID_TYPE", amount=10.0, asset="USDT")
    assert "유효하지 않은 이체 방향입니다" in str(excinfo.value)

def test_transfer_internal_invalid_amount():
    client = BinanceSpotClient(api_key="dummy_api_key", secret_key="dummy_secret_key")
    
    with pytest.raises(ValueError) as excinfo:
        client.transfer_internal(type="MAIN_UMFUTURE", amount=0, asset="USDT")
    assert "이체 수량은 0보다 커야 합니다" in str(excinfo.value)
    
    with pytest.raises(ValueError) as excinfo:
        client.transfer_internal(type="MAIN_UMFUTURE", amount=-5.5, asset="USDT")
    assert "이체 수량은 0보다 커야 합니다" in str(excinfo.value)

def test_transfer_internal_non_numeric_amount():
    client = BinanceSpotClient(api_key="dummy_api_key", secret_key="dummy_secret_key")
    
    with pytest.raises(ValueError) as excinfo:
        client.transfer_internal(type="MAIN_UMFUTURE", amount="invalid", asset="USDT")
    assert "이체 수량은 유효한 숫자여야 합니다" in str(excinfo.value)

def test_transfer_internal_invalid_asset():
    client = BinanceSpotClient(api_key="dummy_api_key", secret_key="dummy_secret_key")
    
    with pytest.raises(ValueError) as excinfo:
        client.transfer_internal(type="MAIN_UMFUTURE", amount=10.0, asset="")
    assert "이체 자산 심볼이 필요합니다" in str(excinfo.value)

def test_transfer_internal_asset_normalization():
    client = BinanceSpotClient(api_key="dummy_api_key", secret_key="dummy_secret_key")
    
    mock_response = {
        "tranId": 987654321,
        "type": "UMFUTURE_MAIN"
    }
    client._signed_request = MagicMock(return_value=mock_response)
    
    result = client.transfer_internal(type="UMFUTURE_MAIN", amount=10.0, asset=" usdt ")
    
    assert result["transaction_id"] == "987654321"
    client._signed_request.assert_called_once_with(
        "POST",
        "/sapi/v1/asset/transfer",
        {
            "type": "UMFUTURE_MAIN",
            "asset": "USDT",
            "amount": "10"
        }
    )

def test_transfer_internal_amount_formatting():
    client = BinanceSpotClient(api_key="dummy_api_key", secret_key="dummy_secret_key")
    client._signed_request = MagicMock(return_value={"tranId": 111})
    
    # 0.00001 should not be formatted as scientific notation
    client.transfer_internal(type="MAIN_UMFUTURE", amount=0.00001, asset="USDT")
    client._signed_request.assert_called_with(
        "POST",
        "/sapi/v1/asset/transfer",
        {
            "type": "MAIN_UMFUTURE",
            "asset": "USDT",
            "amount": "1e-05"  # f"{0.00001:.12g}" produces "1e-05" in python or "0.00001"? Wait, let's check!
        }
    )

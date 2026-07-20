import pytest
from backend.services.toss_client import TossClient

def test_toss_client_token_lock_mechanism(monkeypatch):
    lock_acquired = False
    new_token_requested = 0

    def mock_distributed_lock(lock_key, duration_seconds=120):
        nonlocal lock_acquired
        class DummyLock:
            def __enter__(self):
                nonlocal lock_acquired
                lock_acquired = True
                return True
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
        return DummyLock()

    def mock_request_new_token(self):
        nonlocal new_token_requested
        new_token_requested += 1
        return {"access_token": "new-toss-token", "expires_in": 3600}

    # 실제 모듈 경로로 직접 모킹 지정
    monkeypatch.setattr("backend.services.token_cache_service.get_db_token_with_status", lambda *args, **kwargs: {"token": None})
    monkeypatch.setattr("backend.services.token_cache_service.set_db_token", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.services.lock_service.distributed_lock", mock_distributed_lock)
    monkeypatch.setattr("backend.services.toss_client.TossClient._request_new_token", mock_request_new_token)

    client = TossClient("id", "secret", "seq", "MOCK", "user-1")
    client._access_token_cache = {}

    token = client._get_cached_token()
    assert token == "new-toss-token"
    assert lock_acquired is True
    assert new_token_requested == 1

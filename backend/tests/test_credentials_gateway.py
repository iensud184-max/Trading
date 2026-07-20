import time
import pytest
from backend.services.credentials_gateway import CredentialsGateway

def test_credentials_gateway_caching_and_invalidation(monkeypatch):
    query_count = 0
    
    def mock_query_supabase(auth_header, endpoint, method, params=None):
        nonlocal query_count
        query_count += 1
        return [{
            "encrypted_access_key": "encrypted_access",
            "encrypted_secret_key": "encrypted_secret",
            "toss_account_seq": "123"
        }]

    def mock_decrypt(self, text):
        return text.replace("encrypted_", "")

    monkeypatch.setattr("backend.services.credentials_gateway.query_supabase", mock_query_supabase)
    monkeypatch.setattr("backend.utils.crypto_helper.CryptoHelper.decrypt", mock_decrypt)

    gateway = CredentialsGateway()
    gateway._key_cache.clear()

    # 1. 최초 로딩 (DB 조회 발생)
    creds1 = gateway.get_credentials("Bearer test", "user-1", "TOSS", "MOCK")
    assert creds1["access_key"] == "access"
    assert query_count == 1

    # 2. 연속 로딩 (캐시 Hit하여 DB 조회 미발생)
    creds2 = gateway.get_credentials("Bearer test", "user-1", "TOSS", "MOCK")
    assert creds2["access_key"] == "access"
    assert query_count == 1

    # 3. 캐시 무효화 수행 후 로딩 (DB 조회 다시 발생)
    gateway.invalidate_cache("user-1", "TOSS", "MOCK")
    creds3 = gateway.get_credentials("Bearer test", "user-1", "TOSS", "MOCK")
    assert creds3["access_key"] == "access"
    assert query_count == 2

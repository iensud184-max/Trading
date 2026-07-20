import time
import os
from flask import current_app
from backend.services.supabase_client import query_supabase
from backend.utils.crypto_helper import CryptoHelper

class CredentialsGateway:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._key_cache = {}
            cls._instance._key_ttl_seconds = 60
        return cls._instance

    def _get_crypto_helper(self):
        try:
            # Flask 애플리케이션 컨텍스트에 바인딩된 글로벌 인스턴스 획득 시도
            if current_app and hasattr(current_app, "crypto"):
                return current_app.crypto
        except RuntimeError:
            pass
        # Flask 외부(테스트 등) 환경인 경우 로컬 생성
        return CryptoHelper(os.getenv("ENCRYPTION_KEY", "temporary-key-for-test"))

    def _resolve_cache_key(self, user_id: str, exchange: str, broker_env: str) -> tuple[str, str, str]:
        return (user_id, exchange, broker_env)

    def get_credentials(self, auth_header: str, user_id: str, exchange: str, broker_env: str) -> dict:
        cache_key = self._resolve_cache_key(user_id, exchange, broker_env)
        now = time.time()
        
        if cache_key in self._key_cache:
            entry = self._key_cache[cache_key]
            if now - entry["cached_at"] < self._key_ttl_seconds:
                return entry["data"]

        credential_exchange = "BINANCE" if exchange == "BINANCE_UM_FUTURES" else exchange
        params = {
            "user_id": f"eq.{user_id}",
            "exchange": f"eq.{credential_exchange}",
            "broker_env": f"eq.{broker_env}"
        }
        records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
        if not records:
            raise ValueError(f"등록된 {credential_exchange} ({broker_env}) API 키 정보가 없습니다.")

        record = records[0]
        crypto = self._get_crypto_helper()
        access_key = crypto.decrypt(record.get("encrypted_access_key"))
        secret_key = crypto.decrypt(record.get("encrypted_secret_key"))
        
        data = {
            "access_key": access_key,
            "secret_key": secret_key,
            "toss_account_seq": record.get("toss_account_seq"),
            "toss_account_no": record.get("toss_account_no"),
            "kis_account_no": record.get("kis_account_no"),
            "kis_account_code": record.get("kis_account_code", "01"),
        }
        
        self._key_cache[cache_key] = {
            "data": data,
            "cached_at": now
        }
        return data

    def invalidate_cache(self, user_id: str, exchange: str, broker_env: str) -> None:
        cache_key = self._resolve_cache_key(user_id, exchange, broker_env)
        if cache_key in self._key_cache:
            del self._key_cache[cache_key]

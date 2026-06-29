import os
import json
import logging
from typing import Any

import requests
from requests import HTTPError

logger = logging.getLogger(__name__)


class MarketIndexRepository:
    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    def upsert_latest(self, rows: list[dict[str, Any]]) -> None:
        if not self.is_configured or not rows:
            return

        # 저장 시에는 새 스키마 필드와 구 스키마 필드를 함께 정규화해서 보낸다.
        # 업서트 대상이 오래된 컬럼 구성을 가지고 있어도 깨지지 않게 맞춰주는 단계다.
        logger.info("[MarketIndex][upsert] count=%s", len(rows))
        payload = [self._compat_row(row) for row in rows]
        response = requests.post(
            f"{self.supabase_url}/rest/v1/market_indices_latest?on_conflict=symbol",
            headers=self._service_write_headers(),
            json=payload,
            timeout=60,
        )
        if response.ok:
            return

        fallback_response = requests.post(
            f"{self.supabase_url}/rest/v1/market_indices_latest?on_conflict=symbol",
            headers=self._service_write_headers(),
            json=payload,
            timeout=60,
        )
        fallback_response.raise_for_status()

    def list_latest(self) -> list[dict[str, Any]]:
        if not self.is_configured:
            return []

        try:
            response = requests.get(
                f"{self.supabase_url}/rest/v1/market_indices_latest",
                headers=self._service_read_headers(),
                params={
                    "select": "symbol,label,source,market_country,ticker,current_price,previous_close,change_price,change_rate,current_value,change_value,change_percent,currency,display_order,as_of,updated_at,raw_payload",
                    "order": "display_order.asc,updated_at.desc",
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                raise RuntimeError("market_indices_latest table is not available in Supabase yet.") from error
            return self._list_latest_fallback()
        except Exception:
            return self._list_latest_fallback()

    def _list_latest_fallback(self) -> list[dict[str, Any]]:
        # GET이 실패해도 동일 엔드포인트를 다시 조회해 일시적 헤더/응답 문제를 흡수한다.
        response = requests.get(
            f"{self.supabase_url}/rest/v1/market_indices_latest",
            headers=self._service_read_headers(),
            params={
                "select": "symbol,label,source,market_country,ticker,current_price,previous_close,change_price,change_rate,current_value,change_value,change_percent,currency,display_order,as_of,updated_at,raw_payload",
                "order": "display_order.asc,updated_at.desc",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _compat_row(self, row: dict[str, Any]) -> dict[str, Any]:
        # DB에 남아 있는 예전 컬럼명과 새 컬럼명을 동시에 읽어서 호환성을 유지한다.
        # 데이터 마이그레이션이 끝나기 전후 모두를 같은 코드로 다루기 위한 변환 레이어다.
        current_price = row.get("current_price") or row.get("current_value") or 0
        change_price = row.get("change_price") or row.get("change_value") or 0
        change_rate = row.get("change_rate") or row.get("change_percent") or 0
        previous_close = row.get("previous_close")
        if previous_close in (None, ""):
            previous_close = current_price - change_price if current_price and change_price is not None else 0
        updated_at = row.get("updated_at") or row.get("synced_at") or row.get("as_of")
        return {
            "symbol": row.get("symbol"),
            "label": row.get("label"),
            "source": row.get("source"),
            "market_country": row.get("market_country"),
            "ticker": row.get("ticker"),
            "current_price": current_price,
            "previous_close": previous_close,
            "change_price": change_price,
            "change_rate": change_rate,
            "current_value": current_price,
            "change_value": change_price,
            "change_percent": change_rate,
            "currency": row.get("currency"),
            "display_order": row.get("display_order"),
            "as_of": row.get("as_of") or row.get("synced_at") or updated_at,
            "updated_at": updated_at,
            "raw_payload": row.get("raw_payload") or {},
        }

    def _service_read_headers(self) -> dict[str, str]:
        return {
            "apikey": self.supabase_service_role_key,
            "Authorization": f"Bearer {self.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    def _service_write_headers(self) -> dict[str, str]:
        return {
            "apikey": self.supabase_service_role_key,
            "Authorization": f"Bearer {self.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }

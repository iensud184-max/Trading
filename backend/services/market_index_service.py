import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from backend.services.kis_client import KISClient


KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)
MARKET_INDEX_OPEN_STALE_SECONDS = int(os.getenv("MARKET_INDEX_OPEN_STALE_SECONDS", "180"))
MARKET_INDEX_CLOSED_STALE_SECONDS = int(os.getenv("MARKET_INDEX_CLOSED_STALE_SECONDS", "1800"))

KIS_INDEX_DEFINITIONS = [
    {
        "symbol": "USDKRW",
        "label": "USD/KRW",
        "currency": "KRW",
        "market_country": "KR",
        "display_order": 10,
        "kind": "fx",
        "code": "FX@KRWKFTC",
        "env": "REAL",
    },
    {
        "symbol": "KOSPI",
        "label": "KOSPI",
        "currency": "KRW",
        "market_country": "KR",
        "display_order": 20,
        "kind": "domestic",
        "code": "0001",
        "env": "REAL",
    },
    {
        "symbol": "KOSDAQ",
        "label": "KOSDAQ",
        "currency": "KRW",
        "market_country": "KR",
        "display_order": 30,
        "kind": "domestic",
        "code": "1001",
        "env": "REAL",
    },
    {
        "symbol": "NASDAQ100_F",
        "label": "NASDAQ 100 Futures",
        "currency": "USD",
        "market_country": "US",
        "display_order": 50,
        "kind": "overseas",
        "code": "NDX",
        "env": "REAL",
    },
    {
        "symbol": "SP500",
        "label": "S&P 500",
        "currency": "USD",
        "market_country": "US",
        "display_order": 60,
        "kind": "overseas",
        "code": "SPX",
        "env": "REAL",
    },
]
CONFIGURED_INDEX_SYMBOLS = [item["symbol"] for item in KIS_INDEX_DEFINITIONS]
CONFIGURED_INDEX_SYMBOL_SET = set(CONFIGURED_INDEX_SYMBOLS)
INDEX_DEFINITION_BY_SYMBOL = {item["symbol"]: item for item in KIS_INDEX_DEFINITIONS}


def _log_collection_stage(stage: str, symbol: str, payload: Any) -> None:
    logger.info(
        "[MarketIndex][%s] symbol=%s payload=%s",
        stage,
        symbol,
        json.dumps(payload, ensure_ascii=False, default=str),
    )


def _configured_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_by_symbol: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        if symbol not in CONFIGURED_INDEX_SYMBOL_SET:
            continue
        if symbol not in latest_by_symbol:
            latest_by_symbol[symbol] = row

    ordered_rows: list[dict[str, Any]] = []
    for symbol in CONFIGURED_INDEX_SYMBOLS:
        row = latest_by_symbol.get(symbol)
        if row:
            ordered_rows.append(row)
    return ordered_rows


def is_korean_market_open(now: datetime | None = None) -> bool:
    current = now or datetime.now(KST)
    if current.weekday() >= 5:
        return False
    minutes = current.hour * 60 + current.minute
    return 9 * 60 <= minutes <= 15 * 60 + 30


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def get_kis_market_index_client(env: str) -> KISClient | None:
    appkey = os.getenv("KIS_APPKEY", "") or os.getenv("KIS_APP_KEY", "")
    appsecret = os.getenv("KIS_APPSECRET", "") or os.getenv("KIS_APP_SECRET", "")
    if not appkey or not appsecret:
        return None

    return KISClient(
        appkey=appkey,
        appsecret=appsecret,
        cano=os.getenv("KIS_CANO", ""),
        acnt_prdt_cd=os.getenv("KIS_ACNT_PRDT_CD", "01"),
        env=env,
    )


def fetch_kis_domestic_index_snapshot(client: KISClient, definition: dict[str, Any]) -> dict[str, Any]:
    token = client._get_cached_token()
    response = requests.get(
        f"{client.base_url}/uapi/domestic-stock/v1/quotations/inquire-index-price",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": client.appkey,
            "appsecret": client.appsecret,
            "tr_id": "FHPUP02100000",
        },
        params={
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": definition["code"],
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("rt_cd") != "0":
        raise RuntimeError(payload.get("msg1") or f"Domestic index lookup failed for {definition['symbol']}")

    output = payload.get("output") or {}
    current_value = float(output.get("bstp_nmix_prpr") or 0)
    change_value = float(output.get("bstp_nmix_prdy_vrss") or 0)
    change_percent = float(output.get("bstp_nmix_prdy_ctrt") or 0)

    normalized = {
        "symbol": definition["symbol"],
        "label": definition["label"],
        "source": "KIS_OPEN_API",
        "market_country": definition["market_country"],
        "ticker": definition["code"],
        "current_value": current_value,
        "change_value": change_value,
        "change_percent": change_percent,
        "currency": definition["currency"],
        "display_order": definition["display_order"],
        "as_of": datetime.now(timezone.utc).isoformat(),
        "raw_payload": payload,
    }
    _log_collection_stage(
        "raw",
        definition["symbol"],
        {
            "endpoint": "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            "env": definition.get("env"),
            "params": {
                "FID_COND_MRKT_DIV_CODE": "U",
                "FID_INPUT_ISCD": definition["code"],
            },
            "response": payload,
        },
    )
    _log_collection_stage("normalized", definition["symbol"], normalized)
    return normalized


def fetch_kis_overseas_index_snapshot(client: KISClient, definition: dict[str, Any]) -> dict[str, Any]:
    token = client._get_cached_token()
    response = requests.get(
        f"{client.base_url}/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": client.appkey,
            "appsecret": client.appsecret,
            "tr_id": "FHKST03030200",
        },
        params={
            "FID_COND_MRKT_DIV_CODE": "N",
            "FID_INPUT_ISCD": definition["code"],
            "FID_HOUR_CLS_CODE": "0",
            "FID_PW_DATA_INCU_YN": "Y",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("rt_cd") != "0":
        raise RuntimeError(payload.get("msg1") or f"Overseas index lookup failed for {definition['symbol']}")

    output = payload.get("output1") or {}
    current_value = float(output.get("ovrs_nmix_prpr") or 0)
    change_value = float(output.get("ovrs_nmix_prdy_vrss") or 0)
    change_percent = float(output.get("prdy_ctrt") or 0)
    if current_value == 0 and change_value == 0 and change_percent == 0:
        raise RuntimeError(f"Overseas index returned empty values for {definition['symbol']}")

    normalized = {
        "symbol": definition["symbol"],
        "label": definition["label"],
        "source": "KIS_OPEN_API",
        "market_country": definition["market_country"],
        "ticker": definition["code"],
        "current_value": current_value,
        "change_value": change_value,
        "change_percent": change_percent,
        "currency": definition["currency"],
        "display_order": definition["display_order"],
        "as_of": datetime.now(timezone.utc).isoformat(),
        "raw_payload": payload,
    }
    _log_collection_stage(
        "raw",
        definition["symbol"],
        {
            "endpoint": "/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice",
            "env": definition.get("env"),
            "params": {
                "FID_COND_MRKT_DIV_CODE": "N",
                "FID_INPUT_ISCD": definition["code"],
                "FID_HOUR_CLS_CODE": "0",
                "FID_PW_DATA_INCU_YN": "Y",
            },
            "response": payload,
        },
    )
    _log_collection_stage("normalized", definition["symbol"], normalized)
    return normalized


def fetch_kis_fx_snapshot(client: KISClient, definition: dict[str, Any]) -> dict[str, Any]:
    token = client._get_cached_token()
    response = requests.get(
        f"{client.base_url}/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": client.appkey,
            "appsecret": client.appsecret,
            "tr_id": "FHKST03030200",
        },
        params={
            "FID_COND_MRKT_DIV_CODE": "X",
            "FID_INPUT_ISCD": definition["code"],
            "FID_HOUR_CLS_CODE": "0",
            "FID_PW_DATA_INCU_YN": "Y",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("rt_cd") != "0":
        raise RuntimeError(payload.get("msg1") or f"FX lookup failed for {definition['symbol']}")

    output = payload.get("output1") or {}
    current_value = float(output.get("ovrs_nmix_prpr") or 0)
    change_value = float(output.get("ovrs_nmix_prdy_vrss") or 0)
    change_percent = float(output.get("prdy_ctrt") or 0)
    if current_value == 0 and change_value == 0 and change_percent == 0:
        raise RuntimeError(f"FX returned empty values for {definition['symbol']}")

    normalized = {
        "symbol": definition["symbol"],
        "label": definition["label"],
        "source": "KIS_OPEN_API",
        "market_country": definition["market_country"],
        "ticker": definition["code"],
        "current_value": current_value,
        "change_value": change_value,
        "change_percent": change_percent,
        "currency": definition["currency"],
        "display_order": definition["display_order"],
        "as_of": datetime.now(timezone.utc).isoformat(),
        "raw_payload": payload,
    }
    _log_collection_stage(
        "raw",
        definition["symbol"],
        {
            "endpoint": "/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice",
            "env": definition.get("env"),
            "params": {
                "FID_COND_MRKT_DIV_CODE": "X",
                "FID_INPUT_ISCD": definition["code"],
                "FID_HOUR_CLS_CODE": "0",
                "FID_PW_DATA_INCU_YN": "Y",
            },
            "response": payload,
        },
    )
    _log_collection_stage("normalized", definition["symbol"], normalized)
    return normalized


def fetch_kis_index_snapshot(client: KISClient, definition: dict[str, Any]) -> dict[str, Any]:
    if definition["kind"] == "domestic":
        return fetch_kis_domestic_index_snapshot(client, definition)
    if definition["kind"] == "fx":
        return fetch_kis_fx_snapshot(client, definition)
    return fetch_kis_overseas_index_snapshot(client, definition)


def collect_market_index_rows() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    clients_by_env: dict[str, KISClient | None] = {}

    for definition in KIS_INDEX_DEFINITIONS:
        try:
            env = definition.get("env", "REAL")
            if env not in clients_by_env:
                client = get_kis_market_index_client(env)
                if client is not None:
                    # Reuse one access token per env during a single collection pass.
                    cached_token = client._get_cached_token()
                    client._get_cached_token = lambda cached_token=cached_token: cached_token
                clients_by_env[env] = client
            client = clients_by_env[env]
            if client is None:
                raise RuntimeError("KIS market index credentials are not configured.")
            rows.append(fetch_kis_index_snapshot(client, definition))
        except Exception as error:
            errors.append({
                "symbol": definition["symbol"],
                "message": str(error),
            })
            _log_collection_stage("error", definition["symbol"], {"message": str(error)})

    return rows, errors


def serialize_market_index_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _configured_rows(rows)
    open_market = is_korean_market_open()
    stale_seconds = MARKET_INDEX_OPEN_STALE_SECONDS if open_market else MARKET_INDEX_CLOSED_STALE_SECONDS

    items: list[dict[str, Any]] = []
    latest_updated_at: datetime | None = None

    for row in rows:
        as_of = parse_datetime(row.get("as_of"))
        if as_of and (latest_updated_at is None or as_of > latest_updated_at):
            latest_updated_at = as_of

        age_seconds = None
        if as_of:
            age_seconds = (datetime.now(timezone.utc) - as_of.astimezone(timezone.utc)).total_seconds()

        change_value = float(row.get("change_value") or 0)
        items.append({
            "key": row.get("symbol"),
            "label": row.get("label") or row.get("symbol"),
            "value": float(row.get("current_value") or 0),
            "change": change_value,
            "changePercent": float(row.get("change_percent") or 0),
            "direction": "up" if change_value > 0 else "down" if change_value < 0 else "flat",
            "updatedAt": row.get("as_of"),
            "currency": row.get("currency") or "USD",
            "stale": bool(age_seconds is None or age_seconds > stale_seconds),
        })

    return {
        "items": items,
        "fetchedAt": latest_updated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if latest_updated_at else None,
        "source": "supabase.market_indices_latest",
    }


def market_index_rows_need_refresh(rows: list[dict[str, Any]]) -> bool:
    rows = _configured_rows(rows)
    if not rows:
        return True

    row_symbols = {str(row.get("symbol") or "").upper() for row in rows}
    if row_symbols != CONFIGURED_INDEX_SYMBOL_SET:
        return True

    payload = serialize_market_index_rows(rows)
    items = payload.get("items") or []
    if not items:
        return True

    # If any configured index is stale, refresh from KIS before responding.
    return any(bool(item.get("stale")) for item in items)

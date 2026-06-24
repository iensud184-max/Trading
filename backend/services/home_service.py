import os
import re
import requests
from datetime import datetime
from backend.services.kis_client import KISClient

COINONE_HOME_LIMIT = int(os.getenv("COINONE_HOME_LIMIT", "20"))
KIS_APPKEY = os.getenv("KIS_APPKEY")
KIS_APPSECRET = os.getenv("KIS_APPSECRET")
KIS_CANO = os.getenv("KIS_CANO")
KIS_ACNT_PRDT_CD = os.getenv("KIS_ACNT_PRDT_CD")
KIS_ENV = os.getenv("KIS_ENV", "MOCK")

def to_float(value, default=0.0):
    """값을 float으로 안전하게 변환하며, 에러 발생 시 기본값을 반환합니다."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def normalize_coinone_ticker(symbol: str, ticker: dict) -> dict:
    """코인원 티커 정보를 통일된 형식으로 정규화합니다."""
    last = to_float(
        ticker.get("last")
        or ticker.get("close")
        or ticker.get("price")
        or ticker.get("last_price")
    )
    first = to_float(
        ticker.get("first")
        or ticker.get("open")
        or ticker.get("yesterday_price")
        or ticker.get("prev_close")
    )
    high = to_float(ticker.get("high"))
    low = to_float(ticker.get("low"))
    change_rate = to_float(
        ticker.get("change_rate")
        or ticker.get("rate")
        or ticker.get("change")
        or ticker.get("price_change_percent")
    )
    trading_volume = to_float(
        ticker.get("volume")
        or ticker.get("trading_volume")
        or ticker.get("quote_volume")
        or ticker.get("acc_volume")
    )
    trading_value = to_float(
        ticker.get("quote_volume")
        or ticker.get("trading_value")
        or ticker.get("acc_trading_value")
    )

    if not change_rate and first:
        change_rate = ((last - first) / first) * 100 if first else 0.0

    if not first:
        first = last

    if not trading_value and last and trading_volume:
        trading_value = last * trading_volume

    return {
        "symbol": symbol,
        "name": symbol,
        "price": last,
        "open": first,
        "high": high,
        "low": low,
        "change_rate": change_rate,
        "trading_volume": trading_volume,
        "trading_value": trading_value,
    }

def fetch_coinone_overview(limit=COINONE_HOME_LIMIT) -> list[dict]:
    """코인원 마켓 오버뷰 정보를 조회하고 정렬하여 반환합니다."""
    url = "https://api.coinone.co.kr/public/v2/ticker_new/KRW"
    response = requests.get(url, params={"additional_data": "true"}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    if payload.get("result") not in (None, "success"):
        raise Exception(payload.get("error_message") or payload.get("message") or "Coinone API error")

    rows = []
    for ticker in payload.get("tickers", []):
        symbol = str(
            ticker.get("target_currency")
            or ticker.get("currency")
            or ticker.get("symbol")
            or ""
        ).upper().strip()
        if not symbol:
            continue
        rows.append(normalize_coinone_ticker(symbol, ticker))

    rows.sort(key=lambda item: (item.get("trading_value", 0.0), abs(item.get("change_rate", 0.0))), reverse=True)
    return rows[:limit]

def split_kis_holdings(holdings: list[dict]) -> tuple[list[dict], list[dict]]:
    """보유 잔고 종목을 국내 주식과 해외 주식으로 구분하여 반환합니다."""
    domestic = []
    foreign = []

    for stock in holdings or []:
        symbol = str(stock.get("symbol", "")).strip()
        row = {
            "symbol": symbol,
            "name": stock.get("name", symbol),
            "qty": to_float(stock.get("qty")),
            "avg_price": to_float(stock.get("avg_price")),
            "current_price": to_float(stock.get("current_price")),
            "profit": to_float(stock.get("profit")),
            "profit_rate": to_float(stock.get("profit_rate")),
        }

        if re.search(r"[A-Za-z]", symbol):
            foreign.append(row)
        else:
            domestic.append(row)

    domestic.sort(key=lambda item: abs(item["profit_rate"]), reverse=True)
    foreign.sort(key=lambda item: abs(item["profit_rate"]), reverse=True)
    return domestic, foreign

def resolve_kis_credentials(data: dict) -> dict:
    """사용자가 제공한 KIS 인증 정보가 없으면 환경변수 값으로 대체하여 반환합니다."""
    return {
        "appkey": data.get("appkey") or KIS_APPKEY,
        "appsecret": data.get("appsecret") or KIS_APPSECRET,
        "cano": data.get("cano") or KIS_CANO,
        "acnt_prdt_cd": data.get("acnt_prdt_cd") or KIS_ACNT_PRDT_CD,
        "env": (data.get("env") or KIS_ENV or "MOCK").upper(),
    }

def build_home_overview(data: dict) -> dict:
    """홈 화면에서 보여줄 국내/해외주식 잔고 및 가상자산 시세 정보를 통합해 구성합니다."""
    kis = resolve_kis_credentials(data)
    appkey = kis["appkey"]
    appsecret = kis["appsecret"]
    cano = kis["cano"]
    acnt_prdt_cd = kis["acnt_prdt_cd"]
    env = kis["env"]

    result = {
        "kis": None,
        "coins": [],
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "message": "",
    }

    try:
        result["coins"] = fetch_coinone_overview()
    except Exception as coin_error:
        result["message"] = f"Coinone 조회 실패: {str(coin_error)}"

    if not (appkey and appsecret and cano):
        if not result["message"]:
            result["message"] = "KIS 환경변수가 없어서 국내/해외 보유 종목은 비어 있습니다."
        return result

    client = KISClient(
        appkey=appkey,
        appsecret=appsecret,
        cano=cano,
        acnt_prdt_cd=acnt_prdt_cd,
        env=env,
    )

    balance = client.get_balance()
    domestic_holdings, foreign_holdings = split_kis_holdings(balance.get("holdings", []))

    result["kis"] = {
        "total_evaluation": to_float(balance.get("total_evaluation")),
        "available_cash": to_float(balance.get("available_cash")),
        "domestic": domestic_holdings,
        "foreign": foreign_holdings,
    }
    return result

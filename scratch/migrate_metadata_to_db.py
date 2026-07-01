# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
import requests

# 프로젝트 루트 경로를 path에 추가하여 백엔드 모듈 임포트 가능하도록 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# .env 환경 변수 로드
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "backend" / ".env")

from backend.services.kis_market_universe import clean_stock_name
from backend.services.symbol_metadata import SYMBOL_METADATA

def main():
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_role_key:
        print("오류: Supabase 자격증명이 .env 파일에 누락되었습니다.")
        return 1

    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json"
    }

    # 1. 잘못 적재되었던 가짜 이노스페이스 종목코드 '461350' 레코드 삭제
    print("1. DB에서 잘못된 이노스페이스 종목코드(461350) 제거 시도...")
    del_res1 = requests.delete(
        f"{supabase_url}/rest/v1/kis_stock_master?symbol=eq.461350",
        headers=headers
    )
    del_res2 = requests.delete(
        f"{supabase_url}/rest/v1/kis_stock_turnover_latest?symbol=eq.461350",
        headers=headers
    )
    print(f"   - kis_stock_master 삭제 결과: {del_res1.status_code}")
    print(f"   - kis_stock_turnover_latest 삭제 결과: {del_res2.status_code}")

    # 2. 기존 DB 종목 마스터 가져오기 및 한글명 정제 작업
    print("\n2. DB에서 기존 KIS 종목 마스터 데이터를 로드하여 정제 준비 중...")
    all_records = []
    limit = 1000
    offset = 0

    while True:
        r = requests.get(
            f"{supabase_url}/rest/v1/kis_stock_master",
            headers=headers,
            params={
                "select": "symbol,name,market_segment,market_country,asset_type,source,is_active,source_file_row,listed_at,sector,display_name",
                "order": "symbol.asc",
                "limit": limit,
                "offset": offset
            }
        )
        if r.status_code != 200:
            print(f"오류: DB 로드 실패 - {r.text}")
            return 1
        
        chunk = r.json()
        if not chunk:
            break
        all_records.extend(chunk)
        offset += limit
        print(f"   - {len(all_records)}개 종목 로드 완료...")

    print(f"   => 총 {len(all_records)}개 종목 분석 및 정제 시작...")
    cleaned_rows = []
    
    # KIS 마스터 종목들 정제 및 display_name 맵핑
    for row in all_records:
        symbol = row["symbol"]
        raw_name = row["name"]
        
        # 'KR...' 접두사를 제거한 깨끗한 이름
        cleaned_name = clean_stock_name(raw_name)
        
        # 하드코딩 사전에 정의되어 있었던 테마(sector) 매핑
        curated_meta = SYMBOL_METADATA.get(symbol, {})
        sector = curated_meta.get("sector") or row.get("sector") or ""
        display_name = curated_meta.get("display_name") or cleaned_name
        
        cleaned_rows.append({
            "symbol": symbol,
            "name": cleaned_name,
            "display_name": display_name,
            "market_segment": row["market_segment"],
            "market_country": row["market_country"],
            "asset_type": row["asset_type"],
            "source": row["source"],
            "is_active": row["is_active"],
            "listed_at": row.get("listed_at"),
            "source_file_row": row.get("source_file_row") or {},
            "sector": sector
        })

    # 3. 하드코딩 SYMBOL_METADATA 내의 신규 종목 및 미국 주식 추가 이관
    print("\n3. symbol_metadata.py의 하드코딩 리스트 중 미등록/미국주식 이관 분석...")
    for symbol, meta in SYMBOL_METADATA.items():
        symbol_upper = symbol.upper()
        
        # 잘못된 코드인 461350은 진짜 코드인 462350으로 치환하여 이관
        if symbol_upper == "461350":
            symbol_upper = "462350"
            
        # 가상자산(CRYPTO)은 주식 마스터 테이블 제약조건(asset_type='STOCK') 위배를 방지하기 위해 제외
        if meta.get("asset_type") == "CRYPTO" or symbol_upper.endswith("USDT"):
            continue
            
        # 이미 로드된 종목 리스트에 존재하는지 체크
        exists = any(row["symbol"] == symbol_upper for row in cleaned_rows)
        
        # 이노스페이스 진짜 코드 (462350) 강제 주입
        if symbol_upper == "462350":
            exists = False
            
        if not exists:
            market_country = meta.get("market") or "KR"
            # 미국주식인 경우 시장구분을 적절히 부여
            market_segment = "NASDAQ" if market_country == "US" else "KOSDAQ"
            
            cleaned_rows.append({
                "symbol": symbol_upper,
                "name": meta.get("display_name"),
                "display_name": meta.get("display_name"),
                "market_segment": market_segment,
                "market_country": market_country,
                "asset_type": meta.get("asset_type", "STOCK"),
                "source": "KIS" if market_country == "KR" else "TOSS",
                "is_active": True,
                "listed_at": None,
                "source_file_row": {},
                "sector": meta.get("sector", "")
            })
            print(f"   - 신규 메타데이터 추가: {symbol_upper} ({meta.get('display_name')}) [국가:{market_country}]")

    # 4. DB에 일괄 업서트 (Batch Upsert)
    batch_size = 500
    headers_write = {
        **headers,
        "Prefer": "resolution=merge-duplicates,return=minimal"
    }

    print(f"\n4. DB에 총 {len(cleaned_rows)}개 종목 업서트 진행 중...")
    for i in range(0, len(cleaned_rows), batch_size):
        batch = cleaned_rows[i:i + batch_size]
        res = requests.post(
            f"{supabase_url}/rest/v1/kis_stock_master?on_conflict=symbol",
            headers=headers_write,
            json=batch
        )
        if res.status_code not in (200, 201, 204):
            print(f"오류: 배치 {i} ~ {i+batch_size} 업서트 실패 - {res.status_code} : {res.text}")
            return 1
        print(f"   - {i + len(batch)} / {len(cleaned_rows)} 업서트 완료...")

    print("\n🎉 데이터베이스 정제 및 마이그레이션이 성공적으로 완료되었습니다!")
    return 0

if __name__ == "__main__":
    sys.exit(main())

import os
import sys
import json
from dotenv import load_dotenv

# sys.path에 프로젝트 루트 및 backend 폴더 추가하여 모듈 임포트 가능하도록 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# backend/.env 로드
env_path = os.path.join(project_root, "backend", ".env")
load_dotenv(dotenv_path=env_path)

import requests
from backend.utils.crypto_helper import CryptoHelper
from backend.services.kis_client import KISClient

supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
encryption_key = os.getenv("ENCRYPTION_KEY", "")

headers = {
    "apikey": supabase_service_role_key,
    "Authorization": f"Bearer {supabase_service_role_key}",
    "Content-Type": "application/json",
}

user_id = "d4efb544-2a8a-443d-994d-9e7077eddbe7"

try:
    # 1. user_api_keys 테이블에서 사용자 KIS 키 목록 조회
    response = requests.get(
        f"{supabase_url}/rest/v1/user_api_keys?user_id=eq.{user_id}&exchange=eq.KIS",
        headers=headers,
        timeout=10,
    )
    if response.status_code != 200:
        print("Supabase Error:", response.text)
        sys.exit(1)
        
    keys_data = response.json()
    print(f"Found {len(keys_data)} KIS API Keys for user {user_id}\n")
    
    crypto = CryptoHelper(encryption_key)
    
    for row in keys_data:
        env = row.get("broker_env", "MOCK")
        enc_access = row.get("encrypted_access_key")
        enc_secret = row.get("encrypted_secret_key")
        cano = row.get("kis_account_no", "")
        acnt_prdt_cd = row.get("kis_account_code", "01")
        
        try:
            # 복호화 진행
            appkey = crypto.decrypt(enc_access)
            appsecret = crypto.decrypt(enc_secret)
            
            print(f"=== Querying KIS API [Env: {env}] ===")
            print(f"Account: {cano}-{acnt_prdt_cd}")
            
            # KISClient 초기화
            client = KISClient(
                appkey=appkey,
                appsecret=appsecret,
                cano=cano,
                acnt_prdt_cd=acnt_prdt_cd,
                env=env
            )
            
            # 잔고 조회 실행
            balance = client.get_balance()
            
            print(f"Total Evaluation: {balance.get('total_evaluation'):,.0f} KRW")
            print(f"Available Cash: {balance.get('available_cash'):,.0f} KRW")
            print("Holdings:")
            holdings = balance.get("holdings", [])
            if not holdings:
                print("  (No holdings found in this account)")
            for idx, h in enumerate(holdings):
                print(f"  [{idx+1}] Symbol: {h.get('symbol')} | Name: {h.get('name')} | Qty: {h.get('qty')} | Avg Price: {h.get('avg_price'):,.0f} | Current: {h.get('current_price'):,.0f}")
            print("-" * 60)
            
        except Exception as decrypt_or_api_error:
            print(f"Error for KIS Env {env}: {decrypt_or_api_error}")
            print("-" * 60)

except Exception as e:
    print("Main exception:", e)

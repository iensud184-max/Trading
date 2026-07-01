import os
import requests
from dotenv import load_dotenv

# backend/.env 파일 로드
env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
load_dotenv(dotenv_path=env_path)

supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

headers = {
    "apikey": supabase_service_role_key,
    "Authorization": f"Bearer {supabase_service_role_key}",
    "Content-Type": "application/json",
}

params = {
    "order": "created_at.asc",
    "select": "id,user_id,exchange,asset_type,ticker,symbol,side,price,volume,status,failure_reason,created_at,broker_env",
}

try:
    response = requests.get(
        f"{supabase_url}/rest/v1/trade_proposals",
        headers=headers,
        params=params,
        timeout=10,
    )
    if response.status_code == 200:
        data = response.json()
        hynix_records = [
            row for row in data 
            if "000660" in str(row.get("symbol") or "") or "000660" in str(row.get("ticker") or "")
        ]
        print(f"Total Hynix trade proposals found in DB: {len(hynix_records)}")
        print("-" * 90)
        for r in hynix_records:
            print(
                f"ID: {r.get('id')}\n"
                f"  Side: {r.get('side')} | Qty: {r.get('volume')} | Price: {r.get('price')}\n"
                f"  Status: {r.get('status')} | Env: {r.get('broker_env')}\n"
                f"  Created: {r.get('created_at')}\n"
                f"  Failure: {r.get('failure_reason')}\n"
                + "-" * 90
            )
    else:
        print("API Error:", response.status_code, response.text)
except Exception as e:
    print("Error querying database:", e)

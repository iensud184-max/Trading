import os
import requests
import json
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
load_dotenv(dotenv_path=env_path)

supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

headers = {
    "apikey": supabase_service_role_key,
    "Authorization": f"Bearer {supabase_service_role_key}",
    "Content-Type": "application/json",
}

proposal_id = "c10224fd-9631-4b19-bef0-2be30889c0dc"

try:
    response = requests.get(
        f"{supabase_url}/rest/v1/trade_proposals?id=eq.{proposal_id}",
        headers=headers,
        timeout=10,
    )
    if response.status_code == 200:
        data = response.json()
        if data:
            row = data[0]
            print("=== Proposal Details ===")
            for k, v in row.items():
                if k != "raw_order_payload":
                    print(f"{k}: {v}")
            print("\n=== Raw Order Payload ===")
            raw_payload = row.get("raw_order_payload")
            if isinstance(raw_payload, str):
                try:
                    raw_payload = json.loads(raw_payload)
                except Exception:
                    pass
            print(json.dumps(raw_payload, indent=2, ensure_ascii=False))
        else:
            print(f"No proposal found with ID: {proposal_id}")
    else:
        print("API Error:", response.status_code, response.text)
except Exception as e:
    print("Error querying database:", e)

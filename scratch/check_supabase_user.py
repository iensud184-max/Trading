import requests
import json
import os

SUPABASE_URL = "https://fdvhoaytcqnswuebocmr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZkdmhvYXl0Y3Fuc3d1ZWJvY21yIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MjA3MjM0MywiZXhwIjoyMDk3NjQ4MzQzfQ.8QzDGQRdGOXYkPa01ypRRrQRewX69ktckUw_si0I3yI"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def check_supabase():
    print("[CLI TEST] 실제 프로젝트 Supabase DB 조회 시작")
    
    # 1. Auth Admin API로 사용자 리스트 조회
    auth_url = f"{SUPABASE_URL}/auth/v1/admin/users"
    res = requests.get(auth_url, headers=headers)
    
    if res.status_code != 200:
        print(f"-> Auth API 조회 실패 ({res.status_code}): {res.text}")
        return
        
    users = res.json().get("users", [])
    target_user = None
    for u in users:
        if u.get("email") == "ka6865@naver.com":
            target_user = u
            break
            
    if not target_user:
        print("-> [결과] auth.users 테이블에서 'ka6865@naver.com' 사용자를 찾을 수 없습니다! (계정이 유실/삭제되었을 가능성 있음)")
        # 전체 등록된 이메일 리스트 출력해서 힌트 제공
        emails = [u.get("email") for u in users]
        print(f"-> 현재 가입된 전체 이메일 목록: {emails}")
        return
        
    user_id = target_user["id"]
    created_at = target_user["created_at"]
    print(f"-> [SUCCESS] auth.users 에 사용자 존재함!")
    print(f"   - User ID: {user_id}")
    print(f"   - 가입일시: {created_at}")
    
    # 2. profiles 테이블 조회
    profile_url = f"{SUPABASE_URL}/rest/v1/profiles"
    params = {"id": f"eq.{user_id}"}
    res_prof = requests.get(profile_url, headers=headers, params=params)
    if res_prof.status_code == 200 and res_prof.json():
        print(f"-> [SUCCESS] profiles 테이블에 데이터 존재함!")
        print(f"   - 프로필 내용: {json.dumps(res_prof.json(), ensure_ascii=False, indent=2)}")
    else:
        print(f"-> [WARNING] profiles 테이블에 데이터가 없습니다. (HTTP {res_prof.status_code}): {res_prof.text}")
        
    # 3. user_api_keys 테이블 조회
    keys_url = f"{SUPABASE_URL}/rest/v1/user_api_keys"
    params_keys = {"user_id": f"eq.{user_id}"}
    res_keys = requests.get(keys_url, headers=headers, params=params_keys)
    if res_keys.status_code == 200:
        keys_data = res_keys.json()
        if keys_data:
            print(f"-> [SUCCESS] user_api_keys 테이블에 API Key가 존재함! (개수: {len(keys_data)})")
            for k in keys_data:
                print(f"   - 거래소: {k.get('exchange')}, 환경: {k.get('broker_env')}, 등록시각: {k.get('created_at')}")
        else:
            print("-> [WARNING] user_api_keys 테이블에 등록된 API Key가 전혀 없습니다. (키가 지워졌거나 미등록 상태)")
    else:
        print(f"-> [ERROR] user_api_keys 조회 실패 (HTTP {res_keys.status_code}): {res_keys.text}")

if __name__ == "__main__":
    check_supabase()

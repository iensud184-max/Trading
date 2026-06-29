# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가하여 백엔드 모듈을 임포트할 수 있게 함
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "backend" / ".env")

from backend.services.toss_client import TossClient

def main():
    client_id = os.getenv("TOSS_API_KEY")
    client_secret = os.getenv("TOSS_SECRET_KEY")

    if not client_id or not client_secret:
        print("오류: 토스증권 API 키가 .env 파일에 설정되어 있지 않습니다.")
        return

    # TossClient 초기화 (실거래용 REAL 또는 MOCK)
    # env를 'REAL'로 설정하여 실거래 Open API 시세를 테스트해봅니다.
    print(f"TossClient 초기화 진행 (TOSS_API_KEY={client_id[:10]}...)")
    import requests
    client = TossClient(client_id=client_id, client_secret=client_secret, env="REAL")
    # 토큰은 클라이언트의 캐시/재발급 로직을 그대로 사용한다.
    # 이렇게 해야 실제 서비스에서 쓰는 경로와 같은 조건으로 테스트할 수 있다.
    token = client.get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    url = "https://openapi.tossinvest.com/api/v1/prices"

    for cand in ["461350", "A461350"]:
        print(f"\n후보 [{cand}] 직접 API 호출...")
        for param_name in ["symbol", "symbols"]:
            try:
                res = requests.get(url, headers=headers, params={param_name: cand}, timeout=10)
                print(f"[{param_name}={cand}] HTTP {res.status_code}")
                print(f"응답 바디: {res.text}")
            except Exception as e:
                print(f"에러: {e}")

if __name__ == "__main__":
    main()

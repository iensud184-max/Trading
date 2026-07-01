import sys
import os
import time

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.toss_client import TossClient, TOSS_LIMITS

def test_rate_limiter():
    print("[TEST] Toss Client Rate Limiter & Circuit Breaker 검증을 시작합니다.")
    
    # Mocking TossClient
    client = TossClient(
        client_id="mock_id",
        client_secret="mock_secret",
        account_seq="1",
        env="MOCK"
    )
    
    # 1. 초기 한도 상태 설정 (Remaining이 1로 떨어진 상태 시뮬레이션 -> Self-Throttling 유도)
    TOSS_LIMITS["MARKET_DATA"] = {
        "remaining": 1,
        "reset": time.time() + 0.3,
        "blocked_until": 0.0,
        "limit": 10
    }
    
    print("\n1) Self-Throttling 테스트: remaining이 1일 때 딜레이(Throttling)가 적용되는지 측정합니다.")
    start_t = time.time()
    try:
        # 가상의 URL로 GET 요청
        res = client._send_request("GET", "https://openapi.tossinvest.com/api/v1/prices?symbol=005930")
        elapsed = time.time() - start_t
        print(f"-> 요청 성공! 소요 시간: {elapsed:.3f}초 (Self-Throttling 대기가 잘 작동했는지 여부: {elapsed >= 0.1})")
    except Exception as e:
        elapsed = time.time() - start_t
        print(f"-> 에러 발생 (소요시간: {elapsed:.3f}초): {e}")

    # 2. 서킷 브레이커 테스트 (blocked_until이 미래인 경우 강제 차단되는지)
    print("\n2) 서킷 브레이커 테스트: blocked_until이 미래일 때 즉시 차단(Circuit Break) 에러를 뿜는지 확인합니다.")
    TOSS_LIMITS["MARKET_DATA"] = {
        "remaining": 0,
        "reset": time.time() + 10.0,
        "blocked_until": time.time() + 5.0, # 5초간 차단
        "limit": 10
    }
    
    try:
        client._send_request("GET", "https://openapi.tossinvest.com/api/v1/prices?symbol=005930")
        print("-> [FAIL] 서킷 브레이커가 작동하지 않고 통과해 버렸습니다.")
    except Exception as e:
        if "Circuit Breaker active" in str(e):
            print(f"-> [SUCCESS] 기대했던 서킷 브레이커 차단 에러 발생: {e}")
        else:
            print(f"-> 다른 에러 발생: {e}")

    print("\n[TEST END] 모든 로컬 알고리즘 검증이 완료되었습니다.")

if __name__ == "__main__":
    test_rate_limiter()

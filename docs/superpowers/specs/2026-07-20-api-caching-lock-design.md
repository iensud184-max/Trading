# API 호출 부하 감소 및 토큰 갱신 병목 극복을 위한 설계서 (2026-07-20-api-caching-lock-design.md)

본 문서는 Toss증권, KIS(한국투자증권), 코인원, 바이낸스 등 연동 거래소 및 Supabase 데이터베이스와의 통신 과정에서 발생하는 호출 제한(Rate Limit)을 억제하고 인증 세션 충돌을 방지하기 위한 통합 캐싱 및 분산 락 연동 사양을 정의합니다.

---

## 1. 배경 및 개선 목적

1.  **Supabase DB 및 복호화 부하**: 디테일 페이지(AssetDetail) 로딩 시 여러 API(잔고, 보유수량, 주문가능수량 등)가 동시에 병렬 호출되면서 `user_api_keys` 테이블에 대한 중복 조회와 AES-256-GCM 복호화 연산이 발생합니다.
2.  **토큰 갱신 충돌 (TossClient 무방비)**: KISClient에는 토큰 갱신 시 `distributed_lock`이 연동되어 있으나, TossClient에는 분산 락이 없어 병렬 요청이 들어올 때 Toss API 측으로 토큰 갱신 요청이 중복으로 날아가 세션이 깨지거나 Rate Limit이 초과되는 상태입니다.
3.  **시스템-사용자 동일 키 간섭**: 1인 개발/소규모 테스트 환경에서는 시스템 환경변수(`.env`)의 공용 키와 개별 사용자가 등록한 키가 동일하여 호출 제한 카운트를 공유해 간섭이 발생합니다.
4.  **목적**: `CredentialsGateway` 싱글톤 서비스를 도입하여 In-Memory 2차 캐시를 적용하고, TossClient에 분산 락을 결합하며, 동일 키 감지 시 세션을 하나로 매핑하여 호출 실패율을 0%에 수렴하게 합니다.

---

## 2. 세부 설계 사양

### 2.1 CredentialsGateway 싱글톤 설계 (In-Memory Cache)
*   **역할**: API 키 복호화본 및 관련 계좌 정보를 임시 메모리에 적재하여 중복 조회를 차단하는 게이트웨이 서비스입니다.
*   **저장 구조**: 
    *   캐시 키: `(user_id, exchange, broker_env)` 튜플
    *   기본 TTL(Time-To-Live): 60초
*   **동일 키 매핑 처리**:
    *   사용자 키를 로딩했을 때, 그 값이 시스템 `.env`에 정의된 `TOSS_API_KEY` 또는 `KIS_APPKEY`와 물리적으로 동일하면, 캐시 키와 락 키의 소유 주체를 공용 명칭(`system_toss`, `system_kis`)으로 강제 통합 맵핑합니다.
    *   이를 통해 백그라운드 스케줄러(뉴스/시세 동기화 등)와 실시간 사용자 요청이 동일한 캐시/세션 토큰을 참조하도록 일원화합니다.
*   **캐시 무효화(Invalidation)**:
    *   키 관리 라우트(`/api/keys`)에서 수정/삭제 발생 시 `invalidate_cache(user_id, exchange, broker_env)`를 즉시 호출하여 정합성을 보장합니다.

### 2.2 TossClient 분산 락(Distributed Lock) 도입
*   **역할**: KISClient의 방어벽 설계를 적용하여, Toss 토큰 만료 또는 누락 시 여러 스레드가 동시에 토큰 재발급 API를 때리는 병목을 방지합니다.
*   **로직**:
    *   토큰 발급 직전 `lock_key = f"toss-token:{self.env}:{self.user_id or 'anonymous'}"` 분산 락을 획득합니다.
    *   락을 선점하지 못한 스레드는 `time.sleep(0.5)` 대기 후 캐시 테이블(`token_caches`)에 선점 스레드가 새로 적재해 둔 토큰을 안전하게 재사용합니다.

---

## 3. 리팩토링 및 구현 타겟

*   **[NEW] `backend/services/credentials_gateway.py`**: 캐싱 및 동일 키 감지 감화용 싱글톤 서비스 구현.
*   **[MODIFY] `backend/services/toss_client.py`**: `_get_cached_token` 메소드 내에 `distributed_lock` 및 0.5초 대기 재조회 로직 추가.
*   **[MODIFY] `backend/routes/trade.py`**: `_load_user_exchange_record` 등 사용자 API 키 접근 구조를 `CredentialsGateway` 방식으로 위임.
*   **[MODIFY] `backend/routes/home.py`**: 대시보드 잔고 융합 헬퍼에서 `CredentialsGateway`를 통과하도록 구조 리팩토링.
*   **[MODIFY] `backend/services/chatbot/tool_registry.py`**: 챗봇 툴 내부에서 `user_api_keys`를 직접 쿼리하는 부하 영역을 `CredentialsGateway`로 전환.

---

## 4. 검증 계획

### 4.1 정적 분석 및 컴파일 검증
*   리팩토링 후 수정 대상 파이썬 파일들이 구문 에러 없이 빌드되는지 검사합니다:
    ```bash
    python -m py_compile backend/services/credentials_gateway.py backend/services/toss_client.py backend/routes/trade.py backend/routes/home.py backend/services/chatbot/tool_registry.py
    ```

### 4.2 단위 테스트 (Pytest)
*   캐시 히트(Hit) 상태에서 Supabase API 쿼리가 중복으로 발생하지 않는지 검증하는 Mocking 테스트 코드 추가.
*   TossClient에서 복수의 스레드가 경쟁적으로 토큰을 요구할 때 분산 락이 1회만 갱신을 허용하는지 검증하는 멀티스레드 동시성 테스트 수행.

### 4.3 통합 빌드 검증
*   프론트엔드 정적 빌드 체크: `npm run build` 성공 여부 검사.

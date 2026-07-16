# 챗봇 시나리오 통합 성능 진단 스크립트 설계서

본 문서는 최근 리팩토링된 챗봇의 도구(Tool) 호출 및 한국어 종목 인식 정확도를 정량적으로 검증하고 지속적으로 관리하기 위한 시나리오 기반 통합 성능 진단 스크립트의 상세 설계서입니다.

---

## 1. 개요 및 목적
* **목적**: OpenAI Function Calling 기반 챗봇의 자연어 의도 분석, 파라미터 매핑(`**arguments` 바인딩) 및 종목 심볼 명칭 정규화 로직이 런타임 환경에서 의도대로 수행되는지 정량적으로 검증합니다.
* **범위**: 수동 주문 사전검증 하위 호환성 핫픽스가 적용된 백엔드 라우터 및 챗봇 서비스 내부 도구 호출 파이프라인.

---

## 2. 테스트 시나리오 정의 (Test Scenarios)
각 핵심 시나리오는 실제 사용자 발화(Input)로부터 기대되는 도구 호출과 핵심 인자값(Expected Output)을 정의하여 검증합니다.

| 번호 | 검증 대상 시나리오 | 사용자 발화 예시 (Input) | 기대 도구 및 핵심 인자 (Expected Output) |
| :--- | :--- | :--- | :--- |
| **1** | 가상자산 시세 및 기본 거래소 매핑 | "비트코인 현재가 얼마야?" | `get_asset_price(query="BTC", exchange="COINONE")` |
| **2** | 주식 시세 및 기본 거래소 매핑 | "삼성전자 현재가 알려줘" | `get_asset_price(query="삼성전자", exchange="TOSS")` |
| **3** | 특정 간격 캔들 조회 및 조사 탈락 | "리플 1시간 봉 캔들 흐름 보여줘" | `get_asset_candles(query="XRP", exchange="COINONE", interval="1h")` |
| **4** | 종합 분석 도구 경계 선택 및 자동 감지 | "이더리움 단타 진입 타이밍 봐줘" | `get_crypto_market_context(query="ETH", exchange="COINONE", interval="1h")` |
| **5** | 특정 거래소 보유자산 조회 | "내 보유 코인 잔고 보여줘" | `get_holdings(exchange="COINONE")` |
| **6** | 뉴스 RAG 및 장기 전망 도구 분기 | "현대차 관련 최근 소식 분석해줘" | `get_asset_outlook(query="현대차")` |
| **7** | 관심종목 추가 데이터 바인딩 | "솔라나 관심종목에 넣어줘" | `add_watchlist_item(query="SOL")` |

---

## 3. 아키텍처 및 구현 설계 (Architecture)

### 3.1 스크립트 구동 환경
* **구동 위치**: `backend/scripts/run_chatbot_scenario_test.py`
* **의존성**: Flask Application Context 및 `.env` 파일의 환경변수를 그대로 로드하여 실제 API 자격증명 하에서 실행.

### 3.2 테스트 인터셉터 (Interceptor)
테스트 실행 시 `ChatbotService`의 도구 실행 직전 단계인 `_run_llm_tool_call` 또는 `_tool_message_from_arguments` 에 래퍼 함수를 적용하여 LLM이 채워낸 **도구 명칭(tool_name)**과 **매개변수(arguments)**를 외부 스크립트 측에서 안전하게 추출합니다.

```python
# 캡처 래퍼 예시
captured_calls = []

def make_interceptor(original_func):
    def wrapper(auth_header, tool_call, fallback_text):
        tool_name = tool_call.get("function", {}).get("name")
        arguments = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
        captured_calls.append({
            "tool_name": tool_name,
            "arguments": arguments
        })
        return original_func(auth_header, tool_call, fallback_text)
    return wrapper
```

---

## 4. 검증 메트릭 및 결과 포맷 (Metrics)

### 4.1 성공 판정 기준 (Success Criteria)
* **Tool Match**: 의도한 함수가 정상 호출되었는지 여부.
* **Args Match**: 필수 파라미터(`exchange`, `interval` 등)가 훼손 없이 매핑되었는지 여부.
* **Symbol Match**: 조사 탈락 필터를 거쳐 올바른 canonical 심볼명으로 복원 및 변환되었는지 여부.

### 4.2 결과 출력 및 기록 포맷
모든 시나리오 수행이 완료되면 터미널 상에 Pass/Fail 여부와 성공률(Success Rate %)을 렌더링하고, 검증 타임스탬프와 함께 결과를 기록합니다.

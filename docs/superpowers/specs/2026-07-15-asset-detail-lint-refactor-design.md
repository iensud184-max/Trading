# Asset Detail Lint Refactor Design

## 목적

`AssetDetail.jsx`와 `MobileAssetDetail.jsx`는 각각 5천 줄 이상이며, 현재 프론트엔드 lint warning이 각 16개씩 남아 있다. 첫 리팩토링 사이클의 목적은 기능을 바꾸지 않고 두 상세 페이지의 공통 순수 로직을 분리해 파일 크기와 중복을 줄이고, 해당 파일군의 명확한 lint warning을 우선 제거하는 것이다.

## 현재 기준

- 전체 lint 상태: `0 errors`, `122 warnings`
- 최우선 대상:
  - `frontend/src/pages/AssetDetail.jsx`: 5029줄, 16 warnings
  - `frontend/src/pages/mobile/MobileAssetDetail.jsx`: 5017줄, 16 warnings
- 주요 warning:
  - `no-unused-vars`
  - `no-empty`
  - `no-useless-assignment`
  - `react-hooks/exhaustive-deps`

## 범위

이번 사이클은 `AssetDetail` 계열에 한정한다.

- 공통 상수와 순수 함수를 `frontend/src/pages/assetDetailModel.js`로 추출한다.
- 데스크톱/모바일 상세 페이지에서 동일하게 쓰는 라벨 변환, 상태 판별, 종목 심볼 정규화, 가격 포맷 보조 로직을 우선 분리한다.
- `no-unused-vars`, `no-empty`, `no-useless-assignment`는 동작 영향이 작으므로 이번 사이클에서 제거한다.
- `react-hooks/exhaustive-deps`는 stale closure 위험을 확인하면서 처리한다. 단순 의존성 추가가 네트워크 재호출 루프를 만들 수 있는 경우에는 이번 사이클에서 억지로 고치지 않고 원인과 후속 작업으로 문서화한다.

## 제외 범위

- `backend/routes/trade.py` 분할은 다음 사이클로 미룬다.
- `Dashboard.jsx`와 `MobileDashboardPage.jsx` 리팩토링은 다음 프론트 사이클로 미룬다.
- UI 구조, 주문 정책, API 계약, Supabase 스키마는 변경하지 않는다.
- lint 규칙을 더 느슨하게 낮추는 방식으로 warning을 숨기지 않는다.

## 설계

### 공통 모델 파일

`frontend/src/pages/assetDetailModel.js`를 추가한다.

이 파일은 React state, router, DOM, Supabase에 의존하지 않는 순수 함수와 상수만 가진다.

초기 추출 대상:

- `ACTIONABLE_ORDER_STATUSES`
- `STOCK_WARNING_BADGE_META`
- `isActionableOrderStatus(status)`
- `isCancelReplaceExchange(exchange)`
- `getStockWarningBadgeTone(warningType)`
- `getOrderStatusLabel(status)`
- `getOrderSideLabel(side)`
- `getAutoRuleStatusLabel(status)`
- `getAutoExecutionModeLabel(mode)`
- `getAutoTriggerLabel(triggerSide)`
- `normalizeStockSymbol(value)`
- `isDomesticStockSymbol(value)`
- `isUsStockSymbol(value, market)`

데스크톱과 모바일의 `isDomesticStockSymbol` 구현이 현재 다르므로 실제 의도 확인이 필요하다. 첫 사이클에서는 기존 동작 보존을 우선하여 모바일 전용 차이가 필요한지 테스트로 고정한 뒤 합칠 수 있는 범위만 합친다.

### 테스트

`frontend/src/pages/assetDetailModel.test.mjs`를 추가한다.

테스트는 다음을 고정한다.

- 주문 상태 라벨 변환
- 자동매매 규칙 상태 라벨 변환
- 매수/매도 라벨 변환
- 국내/미국 주식 심볼 판별
- 취소/정정 지원 거래소 판별
- 주식 경고 배지 fallback

테스트는 Node 내장 test runner를 사용한다.

### lint 처리

명확한 dead code는 제거한다.

- 쓰지 않는 변수와 import 제거
- 빈 `catch` 또는 빈 블록 정리
- 마지막 대입값이 사용되지 않는 변수 정리

hook dependency warning은 각 effect의 네트워크 호출, chart lifecycle, subscription cleanup 여부를 보고 처리한다. 자동 수정으로 동작이 바뀔 가능성이 있으면 이번 사이클에서는 남은 warning 목록을 문서화한다.

## 검증

필수 검증 명령:

```bash
node --test frontend/src/pages/assetDetailModel.test.mjs
npm run lint
npm run build
python3 -m pytest -q
```

기대 결과:

- 새 모델 테스트 통과
- lint error 0 유지
- 전체 warning 수는 감소해야 한다.
- build 성공
- backend pytest 성공

## 문서 최신화

구현 완료 후 다음 문서를 실제 결과 기준으로 갱신한다.

- `project_structure.md`: 새 `assetDetailModel.js`와 테스트 파일 반영
- 필요 시 `README.md` 또는 QA 문서: lint warning 현황과 후속 리팩토링 순서 반영

## 후속 사이클 후보

1. `Dashboard.jsx` / `MobileDashboardPage.jsx` 공통 로직 분리
2. `backend/routes/trade.py` 주문/조회/자동감시 라우트 단위 분할
3. `backend/services/chatbot/tool_registry.py` 도구 카테고리별 모듈화
4. `AdminMlData.jsx` / `MobileAdminMlData.jsx` 공통 컴포넌트 분리

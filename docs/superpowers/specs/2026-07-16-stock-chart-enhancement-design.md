# 주식 및 가상자산 차트 고도화 설계서 (stock-chart-enhancement-design)

본 문서는 트레이딩 시스템 내 차트의 정보 인지성을 높이고 사용자 거래 경험을 최적화하기 위해, 기존 `lightweight-charts (v5.2.0)` 기반 차트를 고도화하기 위한 아키텍처 및 세부 설계 사양을 정의합니다.

---

## 1. 개요 및 배경
현재 서비스의 상세 화면([AssetDetail.jsx](file:///Users/kangheesung/10-19_%EA%B0%9C%EB%B0%9C/13_%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/13.05_%E1%84%90%E1%85%B3%E1%84%85%E1%85%A6%E1%84%8B%E1%85%B5%E1%84%83%E1%85%B5%E1%86%BC/teamproject/frontend/src/pages/AssetDetail.jsx))은 기본적인 봉(캔들) 차트만을 단독으로 보여주고 있습니다. 이는 주식/코인 투자자들이 기술적 분석 및 투자 판단을 내리는 데 필요한 핵심 데이터(거래량, 이동평균선, 과거 거래 지점 등)가 부족하여 다음과 같은 고도화를 진행합니다.

---

## 2. 핵심 목표 (Goals)
1. **기술적 분석 지원**: 가격 이동평균선(MA) 및 거래량(Volume) 정보를 추가하여 시장 추세와 유동성을 파악하도록 지원.
2. **거래 정보 시각화**: 사용자의 과거 실제 체결 이력(BUY/SELL)을 차트 위에 마커(Marker)로 매핑하여 직관적인 투자 복기 유도.
3. **인터랙션(UX) 고도화**: 마우스 호버(Crosshair Move) 시 캔들의 정밀한 수치(OHLCV)를 화면 상단 레전드에 지연 없이 출력.
4. **최적의 레이아웃**: 대시보드 화면 크기(컴팩트 뷰 vs 크게보기)에 따라 차트 구성 요소를 유연하게 전환하는 하이브리드 레이아웃 구현.

---

## 3. UI/UX 및 아키텍처 설계

### 3.1 하이브리드 동적 레이아웃 (3안 채택)
* **컴팩트 차트 모드 (기본 뷰)**
  * **목적**: 대시보드 내 한정된 세로 공간 절약 및 고밀도 정보 노출.
  * **구조**: 단일 차트 캔버스 구조. 거래량(Volume)은 가격 캔들스틱 차트 영역 하단 20% 공간에 반투명 막대로 겹쳐서 표시(Overlay).
  * **옵션**: `priceScaleId: ''` (Overlay 모드), `scaleMargins: { top: 0.8, bottom: 0 }`.
* **크게보기 모드 (전체화면 팝업)**
  * **목적**: 전문 HTS급 화면 분할 및 고정밀 분석 환경 제공.
  * **구조**: 차트 영역이 2개의 패널(Pane)로 상/하 분할됨. 
    * 상단 패널 (Pane 0 - 75% 비중): 가격 캔들스틱, 이동평균선, 매매 마커.
    * 하단 패널 (Pane 1 - 25% 비중): 독립된 거래량 막대그래프 단독 노출.
  * **옵션**: 거래량 생성 시 `paneIndex: 1` 설정.

### 3.2 이동평균선(SMA) 오버레이
* **구간 정의**: 주식/코인 시장에서 가장 흔히 탐색되는 5일선(단기), 20일선(중기 생명선), 60일선(장기 수급선) 제공.
* **계산 로직**: 프론트엔드가 수신한 캔들 배열을 루프 돌며 단순 이동평균(Simple Moving Average)을 실시간 산출.
* **디자인 및 색상**: 
  * 5일선: 황금색 (`#ffd700`, lineWidth: 1.5)
  * 20일선: 보라색 (`#a855f7`, lineWidth: 1.5)
  * 60일선: 민트색 (`#06b6d4`, lineWidth: 1.5)
  * *Semantic 컬러(상승 초록 `#ef4444`, 하락 파랑 `#3b82f6`)와의 혼동을 엄격하게 금지하기 위한 색상 스킴 채택.*

### 3.3 실시간 호버 레전드 & MagnetOHLC
* **UI 레이아웃**: [assetDetailChartPanel.jsx](file:///Users/kangheesung/10-19_%EA%B0%9C%EB%B0%9C/13_%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/13.05_%E1%84%90%E1%85%B3%E1%84%85%E1%85%A6%E1%84%8B%E1%85%B5%E1%84%83%E1%85%B5%E1%86%BC/teamproject/frontend/src/pages/assetDetailChartPanel.jsx) 컴포넌트 내부 차트 컨테이너의 좌측 상단 영역에 절대 위치(Absolute Position)로 정렬된 텍스트 판넬 배치.
* **동작 매커니즘**:
  1. `chart.subscribeCrosshairMove((param) => { ... })` 구독.
  2. 마우스 커서 아래에 유효한 캔들 데이터가 존재하면 해당 시점의 `Open`, `High`, `Low`, `Close`, `Volume` 수치를 React 상태값에 바인딩하여 레전드에 즉시 표기.
  3. 전일 종가 대비 당일 종가 등락률 `((Close - PrevClose) / PrevClose) * 100`을 계산하여 함께 표시 (상승 시 success-green, 하락 시 danger-red 색상 매칭).
  4. 마우스가 차트 밖으로 이탈하면 가장 최근(마지막) 캔들의 시세 수치로 자동 원복 처리.
* **착붙 모드**: `CrosshairMode.MagnetOHLC`를 차트 크로스헤어 옵션에 적용하여, 마우스 이동 시 캔들의 실시간 시세 접점에 크로스헤어 가로선이 자석처럼 부착되도록 구현.

### 3.4 체결 마커 (Trading Markers) 연동
* **데이터 수집**: Supabase의 `trade_proposals` 테이블에서 로그인한 현재 사용자의 계정 ID 기준으로 필터링하여 해당 종목(`symbol` 및 `exchange`)의 체결 완료 주문(`status = 'EXECUTED'`) 정보를 프론트엔드가 수신.
* **마커 생성 및 맵핑**:
  * 각 주문의 체결 시점(`executed_at`)의 Unix timestamp와 일치하는 차트 캔들 좌표를 식별.
  * **매수(BUY)**: 캔들 하단(`position: 'belowBar'`)에 초록색 위쪽 화살표(`shape: 'arrowUp'`, color: `#10b981`) 및 **"BUY"** 텍스트 라벨 출력.
  * **매도(SELL)**: 캔들 상단(`position: 'aboveBar'`)에 빨간색 아래쪽 화살표(`shape: 'arrowDown'`, color: `#ef4444`) 및 **"SELL"** 텍스트 라벨 출력.

---

## 4. 데이터 및 백엔드 설계

### 4.1 캔들 API 거래량(Volume) 정제
* **대상 라우트**: Flask 백엔드의 차트 캔들 서빙 API (`/api/chart/candles`).
* **데이터 무결성 확보**:
  * [toss_client.py](file:///Users/kangheesung/10-19_%EA%B0%9C%EB%B0%9C/13_%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/13.05_%E1%84%90%E1%85%B3%E1%84%85%E1%85%A6%E1%84%8B%E1%85%B5%E1%84%83%E1%85%B5%E1%86%BC/teamproject/backend/services/toss_client.py), [coinone_client.py](file:///Users/kangheesung/10-19_%EA%B0%9C%EB%B0%9C/13_%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/13.05_%E1%84%90%E1%85%B3%E1%84%85%E1%85%A6%E1%84%8B%E1%85%B5%E1%84%83%E1%85%B5%E1%86%BC/teamproject/backend/services/coinone_client.py), [binance_client.py](file:///Users/kangheesung/10-19_%EA%B0%9C%EB%B0%9C/13_%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/13.05_%E1%84%90%E1%85%B3%E1%84%85%E1%85%A6%E1%84%8B%E1%85%B5%E1%84%83%E1%85%B5%E1%86%BC/teamproject/backend/services/binance_client.py)에서 개별 원시 캔들 데이터 수집 시 거래량(`volume` 또는 `qty`)을 실수형(Float)으로 정제하여 누락 없이 포함하도록 응답 JSON 규격을 공통화.
  * 거래소 리턴값 중 volume 데이터가 누락되거나 Null인 경우, 프론트엔드 오류를 차단하기 위해 `0`으로 백엔드 서비스 레이어에서 강제 변환 후 전송.

### 4.2 글로벌 타임스탬프(Unix Epoch) 통일
* 차트 가격 데이터의 `time` 속성과 체결 완료 이력의 `executed_at` 시각을 모두 **초 단위 Unix Timestamp(integer)**로 통일하여 매핑 오차를 차단.
* 차트 라이브러리 내 localization 포맷터를 사용하여 브라우저가 위치한 현지 기준(ko-KR)의 타임존(UTC+9)으로 날짜와 시각을 파싱하도록 제어.

---

## 5. 성능 및 리스크 제어

### 5.1 추가 트래픽 최소화 (YAGNI 및 제로 추가 요청)
* 거래량 렌더링에 필요한 정보는 기존 캔들 조회 API 응답 데이터셋에 포함되어 있는 값을 활용하므로, 추가적인 백엔드 네트워크 요청 비용은 **0회**입니다.
* 이동평균선(SMA) 역시 백엔드가 아닌 클라이언트의 브라우저에서 최초 로드 시 한 번만 계산하므로 CPU/메모리 부하가 최소화됩니다.

### 5.2 Supabase 인덱싱 최적화
* 매매 마커 조회를 위해 사용되는 `trade_proposals` 테이블의 `exchange`, `symbol`, `status` 복합 인덱스(Composite Index) 튜닝 여부를 검토하여 대량의 주문 이력이 쌓인 경우에도 지연 없는 렌더링을 보장합니다.

---

## 6. 예외 시나리오 및 대응 (Edge Cases)

| 예외 상황 | 대응 방식 |
| :--- | :--- |
| **신규 가상자산 등 거래 이력이 전무한 종목** | Supabase 쿼리 결과가 빈 배열이므로 차트에 어떠한 마커도 그리지 않고 예외 발생 없이 조용히 무시함. |
| **사용자가 캔들 인터벌(예: 1분봉 -> 일봉)을 변경한 경우** | 인터벌 변경 시 마커 좌표도 바뀐 타임라인에 맞추어 새로 렌더링되도록 차트 초기화 함수와 연계하여 동기화함. |
| **마우스가 차트 영역을 바깥으로 이탈할 때** | 크로스헤어 무브 리스너에서 이탈을 감지하여 실시간 레전드 값을 실시간 체결가와 최신 봉 데이터로 초기화함. |

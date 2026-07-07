# Task 9: 관리자 ML 버튼 3분리 Preset 노출 보고서

## 1. 작업 개요
본 작업은 3분리 ML 자동화 개발 계획 중 **'Task 9: 관리자 ML 버튼 3분리 preset 노출'** 단계에 해당합니다. 관리자 ML 데이터 페이지(`AdminMlData.jsx`)에서 국내 및 해외 주식에 대한 분리 수집+학습 프리셋을 추가하고, 노출 필터 및 관련 비동기 데이터 동기화 코드를 정비하였습니다.

---

## 2. 상세 작업 내역

### 1) 프리셋 추가 (`automationPresets`)
- `kr-stock-v1-full` (국내 주식 v1 자동 수집+학습 (분리))과 `us-stock-v1-full` (미국 주식 v1 자동 수집+학습 (분리)) 두 프리셋 엔트리를 `automationPresets` 배열 상수에 추가하였습니다.
- 설정값: `key`, `label`, `summary`, `version: "split-v1"`, `isNew: true`.

```javascript
  {
    key: 'kr-stock-v1-full',
    label: '국내 주식 v1 자동 수집+학습 (분리)',
    summary: '국내 주식 3분리 자동 수집 후 학습까지 한 번에 실행',
    version: 'split-v1',
    isNew: true,
  },
  {
    key: 'us-stock-v1-full',
    label: '미국 주식 v1 자동 수집+학습 (분리)',
    summary: '미국 주식 3분리 자동 수집 후 학습까지 한 번에 실행',
    version: 'split-v1',
    isNew: true,
  },
```

### 2) 운영 프리셋 필터링 확장 (`operationalAutomationPresets`)
- 기존 `v8` 버전만 노출하도록 정의되어 있던 필터를 수정하여, `v8`과 `split-v1` 버전 둘 다 노출하도록 변경하였습니다.

```javascript
const operationalAutomationPresets = automationPresets.filter((preset) => preset.version === 'v8' || preset.version === 'split-v1')
```

### 3) 시그널 동기화 주석 추가 (`handleRunFullAutomation`)
- `handleRunFullAutomation` 내에서 `loadActiveSignals`를 호출하기 직전에, 국내/해외 분리 모델의 레지스트리 자산 타입에 대한 정책 주석을 삽입하였습니다.

```javascript
      // 국내/해외 분리 모델도 현재 registry asset_type은 STOCK으로 동기화합니다.
      await loadActiveSignals(preset.key.includes('crypto') ? 'CRYPTO' : 'STOCK')
```

---

## 3. 검증 결과 (`npm run build`)
프론트엔드 코드의 구문 오류 및 렌더링에 문제가 없는지 확인하기 위해 `frontend` 디렉토리 내에서 `npm run build`를 실행하여 빌드가 오류 없이 통과하는지 검증하였습니다.

### 빌드 로그
```bash
> frontend@0.0.0 build
> vite build

vite v8.0.16 building client environment for production...
transforming...✓ 94 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.62 kB │ gzip:   0.40 kB
dist/assets/index-BpdwPL-b.css    100.53 kB │ gzip:  15.78 kB
dist/assets/index-C7jGi39z.js   1,058.08 kB │ gzip: 284.03 kB

✓ built in 287ms
```

- 빌드가 **성공(exit 0)** 하였으며, 어떠한 컴파일이나 타입 에러도 발생하지 않았습니다.

---

## 4. 최종 상태 및 후속 조치
- **상태 (Status)**: `DONE`
- **커밋 ID (Commit ID)**: `9bbdbf4` (UI 버그 픽스 및 프리셋 레이블 수정 커밋)
- **빌드 성공 여부**: **성공**

---

## 5. 버그 픽스 및 재검증 내역 (Rejected 판정 조치)

### 1) 프리셋 레이블 및 요약 텍스트 정정
- `kr-stock-v1-full` 프리셋
  - `label`: '국내주식 v1 자동 수집+학습'
  - `summary`: 'stock_kr_core_45 + DART 공시 피처를 포함한 국내주식 shadow 모델'
- `us-stock-v1-full` 프리셋
  - `label`: '해외주식 v1 자동 수집+학습'
  - `summary`: 'stock_us_core_45 기반 해외주식 shadow 모델. DART 피처는 제외합니다.'

### 2) 중복 노출 UI 버그 수정
- `legacyAutomationPresets`와 `operationalAutomationPresets` 필터 정의를 수정하여 `split-v1` 버전 프리셋들이 `legacy` 영역에 중복 노출되지 않고 `operational` 영역에만 한 번만 렌더링되도록 수정하였습니다.
  - `legacyAutomationPresets`: `split-v1` 버전도 제외되도록 수정 (`!['v8', 'split-v1'].includes(preset.version)`)
  - `operationalAutomationPresets`: `split-v1` 버전도 포함되도록 수정 (`['v8', 'split-v1'].includes(preset.version)`)

### 3) 빌드 검증 결과 (`npm run build`)
`frontend` 디렉토리에서 `npm run build`를 실행하여 픽스 작업 후에도 빌드가 정상적으로 완료됨을 확인하였습니다.
```bash
vite v8.0.16 building client environment for production...
transforming...✓ 94 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.62 kB │ gzip:   0.40 kB
dist/assets/index-BpdwPL-b.css    100.53 kB │ gzip:  15.78 kB
dist/assets/index-DXqv72t3.js   1,058.10 kB │ gzip: 284.06 kB

✓ built in 320ms
```
빌드가 정상적으로 수행되어 어떠한 에러도 발생하지 않았습니다.

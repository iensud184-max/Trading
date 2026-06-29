ALTER TABLE public.market_indices_latest
    -- 새 스냅샷 포맷을 저장할 컬럼을 추가하고, 기존 데이터는 그대로 둔다.
    -- 테이블 구조를 바꿔도 기존 응답이 바로 깨지지 않도록 점진적으로 확장한다.
    ADD COLUMN IF NOT EXISTS current_price NUMERIC,
    ADD COLUMN IF NOT EXISTS previous_close NUMERIC,
    ADD COLUMN IF NOT EXISTS change_price NUMERIC,
    ADD COLUMN IF NOT EXISTS change_rate NUMERIC,
    ADD COLUMN IF NOT EXISTS synced_at TIMESTAMPTZ;

-- 기존 데이터는 이전 컬럼에서 새 컬럼으로 한 번만 채워 넣는다.
-- 마이그레이션 직후 API가 새 필드와 구 필드를 함께 읽을 수 있게 만드는 보정 단계다.
UPDATE public.market_indices_latest
SET
    current_price = COALESCE(current_price, current_value),
    previous_close = COALESCE(previous_close, current_value - change_value),
    change_price = COALESCE(change_price, change_value),
    change_rate = COALESCE(change_rate, change_percent),
    synced_at = COALESCE(synced_at, as_of)
WHERE current_price IS NULL
   OR previous_close IS NULL
   OR change_price IS NULL
   OR change_rate IS NULL
   OR synced_at IS NULL;

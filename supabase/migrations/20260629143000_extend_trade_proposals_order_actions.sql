-- trade_proposals order action support fields
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS broker_env TEXT DEFAULT 'REAL';
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS external_order_org_no TEXT;
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS raw_order_payload JSONB;
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS replaced_from_id UUID REFERENCES public.trade_proposals(id);
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS modified_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE public.trade_proposals DROP CONSTRAINT IF EXISTS trade_proposals_broker_env_check;
ALTER TABLE public.trade_proposals ADD CONSTRAINT trade_proposals_broker_env_check CHECK (broker_env IN ('MOCK', 'REAL'));

ALTER TABLE public.trade_proposals DROP CONSTRAINT IF EXISTS trade_proposals_status_check;
ALTER TABLE public.trade_proposals ADD CONSTRAINT trade_proposals_status_check
CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED', 'FAILED', 'CANCELED', 'MODIFIED'));

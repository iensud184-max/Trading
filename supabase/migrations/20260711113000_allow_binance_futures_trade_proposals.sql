alter table public.trade_proposals
drop constraint if exists trade_proposals_exchange_check;

alter table public.trade_proposals
add constraint trade_proposals_exchange_check
check (exchange in ('COINONE', 'BINANCE', 'BINANCE_UM_FUTURES', 'KIS', 'TOSS'));

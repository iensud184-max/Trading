create table if not exists public.chatbot_conversation_states (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  pending_action text,
  pending_payload jsonb not null default '{}'::jsonb,
  pending_expires_at timestamptz,
  recommendation_items jsonb not null default '[]'::jsonb,
  recommendation_source text,
  recommendation_expires_at timestamptz,
  updated_at timestamptz not null default timezone('utc'::text, now()),
  constraint chatbot_conversation_states_pending_payload_object
    check (jsonb_typeof(pending_payload) = 'object'),
  constraint chatbot_conversation_states_recommendation_items_array
    check (jsonb_typeof(recommendation_items) = 'array')
);

alter table public.chatbot_conversation_states enable row level security;

grant select, insert, update, delete
on table public.chatbot_conversation_states
to authenticated;

revoke all
on table public.chatbot_conversation_states
from anon;

drop policy if exists "chatbot_conversation_states_owner_select"
on public.chatbot_conversation_states;
create policy "chatbot_conversation_states_owner_select"
on public.chatbot_conversation_states
for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "chatbot_conversation_states_owner_insert"
on public.chatbot_conversation_states;
create policy "chatbot_conversation_states_owner_insert"
on public.chatbot_conversation_states
for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "chatbot_conversation_states_owner_update"
on public.chatbot_conversation_states;
create policy "chatbot_conversation_states_owner_update"
on public.chatbot_conversation_states
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "chatbot_conversation_states_owner_delete"
on public.chatbot_conversation_states;
create policy "chatbot_conversation_states_owner_delete"
on public.chatbot_conversation_states
for delete
to authenticated
using ((select auth.uid()) = user_id);

alter table public.trade_proposals
add column if not exists approved_at timestamptz;

grant select, insert, update, delete
on table public.trade_proposals
to authenticated;

create or replace function public.claim_trade_proposal_for_execution(
  p_proposal_id uuid
)
returns setof public.trade_proposals
language sql
security invoker
set search_path = ''
as $$
  update public.trade_proposals
  set
    status = 'APPROVED',
    approved_at = timezone('utc'::text, now()),
    failure_reason = null
  where id = p_proposal_id
    and user_id = (select auth.uid())
    and status = 'PENDING'
  returning *;
$$;

revoke execute
on function public.claim_trade_proposal_for_execution(uuid)
from public, anon;

grant execute
on function public.claim_trade_proposal_for_execution(uuid)
to authenticated, service_role;

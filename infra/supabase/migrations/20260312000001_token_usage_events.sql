-- Billing: per-LLM-call token usage ledger.
-- One row per provider.complete() call, written in a batch at run completion.
-- api_cost_microdollars = raw provider cost; billed_microdollars = after markup.

create table token_usage_events (
    id                      uuid primary key default gen_random_uuid(),
    org_id                  uuid not null references organizations(id) on delete cascade,
    run_id                  uuid not null references runs(id) on delete cascade,
    call_type               text not null
                            check (call_type in ('file_selection','file_analysis','patch_gen','self_correction')),
    provider                text not null,
    model                   text not null,
    input_tokens            integer not null default 0,
    output_tokens           integer not null default 0,
    -- Raw API cost at provider list price (no markup).
    api_cost_microdollars   bigint not null default 0,
    -- Amount charged to the user after markup (1.5× within plan, 2× overage).
    billed_microdollars     bigint not null default 0,
    rate_type               text not null default 'included'
                            check (rate_type in ('included','overage')),
    created_at              timestamptz not null default now()
);

comment on table token_usage_events is 'Per-call LLM token usage ledger. Aggregated for billing and usage display.';

create index idx_token_usage_org_period on token_usage_events(org_id, created_at);
create index idx_token_usage_run on token_usage_events(run_id);

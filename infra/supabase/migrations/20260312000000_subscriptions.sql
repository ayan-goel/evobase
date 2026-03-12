-- Billing: per-org subscription tracking.
-- One row per organization; free tier is inserted automatically on org creation.
-- Stripe fields are populated when the org upgrades to a paid plan.

create table subscriptions (
    id                               uuid primary key default gen_random_uuid(),
    org_id                           uuid not null unique references organizations(id) on delete cascade,
    tier                             text not null default 'free'
                                     check (tier in ('free','hobby','premium','pro')),
    status                           text not null default 'active'
                                     check (status in ('active','past_due','canceled')),
    stripe_customer_id               text unique,
    stripe_subscription_id           text unique,
    current_period_start             timestamptz not null default now(),
    current_period_end               timestamptz not null default (now() + interval '1 month'),
    -- Raw API budget in microdollars (1 µ$ = $0.000001).
    -- Free: $3.33 → 3333333. Hobby: $13.33 → 13333333. Premium: $40 → 40000000. Pro: $133 → 133000000.
    included_api_budget_microdollars bigint not null default 3333333,
    overage_allowed                  boolean not null default false,
    -- User-set monthly spend cap for overage; null = no limit.
    monthly_spend_limit_microdollars bigint,
    created_at                       timestamptz not null default now(),
    updated_at                       timestamptz not null default now()
);

comment on table subscriptions is 'Per-org billing subscription. Free tier row is auto-created on org creation.';

create index idx_subscriptions_org_id on subscriptions(org_id);
create index idx_subscriptions_stripe_customer on subscriptions(stripe_customer_id);

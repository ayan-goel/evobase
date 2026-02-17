-- SelfOpt MVP Initial Schema
-- All tables use uuid primary keys with gen_random_uuid() default.
-- Text columns with CHECK constraints used instead of Postgres enums for easier migration.
-- Foreign keys cascade on delete where parent removal should propagate.

-- Enable uuid generation
create extension if not exists "pgcrypto";

-- ============================================================================
-- users
-- ============================================================================
create table users (
    id         uuid primary key default gen_random_uuid(),
    email      text unique not null,
    created_at timestamptz not null default now()
);

comment on table users is 'Application users authenticated via Supabase Auth.';

-- ============================================================================
-- organizations
-- ============================================================================
create table organizations (
    id       uuid primary key default gen_random_uuid(),
    name     text not null,
    owner_id uuid not null references users(id) on delete cascade,
    created_at timestamptz not null default now()
);

comment on table organizations is 'Grouping entity for repositories. Each org has one owner.';

-- ============================================================================
-- repositories
-- ============================================================================
create table repositories (
    id              uuid primary key default gen_random_uuid(),
    org_id          uuid not null references organizations(id) on delete cascade,
    github_repo_id  bigint unique,
    default_branch  text not null default 'main',
    package_manager text,
    install_cmd     text,
    build_cmd       text,
    test_cmd        text,
    bench_config    jsonb,
    created_at      timestamptz not null default now()
);

comment on table repositories is 'Connected GitHub repositories with auto-detected build/test configuration.';

-- ============================================================================
-- baselines
-- Stores the baseline metrics for a repository at a given commit SHA.
-- Used as the comparison point for optimization proposals.
-- ============================================================================
create table baselines (
    id                      uuid primary key default gen_random_uuid(),
    repo_id                 uuid not null references repositories(id) on delete cascade,
    sha                     text not null,
    metrics                 jsonb,
    environment_fingerprint jsonb,
    created_at              timestamptz not null default now()
);

comment on table baselines is 'Baseline build/test/bench metrics at a specific commit SHA.';

-- ============================================================================
-- runs
-- Tracks each optimization cycle. Status follows a strict state machine:
-- queued -> running -> completed | failed
-- ============================================================================
create table runs (
    id              uuid primary key default gen_random_uuid(),
    repo_id         uuid not null references repositories(id) on delete cascade,
    sha             text,
    status          text not null default 'queued'
                    check (status in ('queued', 'running', 'completed', 'failed')),
    compute_minutes numeric default 0,
    created_at      timestamptz not null default now()
);

comment on table runs is 'Optimization cycle runs. Each run scans, generates, validates, and packages proposals.';

-- ============================================================================
-- opportunities
-- Identified optimization candidates from the scanner.
-- ============================================================================
create table opportunities (
    id         uuid primary key default gen_random_uuid(),
    run_id     uuid not null references runs(id) on delete cascade,
    type       text not null,
    location   text not null,
    rationale  text,
    risk_score numeric default 0,
    created_at timestamptz not null default now()
);

comment on table opportunities is 'Scanner-identified optimization candidates ranked by impact and risk.';

-- ============================================================================
-- attempts
-- Each attempt applies a patch to an opportunity and records validation results.
-- Rejected attempts are logged but never surfaced as proposals.
-- ============================================================================
create table attempts (
    id                uuid primary key default gen_random_uuid(),
    opportunity_id    uuid not null references opportunities(id) on delete cascade,
    diff              text not null,
    validation_result jsonb,
    status            text not null default 'rejected'
                      check (status in ('accepted', 'rejected')),
    created_at        timestamptz not null default now()
);

comment on table attempts is 'Patch validation attempts. Only accepted attempts become proposals.';

-- ============================================================================
-- proposals
-- Validated, evidence-backed improvements ready for PR creation.
-- pr_url is populated only after the user clicks "Create PR".
-- ============================================================================
create table proposals (
    id             uuid primary key default gen_random_uuid(),
    run_id         uuid not null references runs(id) on delete cascade,
    diff           text not null,
    summary        text,
    metrics_before jsonb,
    metrics_after  jsonb,
    risk_score     numeric default 0,
    created_at     timestamptz not null default now(),
    pr_url         text
);

comment on table proposals is 'Validated optimization proposals with full evidence. PR creation is a user-initiated action.';

-- ============================================================================
-- artifacts
-- References to files stored in Supabase Storage (logs, traces, diffs, benchmarks).
-- Storage paths follow: artifacts/repos/{repo_id}/runs/{run_id}/...
-- ============================================================================
create table artifacts (
    id           uuid primary key default gen_random_uuid(),
    proposal_id  uuid not null references proposals(id) on delete cascade,
    storage_path text not null,
    type         text not null
                 check (type in ('log', 'trace', 'bench', 'diff')),
    created_at   timestamptz not null default now()
);

comment on table artifacts is 'Metadata for evidence files stored in Supabase Storage. Accessed via signed URLs.';

-- ============================================================================
-- settings
-- Per-repository configuration for budget and scheduling.
-- One row per repository (repo_id is the primary key).
-- ============================================================================
create table settings (
    repo_id                uuid primary key references repositories(id) on delete cascade,
    compute_budget_minutes integer not null default 60,
    max_proposals_per_run  integer not null default 10,
    schedule               text not null default '0 2 * * *'
);

comment on table settings is 'Per-repo budget and scheduling configuration. Schedule is a cron string.';

-- ============================================================================
-- Indexes for common query patterns
-- ============================================================================
create index idx_repositories_org_id on repositories(org_id);
create index idx_baselines_repo_id on baselines(repo_id);
create index idx_runs_repo_id on runs(repo_id);
create index idx_runs_status on runs(status);
create index idx_opportunities_run_id on opportunities(run_id);
create index idx_attempts_opportunity_id on attempts(opportunity_id);
create index idx_proposals_run_id on proposals(run_id);
create index idx_artifacts_proposal_id on artifacts(proposal_id);

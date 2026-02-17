-- SelfOpt: Additive migration for columns added in Phases 11–17
--
-- All ALTER TABLE statements use IF NOT EXISTS (Postgres 9.6+) where possible,
-- or guard with DO $$ … END $$ blocks for column additions, so this migration
-- is idempotent and safe to re-apply.
--
-- Phase 11 — Budget + Auto-pause
--   settings: max_candidates_per_run, paused, consecutive_setup_failures,
--             consecutive_flaky_runs, last_run_at
-- Phase 13 — LLM Agent Integration
--   opportunities: llm_reasoning
--   attempts:      llm_reasoning
--   settings:      llm_provider, llm_model
-- Phase 14B — Observability
--   runs: trace_id

-- ============================================================================
-- HELPER: add column only if it does not already exist
-- ============================================================================
-- Postgres does not support ALTER TABLE … ADD COLUMN IF NOT EXISTS before v9.6.
-- All supported Supabase projects (Postgres 15+) have it, but we guard anyway
-- for safety. Using DO blocks to be maximally defensive.

-- ============================================================================
-- repositories — typecheck_cmd (auto-detected by runner, stored for re-runs)
--               github_full_name ("owner/repo", used as HTTPS clone URL)
-- ============================================================================

ALTER TABLE repositories
    ADD COLUMN IF NOT EXISTS typecheck_cmd text;

ALTER TABLE repositories
    ADD COLUMN IF NOT EXISTS github_full_name text;

comment on column repositories.typecheck_cmd is
    'Optional typecheck command (e.g. npx tsc --noEmit). Auto-detected by the '
    'runner at first scan and stored for use in subsequent runs.';

-- ============================================================================
-- settings — Phase 11 budget + auto-pause fields
-- ============================================================================

ALTER TABLE settings
    ADD COLUMN IF NOT EXISTS max_candidates_per_run integer not null default 20;

ALTER TABLE settings
    ADD COLUMN IF NOT EXISTS paused boolean not null default false;

ALTER TABLE settings
    ADD COLUMN IF NOT EXISTS consecutive_setup_failures integer not null default 0;

ALTER TABLE settings
    ADD COLUMN IF NOT EXISTS consecutive_flaky_runs integer not null default 0;

ALTER TABLE settings
    ADD COLUMN IF NOT EXISTS last_run_at timestamptz;

comment on column settings.max_candidates_per_run is
    'Maximum number of patch candidates the agent will attempt per run.';

comment on column settings.paused is
    'When true, no new scheduled runs are enqueued for this repository. '
    'Set automatically when consecutive failure thresholds are exceeded.';

comment on column settings.consecutive_setup_failures is
    'Count of consecutive runs that failed in the setup phase (clone/install). '
    'Auto-pause triggers at 3.';

comment on column settings.consecutive_flaky_runs is
    'Count of consecutive runs whose baseline test suite was flaky. '
    'Auto-pause triggers at 5.';

comment on column settings.last_run_at is
    'Timestamp of the most recent completed run for this repository.';

-- ============================================================================
-- settings — Phase 13 LLM model selection
-- ============================================================================

ALTER TABLE settings
    ADD COLUMN IF NOT EXISTS llm_provider text not null default 'anthropic';

ALTER TABLE settings
    ADD COLUMN IF NOT EXISTS llm_model text not null default 'claude-sonnet-4-5';

comment on column settings.llm_provider is
    'LLM provider used for this repository: anthropic | openai | google.';

comment on column settings.llm_model is
    'Model identifier within the chosen provider, e.g. claude-sonnet-4-5.';

-- ============================================================================
-- opportunities — Phase 13 LLM discovery reasoning trace
-- ============================================================================

ALTER TABLE opportunities
    ADD COLUMN IF NOT EXISTS llm_reasoning jsonb;

comment on column opportunities.llm_reasoning is
    'ThinkingTrace JSON from the LLM discovery agent. Contains model, provider, '
    'reasoning text, and token usage. Surfaced in the UI to show why this '
    'location was flagged.';

-- ============================================================================
-- attempts — Phase 13 LLM patch-generation reasoning trace
-- ============================================================================

ALTER TABLE attempts
    ADD COLUMN IF NOT EXISTS llm_reasoning jsonb;

comment on column attempts.llm_reasoning is
    'ThinkingTrace JSON from the LLM patch-generation agent. Contains model, '
    'provider, reasoning text, and token usage for this specific patch attempt.';

-- ============================================================================
-- proposals — confidence rating from the validation acceptance verdict
-- ============================================================================

ALTER TABLE proposals
    ADD COLUMN IF NOT EXISTS confidence text
    CHECK (confidence IN ('high', 'medium', 'low'));

comment on column proposals.confidence is
    'Confidence rating assigned by the validator acceptance verdict: '
    'high | medium | low. Surfaced in the UI alongside the diff.';

-- ============================================================================
-- runs — Phase 14B trace ID for request correlation
-- ============================================================================

ALTER TABLE runs
    ADD COLUMN IF NOT EXISTS trace_id text;

comment on column runs.trace_id is
    'Copied from X-Request-ID of the HTTP request that enqueued this run. '
    'Threads through all Celery worker logs for grep-ability and distributed '
    'tracing correlation.';

create index if not exists idx_runs_trace_id on runs(trace_id)
    where trace_id is not null;

-- ============================================================================
-- repositories — Phase 17 github_full_name ("owner/repo")
-- ============================================================================

ALTER TABLE repositories
    ADD COLUMN IF NOT EXISTS github_full_name text;

comment on column repositories.github_full_name is
    'GitHub owner/repo full name, e.g. "acme/api-service". '
    'Used as the HTTPS clone URL: https://github.com/{full_name}.git';

-- ============================================================================
-- artifacts — Phase 17 allow NULL proposal_id for baseline artifacts
-- ============================================================================
-- Baseline artifacts (baseline.json, logs.txt, trace.json) are run-level and
-- are created before any proposal exists. Allow proposal_id to be NULL so
-- those artifacts can be stored without a sentinel proposal row.

ALTER TABLE artifacts
    ALTER COLUMN proposal_id DROP NOT NULL;

-- ============================================================================
-- Verify the migration applied correctly (will error if any column is missing)
-- ============================================================================
DO $$
DECLARE
    missing_cols text[] := ARRAY[]::text[];
    col record;
    check_cols text[][] := ARRAY[
        ARRAY['repositories', 'typecheck_cmd'],
        ARRAY['repositories', 'github_full_name'],
        ARRAY['proposals',    'confidence'],
        ARRAY['settings',     'max_candidates_per_run'],
        ARRAY['settings',     'paused'],
        ARRAY['settings',     'consecutive_setup_failures'],
        ARRAY['settings',     'consecutive_flaky_runs'],
        ARRAY['settings',     'last_run_at'],
        ARRAY['settings',     'llm_provider'],
        ARRAY['settings',     'llm_model'],
        ARRAY['opportunities','llm_reasoning'],
        ARRAY['attempts',     'llm_reasoning'],
        ARRAY['runs',         'trace_id']
    ];
    i integer;
BEGIN
    FOR i IN 1..array_length(check_cols, 1) LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name  = check_cols[i][1]
              AND column_name = check_cols[i][2]
        ) THEN
            missing_cols := missing_cols || (check_cols[i][1] || '.' || check_cols[i][2]);
        END IF;
    END LOOP;

    IF array_length(missing_cols, 1) > 0 THEN
        RAISE EXCEPTION 'Migration verification failed — missing columns: %',
            array_to_string(missing_cols, ', ');
    END IF;

    RAISE NOTICE 'Migration 20260217000002 applied successfully — all % columns verified.',
        array_length(check_cols, 1);
END $$;

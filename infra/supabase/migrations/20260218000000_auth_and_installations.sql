-- =============================================================================
-- Phase 1: Authentication & GitHub App Installation tables
--
-- 1. Add GitHub identity columns to users (for OAuth login metadata)
-- 2. Create github_installations table (tracks GitHub App installs per user)
-- 3. Add installation_id FK to repositories (for PR creation token exchange)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- users: add GitHub identity columns
-- ---------------------------------------------------------------------------
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS github_id bigint UNIQUE,
    ADD COLUMN IF NOT EXISTS github_login text,
    ADD COLUMN IF NOT EXISTS avatar_url text;

-- ---------------------------------------------------------------------------
-- github_installations: tracks GitHub App installations linked to users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS github_installations (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id  bigint UNIQUE NOT NULL,
    account_login    text NOT NULL,
    account_id       bigint NOT NULL,
    user_id          uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_github_installations_user_id
    ON github_installations(user_id);

-- ---------------------------------------------------------------------------
-- repositories: link to installation for token exchange during PR creation
-- ---------------------------------------------------------------------------
ALTER TABLE repositories
    ADD COLUMN IF NOT EXISTS installation_id bigint
        REFERENCES github_installations(installation_id);

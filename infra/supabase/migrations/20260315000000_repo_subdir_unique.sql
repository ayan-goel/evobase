-- Allow the same GitHub repo to be connected multiple times with different
-- subdirectories (e.g. apps/web and apps/api from the same monorepo).
--
-- Previously a single-column UNIQUE constraint on github_repo_id prevented this.
-- We replace it with a composite expression index that treats NULL root_dir as
-- an empty string so that two root-level connections still correctly conflict.

ALTER TABLE repositories
  DROP CONSTRAINT IF EXISTS repositories_github_repo_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_repo_rootdir
  ON repositories (github_repo_id, COALESCE(root_dir, ''));

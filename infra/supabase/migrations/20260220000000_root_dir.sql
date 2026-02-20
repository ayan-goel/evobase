-- Add project subdirectory field to repositories.
-- Allows monorepo users to specify which sub-project the runner should analyze
-- instead of always operating at the repository root.

ALTER TABLE repositories
  ADD COLUMN IF NOT EXISTS root_dir TEXT;

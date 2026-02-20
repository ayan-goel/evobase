-- Add detected framework identifier to repositories.
-- Populated by the runner after each detection step and exposed in the API
-- so the UI can display framework logos without waiting for a run.

ALTER TABLE repositories
  ADD COLUMN IF NOT EXISTS framework TEXT;

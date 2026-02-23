-- Add pr_url column to runs for run-level PR tracking
ALTER TABLE runs ADD COLUMN IF NOT EXISTS pr_url text;

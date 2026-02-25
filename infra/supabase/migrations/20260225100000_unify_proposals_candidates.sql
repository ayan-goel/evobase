ALTER TABLE settings DROP COLUMN IF EXISTS max_candidates_per_run;
ALTER TABLE settings ALTER COLUMN max_proposals_per_run SET DEFAULT 20;
UPDATE settings SET max_proposals_per_run = 20 WHERE max_proposals_per_run = 10;

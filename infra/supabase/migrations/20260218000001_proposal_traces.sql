-- Add LLM reasoning trace columns to proposals so the frontend can surface
-- the full agent reasoning chain for each accepted proposal.

ALTER TABLE proposals
  ADD COLUMN IF NOT EXISTS discovery_trace JSONB,
  ADD COLUMN IF NOT EXISTS patch_trace     JSONB;

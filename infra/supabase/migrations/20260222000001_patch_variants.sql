ALTER TABLE proposals ADD COLUMN IF NOT EXISTS patch_variants  JSONB;
ALTER TABLE proposals ADD COLUMN IF NOT EXISTS selection_reason TEXT;
ALTER TABLE proposals ADD COLUMN IF NOT EXISTS approaches_tried  INT;

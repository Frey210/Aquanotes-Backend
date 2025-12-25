-- Add deactivate_at datetime for scheduled device deactivation
ALTER TABLE devices
ADD COLUMN IF NOT EXISTS deactivate_at TIMESTAMP NULL;

-- Add is_active flag for devices (default: true)
ALTER TABLE devices
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

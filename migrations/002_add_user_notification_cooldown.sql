-- Add notification cooldown minutes for users (default: 30)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS notification_cooldown_minutes INTEGER NOT NULL DEFAULT 30;

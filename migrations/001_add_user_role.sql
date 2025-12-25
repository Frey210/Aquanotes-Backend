-- Add role column for RBAC support (default: operator)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'operator';

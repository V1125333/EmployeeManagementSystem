-- Phase 8.5: Account Recovery & Password Reset

ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS force_password_change BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS failed_reset_attempts INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;

CREATE TABLE IF NOT EXISTS password_reset_sessions (
  id VARCHAR(36) PRIMARY KEY,
  employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
  reset_token_hash VARCHAR(64) NOT NULL UNIQUE,
  mfa_verified BOOLEAN DEFAULT FALSE,
  expires_at TIMESTAMP NOT NULL,
  used_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_password_reset_sessions_employee_id
  ON password_reset_sessions (employee_id);

CREATE INDEX IF NOT EXISTS ix_password_reset_sessions_expires_at
  ON password_reset_sessions (expires_at);

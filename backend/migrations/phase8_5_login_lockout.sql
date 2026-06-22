ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS account_locked BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS locked_reason VARCHAR(255) NULL,
  ADD COLUMN IF NOT EXISTS unlocked_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS unlocked_by_user_id VARCHAR(36) NULL;

CREATE TABLE IF NOT EXISTS login_challenge_sessions (
  id VARCHAR(36) PRIMARY KEY,
  employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
  token_hash VARCHAR(64) UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_login_challenge_sessions_employee_id ON login_challenge_sessions (employee_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_login_challenge_sessions_token_hash ON login_challenge_sessions (token_hash);
CREATE INDEX IF NOT EXISTS ix_login_challenge_sessions_expires_at ON login_challenge_sessions (expires_at);

CREATE TABLE IF NOT EXISTS account_unlock_requests (
  id VARCHAR(36) PRIMARY KEY,
  locked_user_id VARCHAR(36) NOT NULL REFERENCES employees(id),
  requested_by_user_id VARCHAR(36) NULL REFERENCES employees(id),
  requested_email VARCHAR(255) NULL,
  request_reason TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'pending',
  reviewed_by_user_id VARCHAR(36) NULL REFERENCES employees(id),
  reviewed_at TIMESTAMPTZ NULL,
  admin_notes TEXT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_unlock_requests_status ON account_unlock_requests (status);
CREATE INDEX IF NOT EXISTS ix_unlock_requests_locked_user ON account_unlock_requests (locked_user_id);

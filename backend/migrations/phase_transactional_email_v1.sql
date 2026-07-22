-- PostgreSQL migration for durable, server-side transactional email.
CREATE TABLE IF NOT EXISTS email_outbox (
    id VARCHAR(36) PRIMARY KEY,
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    recipient_email VARCHAR(320) NOT NULL,
    template_name VARCHAR(80) NOT NULL,
    template_version VARCHAR(20) NOT NULL DEFAULT 'v1',
    encrypted_payload TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 8,
    next_attempt_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at TIMESTAMP NULL,
    locked_by VARCHAR(100) NULL,
    provider_message_id VARCHAR(255) NULL,
    last_error TEXT NULL,
    sent_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_email_outbox_due ON email_outbox(status, next_attempt_at);

CREATE TABLE IF NOT EXISTS account_activation_tokens (
    id VARCHAR(36) PRIMARY KEY,
    employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP NULL,
    revoked_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_account_activation_employee ON account_activation_tokens(employee_id);
CREATE INDEX IF NOT EXISTS ix_account_activation_token_hash ON account_activation_tokens(token_hash);

CREATE TABLE IF NOT EXISTS security_rate_limits (
    id VARCHAR(36) PRIMARY KEY,
    scope VARCHAR(80) NOT NULL,
    key_hash VARCHAR(64) NOT NULL,
    window_started_at TIMESTAMP NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_security_rate_limit_scope_key UNIQUE(scope, key_hash)
);

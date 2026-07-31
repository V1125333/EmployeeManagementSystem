-- Phase 3: durable AI leave-preparation drafts.
-- These rows are AI workflow state, not official leave_requests.
CREATE TABLE IF NOT EXISTS ai_leave_request_drafts (
    id VARCHAR(36) PRIMARY KEY,
    owner_employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
    capability VARCHAR(40) NOT NULL DEFAULT 'leave_request',
    leave_type_id VARCHAR(36) NOT NULL REFERENCES leave_types(id),
    leave_type_code VARCHAR(10) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT NULL,
    eligibility_snapshot TEXT NOT NULL,
    working_day_count NUMERIC(5,1) NOT NULL,
    balance_source VARCHAR(30) NOT NULL,
    approver_id VARCHAR(36) NULL REFERENCES employees(id),
    blocking_reasons TEXT NOT NULL DEFAULT '[]',
    warnings TEXT NOT NULL DEFAULT '[]',
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    payload_hash VARCHAR(64) NOT NULL,
    correlation_id VARCHAR(64) NOT NULL,
    conversation_id VARCHAR(64) NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_ai_leave_drafts_owner_status
    ON ai_leave_request_drafts(owner_employee_id, status, updated_at);
CREATE INDEX IF NOT EXISTS ix_ai_leave_drafts_expiry
    ON ai_leave_request_drafts(expires_at);
CREATE INDEX IF NOT EXISTS ix_ai_leave_drafts_conversation
    ON ai_leave_request_drafts(conversation_id);

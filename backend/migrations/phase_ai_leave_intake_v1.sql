-- Phase 3.5: expiring, principal-bound conversational leave intake.
-- These rows are AI workflow state, not official leave_requests.
CREATE TABLE IF NOT EXISTS ai_leave_intake_states (
    id VARCHAR(36) PRIMARY KEY,
    owner_employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
    conversation_id VARCHAR(64) NOT NULL,
    goal VARCHAR(40) NOT NULL DEFAULT 'prepare_leave_request',
    collected_fields TEXT NOT NULL DEFAULT '{}',
    missing_required_fields TEXT NOT NULL DEFAULT '[]',
    optional_fields TEXT NOT NULL DEFAULT '[]',
    source_confidence TEXT NOT NULL DEFAULT '{}',
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ai_leave_intake_owner_conversation
        UNIQUE (owner_employee_id, conversation_id)
);
CREATE INDEX IF NOT EXISTS ix_ai_leave_intake_owner
    ON ai_leave_intake_states(owner_employee_id);
CREATE INDEX IF NOT EXISTS ix_ai_leave_intake_conversation
    ON ai_leave_intake_states(conversation_id);
CREATE INDEX IF NOT EXISTS ix_ai_leave_intake_expiry
    ON ai_leave_intake_states(expires_at);

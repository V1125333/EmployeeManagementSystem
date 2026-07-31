CREATE TABLE IF NOT EXISTS ai_conversations (
    id VARCHAR(36) PRIMARY KEY,
    owner_employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
    title VARCHAR(160) NOT NULL DEFAULT 'Orbit AI Conversation',
    domain VARCHAR(40) NOT NULL DEFAULT 'leave',
    capability VARCHAR(80),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    workflow_kind VARCHAR(40),
    workflow_reference_id VARCHAR(64),
    workflow_status VARCHAR(40),
    message_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,
    archived_at TIMESTAMP,
    deleted_at TIMESTAMP,
    retention_expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_ai_conversations_owner_employee_id
    ON ai_conversations(owner_employee_id);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_status
    ON ai_conversations(status);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_retention_expires_at
    ON ai_conversations(retention_expires_at);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_owner_updated
    ON ai_conversations(owner_employee_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS ai_conversation_messages (
    id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL
        REFERENCES ai_conversations(id) ON DELETE CASCADE,
    owner_employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    response_status VARCHAR(32),
    result_type VARCHAR(64),
    tool_name VARCHAR(80),
    correlation_id VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_ai_conversation_messages_conversation_id
    ON ai_conversation_messages(conversation_id);
CREATE INDEX IF NOT EXISTS ix_ai_conversation_messages_owner_employee_id
    ON ai_conversation_messages(owner_employee_id);
CREATE INDEX IF NOT EXISTS ix_ai_conversation_messages_created_at
    ON ai_conversation_messages(created_at);

CREATE TABLE IF NOT EXISTS ai_contextual_shadow_evaluations (
    id VARCHAR(36) PRIMARY KEY,
    actor_employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
    conversation_id VARCHAR(36) NOT NULL REFERENCES ai_conversations(id),
    correlation_id VARCHAR(64) NOT NULL,
    active_workflow_type VARCHAR(40) NOT NULL DEFAULT 'none',
    deterministic_goal VARCHAR(60) NOT NULL,
    deterministic_capability VARCHAR(100),
    deterministic_result_category VARCHAR(64) NOT NULL,
    llm_domain VARCHAR(30),
    llm_goal VARCHAR(60),
    llm_workflow_action VARCHAR(30),
    proposed_capabilities TEXT NOT NULL DEFAULT '[]',
    extracted_field_categories TEXT NOT NULL DEFAULT '[]',
    ambiguity VARCHAR(8),
    comparison_outcome VARCHAR(64) NOT NULL,
    segment VARCHAR(40) NOT NULL,
    schema_validation_status VARCHAR(20) NOT NULL,
    provider VARCHAR(40) NOT NULL,
    model VARCHAR(120) NOT NULL,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER,
    output_tokens INTEGER,
    error_category VARCHAR(60),
    error_message VARCHAR(240),
    error_code VARCHAR(80),
    error_http_status INTEGER,
    provider_request_id VARCHAR(120),
    error_retryable BOOLEAN,
    prompt_version VARCHAR(40) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_ai_contextual_shadow_actor_employee_id
    ON ai_contextual_shadow_evaluations(actor_employee_id);
CREATE INDEX IF NOT EXISTS ix_ai_contextual_shadow_conversation_id
    ON ai_contextual_shadow_evaluations(conversation_id);
CREATE INDEX IF NOT EXISTS ix_ai_contextual_shadow_correlation_id
    ON ai_contextual_shadow_evaluations(correlation_id);
CREATE INDEX IF NOT EXISTS ix_ai_contextual_shadow_created_at
    ON ai_contextual_shadow_evaluations(created_at);
CREATE INDEX IF NOT EXISTS ix_ai_shadow_owner_created
    ON ai_contextual_shadow_evaluations(actor_employee_id, created_at DESC);

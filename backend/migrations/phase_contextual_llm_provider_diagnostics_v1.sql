ALTER TABLE ai_contextual_shadow_evaluations
    ADD COLUMN IF NOT EXISTS error_message VARCHAR(240),
    ADD COLUMN IF NOT EXISTS error_code VARCHAR(80),
    ADD COLUMN IF NOT EXISTS error_http_status INTEGER,
    ADD COLUMN IF NOT EXISTS provider_request_id VARCHAR(120),
    ADD COLUMN IF NOT EXISTS error_retryable BOOLEAN;

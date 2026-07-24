CREATE TABLE IF NOT EXISTS employee_documents (
    id VARCHAR(36) PRIMARY KEY,
    employee_id VARCHAR(36) NULL REFERENCES employees(id),
    uploaded_by_id VARCHAR(36) NOT NULL REFERENCES employees(id),
    name VARCHAR(255) NOT NULL,
    stored_file_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(120),
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    checksum_sha256 VARCHAR(64) NOT NULL,
    storage_provider VARCHAR(30) NOT NULL DEFAULT 'local',
    storage_path TEXT NOT NULL,
    category VARCHAR(24) NOT NULL,
    folder VARCHAR(80) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'none',
    tag VARCHAR(80),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_employee_documents_employee_id ON employee_documents(employee_id);
CREATE INDEX IF NOT EXISTS ix_employee_documents_category ON employee_documents(category);
CREATE INDEX IF NOT EXISTS ix_employee_documents_status ON employee_documents(status);
CREATE INDEX IF NOT EXISTS ix_employee_documents_is_deleted ON employee_documents(is_deleted);

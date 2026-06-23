ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS project_manager_id VARCHAR(36) REFERENCES employees(id);

CREATE INDEX IF NOT EXISTS idx_projects_manager ON projects (project_manager_id);

CREATE TABLE IF NOT EXISTS project_documents (
    id                  VARCHAR(36) PRIMARY KEY,
    project_id          VARCHAR(36) NOT NULL REFERENCES projects(id),
    uploaded_by_id      VARCHAR(36) NOT NULL REFERENCES employees(id),
    original_file_name  VARCHAR(255) NOT NULL,
    stored_file_name    VARCHAR(255) NOT NULL,
    file_extension      VARCHAR(20),
    mime_type           VARCHAR(120),
    file_size_bytes     INT,
    checksum_sha256     VARCHAR(64),
    storage_provider    VARCHAR(30) NOT NULL DEFAULT 'local',
    storage_path        TEXT NOT NULL,
    document_type       VARCHAR(50) NOT NULL DEFAULT 'OTHER',
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    deleted_by_id       VARCHAR(36) REFERENCES employees(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pd_project_id ON project_documents (project_id);
CREATE INDEX IF NOT EXISTS idx_pd_is_deleted ON project_documents (is_deleted);

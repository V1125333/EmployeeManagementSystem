BEGIN;

ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS client_id VARCHAR(36) REFERENCES clients(id);

CREATE INDEX IF NOT EXISTS idx_projects_client ON projects (client_id);

COMMIT;

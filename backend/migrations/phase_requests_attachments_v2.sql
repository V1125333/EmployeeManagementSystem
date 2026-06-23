-- Requests attachment storage migration.
-- Run manually against PostgreSQL before restarting the backend.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'request_attachments' AND column_name = 'file_name'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'request_attachments' AND column_name = 'original_file_name'
  ) THEN
    ALTER TABLE request_attachments RENAME COLUMN file_name TO original_file_name;
  END IF;
END $$;

ALTER TABLE request_attachments
  ADD COLUMN IF NOT EXISTS stored_file_name VARCHAR(255),
  ADD COLUMN IF NOT EXISTS file_extension VARCHAR(20),
  ADD COLUMN IF NOT EXISTS checksum_sha256 VARCHAR(64),
  ADD COLUMN IF NOT EXISTS storage_provider VARCHAR(30) DEFAULT 'local',
  ADD COLUMN IF NOT EXISTS file_url TEXT,
  ADD COLUMN IF NOT EXISTS document_type VARCHAR(50) DEFAULT 'OTHER',
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS deleted_by_id VARCHAR(36) REFERENCES employees(id),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

UPDATE request_attachments
SET stored_file_name = COALESCE(storage_path, id || '_unknown')
WHERE stored_file_name IS NULL;

ALTER TABLE request_attachments ALTER COLUMN stored_file_name SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ra_uploaded_by ON request_attachments (uploaded_by_id);
CREATE INDEX IF NOT EXISTS idx_ra_document_type ON request_attachments (document_type);
CREATE INDEX IF NOT EXISTS idx_ra_created_at ON request_attachments (created_at);

CREATE TABLE IF NOT EXISTS employee_requests (
  id VARCHAR(36) PRIMARY KEY,
  employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
  request_type VARCHAR(40) NOT NULL,
  title VARCHAR(200) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  wfh_from_date DATE,
  wfh_to_date DATE,
  wfh_reason TEXT,
  wfh_note TEXT,
  sp_date DATE,
  sp_start_time TIME,
  sp_end_time TIME,
  sp_reason TEXT,
  sp_duration_minutes INTEGER,
  ot_date DATE,
  ot_start_time TIME,
  ot_end_time TIME,
  ot_project_id VARCHAR(36),
  ot_reason TEXT,
  ot_duration_minutes INTEGER,
  exp_date DATE,
  exp_category VARCHAR(80),
  exp_amount NUMERIC(10, 2),
  exp_currency VARCHAR(10),
  exp_description TEXT,
  exp_paid_at TIMESTAMP,
  exp_paid_by_id VARCHAR(36) REFERENCES employees(id),
  reviewed_by_id VARCHAR(36) REFERENCES employees(id),
  reviewed_at TIMESTAMP,
  reviewer_notes TEXT,
  created_by VARCHAR(36) NOT NULL REFERENCES employees(id),
  updated_by VARCHAR(36) REFERENCES employees(id),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  submitted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS request_status_history (
  id VARCHAR(36) PRIMARY KEY,
  request_id VARCHAR(36) NOT NULL REFERENCES employee_requests(id),
  from_status VARCHAR(20),
  to_status VARCHAR(20) NOT NULL,
  changed_by_id VARCHAR(36) NOT NULL REFERENCES employees(id),
  reason TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS request_comments (
  id VARCHAR(36) PRIMARY KEY,
  request_id VARCHAR(36) NOT NULL REFERENCES employee_requests(id),
  author_id VARCHAR(36) NOT NULL REFERENCES employees(id),
  body TEXT NOT NULL,
  is_internal BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS request_attachments (
  id VARCHAR(36) PRIMARY KEY,
  request_id VARCHAR(36) NOT NULL REFERENCES employee_requests(id),
  file_name VARCHAR(255) NOT NULL,
  uploaded_by_id VARCHAR(36) NOT NULL REFERENCES employees(id),
  file_size_bytes INTEGER,
  mime_type VARCHAR(120),
  storage_path TEXT NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_er_employee_id ON employee_requests (employee_id);
CREATE INDEX IF NOT EXISTS idx_er_status ON employee_requests (status);
CREATE INDEX IF NOT EXISTS idx_er_request_type ON employee_requests (request_type);
CREATE INDEX IF NOT EXISTS idx_er_pending ON employee_requests (status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_rsh_request_id ON request_status_history (request_id);
CREATE INDEX IF NOT EXISTS idx_rc_request_id ON request_comments (request_id);
CREATE INDEX IF NOT EXISTS idx_ra_request_id ON request_attachments (request_id);

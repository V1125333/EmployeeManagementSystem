ALTER TABLE employee_requests
  ADD COLUMN IF NOT EXISTS ticket_number VARCHAR(30) UNIQUE,
  ADD COLUMN IF NOT EXISTS current_owner_id VARCHAR(36) REFERENCES employees(id),
  ADD COLUMN IF NOT EXISTS submitted_to_id VARCHAR(36) REFERENCES employees(id),
  ADD COLUMN IF NOT EXISTS pending_since TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS request_ticket_counters (
    prefix VARCHAR(10) NOT NULL,
    year INT NOT NULL,
    last_value INT NOT NULL DEFAULT 0,
    PRIMARY KEY (prefix, year)
);

CREATE INDEX IF NOT EXISTS idx_er_ticket_number ON employee_requests (ticket_number);
CREATE INDEX IF NOT EXISTS idx_er_current_owner ON employee_requests (current_owner_id);
CREATE INDEX IF NOT EXISTS idx_er_pending_since ON employee_requests (pending_since);

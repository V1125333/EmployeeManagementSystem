CREATE TABLE IF NOT EXISTS company_holidays (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    holiday_date DATE NOT NULL,
    holiday_type VARCHAR(30) NOT NULL DEFAULT 'public',
    regions TEXT NOT NULL DEFAULT 'all',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_holidays_date ON company_holidays (holiday_date);
CREATE INDEX IF NOT EXISTS idx_holidays_type ON company_holidays (holiday_type);

ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS holiday_id VARCHAR(36);

INSERT INTO company_holidays (id, name, holiday_date, holiday_type, regions) VALUES
  (gen_random_uuid()::text, 'New Year''s Day', '2026-01-01', 'public', 'all'),
  (gen_random_uuid()::text, 'Independence Day', '2026-07-04', 'public', 'US'),
  (gen_random_uuid()::text, 'Thanksgiving', '2026-11-26', 'public', 'US'),
  (gen_random_uuid()::text, 'Christmas Day', '2026-12-25', 'public', 'all'),
  (gen_random_uuid()::text, 'Republic Day', '2026-01-26', 'public', 'IN'),
  (gen_random_uuid()::text, 'Holi', '2026-03-25', 'public', 'IN'),
  (gen_random_uuid()::text, 'Diwali', '2026-11-08', 'floating', 'IN'),
  (gen_random_uuid()::text, 'Dussehra', '2026-10-28', 'optional', 'IN'),
  (gen_random_uuid()::text, 'UAE National Day', '2026-12-02', 'public', 'AE'),
  (gen_random_uuid()::text, 'Eid Al Fitr', '2026-03-31', 'floating', 'AE'),
  (gen_random_uuid()::text, 'Company Foundation Day', '2026-09-15', 'company', 'all')
ON CONFLICT DO NOTHING;

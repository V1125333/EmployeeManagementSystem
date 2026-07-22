-- Separate an employee's work arrangement from their structured work location.
-- Existing work_location values (Remote/Hybrid/etc.) remain unchanged and are
-- treated as the work-arrangement field for backward compatibility.
ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS work_city VARCHAR(120),
  ADD COLUMN IF NOT EXISTS work_state VARCHAR(120),
  ADD COLUMN IF NOT EXISTS work_country VARCHAR(120);


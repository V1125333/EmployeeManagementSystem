-- Phase 7: Staffing fulfillment and allocation linkage.
-- Apply against PostgreSQL deployments before enabling the allocation creation workflow.

ALTER TABLE staffing_requests
  ADD COLUMN IF NOT EXISTS fulfilled_allocation_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS fulfilled_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS fulfilled_by UUID REFERENCES employees(id);

ALTER TABLE staffing_request_candidates
  ADD COLUMN IF NOT EXISTS allocation_id UUID REFERENCES allocations(id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_staffing_candidate_request_allocation'
  ) THEN
    ALTER TABLE staffing_request_candidates
      ADD CONSTRAINT uq_staffing_candidate_request_allocation
      UNIQUE (staffing_request_id, allocation_id);
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_staffing_candidate_allocated_employee
  ON staffing_request_candidates (staffing_request_id, employee_id)
  WHERE match_status = 'allocated';

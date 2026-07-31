import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { LeaveRequestDraftCard } from './LeaveRequestDraftCard';

describe('LeaveRequestDraftCard approver state', () => {
  it('shows the backend configuration reason when an approver is unresolved', () => {
    render(<LeaveRequestDraftCard draft={{
      tool: 'get_my_leave_request_draft',
      draft_id: 'draft-without-approver',
      capability: 'leave_request',
      status: 'requires_information',
      leave_type: 'Sick Leave',
      leave_type_code: 'SL',
      start_date: '2026-07-31',
      end_date: '2026-08-01',
      calendar_day_count: 2,
      working_day_count: 1,
      reason: 'family event',
      eligibility_status: 'eligible',
      required_leave_units: 1,
      available_leave_balance: 9,
      balance_source: 'stored_balance',
      approver: null,
      approver_resolution: 'missing',
      blocking_reasons: [{
        code: 'APPROVER_SELF_REFERENCE',
        message: 'Your legacy reporting-manager value points to yourself.',
        field: 'approver',
        details: {},
      }],
      warnings: [],
      expires_at: '2026-07-25T17:00:00Z',
      version: 4,
      correlation_id: 'draft-correlation',
    }} />);

    expect(screen.getByText('Needs configuration')).toBeInTheDocument();
    expect(screen.getByText(
      'Your legacy reporting-manager value points to yourself.',
    )).toBeInTheDocument();
    expect(screen.queryByText('Not resolved')).not.toBeInTheDocument();
  });
});

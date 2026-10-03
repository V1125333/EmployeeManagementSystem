import { describe, expect, it } from 'vitest';

import portalSource from './pages/EmployeePortalPages.tsx?raw';
import uiSource from './components/ui/index.tsx?raw';
import { apiErrorMessage, findOverlappingLeaveRequest } from './utils/leaveRequestValidation';

describe('leave request validation feedback', () => {
  it('marks the reason as required and shows an inline error after an attempted action', () => {
    expect(portalSource).toContain('Reason is required to save or submit this request.');
    expect(portalSource).toContain('aria-invalid={leaveValidationAttempted && reasonMissing}');
    expect(portalSource).toContain('role="alert"');
  });

  it('lets incomplete actions reach validation while keeping in-progress actions disabled', () => {
    expect(portalSource).toContain('disabled={!!savingLeave || loadingLeave} onClick={() => saveLeaveRequest(\'draft\')}');
    expect(portalSource).not.toContain('loadingLeave || !formComplete');
  });

  it('styles genuinely disabled shared buttons as unavailable', () => {
    expect(uiSource).toContain('disabled:cursor-not-allowed disabled:opacity-50');
  });

  it('renders structured API errors and warns about overlapping pending leave', () => {
    expect(portalSource).toContain('Choose dates that do not overlap.');
  });

  it('extracts readable messages from supported API error shapes', () => {
    expect(apiErrorMessage({ detail: 'Plain error' }, 'Fallback')).toBe('Plain error');
    expect(apiErrorMessage({ detail: { code: 'LEAVE_OVERLAP', message: 'Dates overlap.' } }, 'Fallback')).toBe('Dates overlap.');
    expect(apiErrorMessage({ detail: [{ msg: 'Start date is invalid.' }, { msg: 'Reason is required.' }] }, 'Fallback')).toBe('Start date is invalid. Reason is required.');
    expect(apiErrorMessage({ detail: { code: 'UNKNOWN' } }, 'Fallback')).toBe('Fallback');
    expect(apiErrorMessage(null, 'Fallback')).toBe('Fallback');
  });

  it('detects inclusive overlaps for pending and approved requests only', () => {
    const requests = [
      { id: 'pending', status: 'pending', start_date: '2026-10-05', end_date: '2026-10-09' },
      { id: 'approved', status: 'approved', start_date: '2026-10-20', end_date: '2026-10-22' },
      { id: 'draft', status: 'draft', start_date: '2026-10-12', end_date: '2026-10-13' },
      { id: 'cancelled', status: 'cancelled', start_date: '2026-10-14', end_date: '2026-10-15' },
    ];

    expect(findOverlappingLeaveRequest(requests, '2026-10-06', '2026-10-07')?.id).toBe('pending');
    expect(findOverlappingLeaveRequest(requests, '2026-10-09', '2026-10-10')?.id).toBe('pending');
    expect(findOverlappingLeaveRequest(requests, '2026-10-19', '2026-10-20')?.id).toBe('approved');
    expect(findOverlappingLeaveRequest(requests, '2026-10-12', '2026-10-15')).toBeUndefined();
  });

  it('excludes the draft currently being edited and ignores invalid ranges', () => {
    const requests = [{ id: 'current', status: 'pending', start_date: '2026-10-05', end_date: '2026-10-09' }];
    expect(findOverlappingLeaveRequest(requests, '2026-10-05', '2026-10-09', 'current')).toBeUndefined();
    expect(findOverlappingLeaveRequest(requests, '', '2026-10-09')).toBeUndefined();
    expect(findOverlappingLeaveRequest(requests, '2026-10-10', '2026-10-09')).toBeUndefined();
  });
});

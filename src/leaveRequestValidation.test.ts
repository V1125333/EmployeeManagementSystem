import { describe, expect, it } from 'vitest';

import portalSource from './pages/EmployeePortalPages.tsx?raw';
import uiSource from './components/ui/index.tsx?raw';

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
    expect(portalSource).toContain("typeof detail.message === 'string'");
    expect(portalSource).toContain("['pending', 'approved'].includes(request.status)");
    expect(portalSource).toContain('Choose dates that do not overlap.');
  });
});

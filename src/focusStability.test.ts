import { describe, expect, it } from 'vitest';

import employeesSource from './pages/EmployeesPage.tsx?raw';
import securityCenterSource from './pages/SecurityCenterPage.tsx?raw';


describe('controlled form focus stability', () => {
  it('keeps the employee edit field component at module scope', () => {
    expect(employeesSource.indexOf('function EditEmployeeField(')).toBeGreaterThan(-1);
    expect(employeesSource.indexOf('function EditEmployeeField(')).toBeLessThan(
      employeesSource.indexOf('function EditEmployeeDrawer('),
    );
    expect(employeesSource).not.toContain('const Field = ({');
    expect(employeesSource).toContain('<EditEmployeeField label="First Name"');
  });

  it('keeps the security unlock modal at module scope', () => {
    expect(securityCenterSource.indexOf('function UnlockModal(')).toBeGreaterThan(-1);
    expect(securityCenterSource.indexOf('function UnlockModal(')).toBeLessThan(
      securityCenterSource.indexOf('export function SecurityCenterPage('),
    );
    expect(securityCenterSource).toContain('onAdminNotesChange={setAdminNotes}');
  });
});

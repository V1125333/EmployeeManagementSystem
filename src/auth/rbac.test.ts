import { describe, expect, it } from 'vitest';
import { assignableRoles, canAccess, canAssignRole, hasPermission, hasPermissionScope } from './rbac';

const hrSubject = {
  role: 'hr_admin',
  permissions: ['portal.access', 'employee.read', 'role.assign', 'employee.read_sensitive'],
  scopes: {
    'employee.read': ['organization'],
    'employee.read_sensitive': ['organization'],
    'role.assign': ['organization'],
  },
};

const systemSubject = {
  role: 'system_admin',
  permissions: ['portal.access', 'security.account.manage', 'security.policy.manage', 'role.assign'],
  scopes: {
    'security.account.manage': ['organization'],
    'security.policy.manage': ['organization'],
    'role.assign': ['organization'],
  },
};

const superSubject = {
  role: 'super_admin',
  permissions: ['role.assign', 'role.manage', 'super_admin.assign', 'security.account.manage', 'employee.read_sensitive'],
  scopes: {
    'role.assign': ['organization'],
    'role.manage': ['organization'],
    'super_admin.assign': ['organization'],
  },
};

describe('frontend RBAC helpers', () => {
  it('uses backend-provided permissions and scopes for access decisions', () => {
    expect(hasPermission(hrSubject, 'employee.read_sensitive')).toBe(true);
    expect(hasPermissionScope(hrSubject, 'employee.read', 'organization')).toBe(true);
    expect(canAccess(hrSubject, 'employee.read', ['organization'])).toBe(true);
    expect(canAccess(hrSubject, 'employee.read', ['direct_reports'])).toBe(false);
    expect(canAccess(systemSubject, 'employee.read_sensitive')).toBe(false);
  });

  it('prevents non-Super Admins from assigning privileged roles in the UI', () => {
    expect(canAssignRole(hrSubject, 'employee')).toBe(true);
    expect(canAssignRole(hrSubject, 'manager')).toBe(true);
    expect(canAssignRole(hrSubject, 'hr_admin')).toBe(false);
    expect(canAssignRole(hrSubject, 'system_admin')).toBe(false);
    expect(canAssignRole(hrSubject, 'super_admin')).toBe(false);

    expect(canAssignRole(superSubject, 'hr_admin')).toBe(true);
    expect(canAssignRole(superSubject, 'system_admin')).toBe(true);
    expect(canAssignRole(superSubject, 'super_admin')).toBe(true);
  });

  it('returns only assignable canonical roles for each subject', () => {
    expect(assignableRoles(hrSubject)).toEqual(['employee', 'manager', 'project_manager', 'resource_manager']);
    expect(assignableRoles(systemSubject)).toEqual(['employee', 'manager', 'project_manager', 'resource_manager']);
    expect(assignableRoles(superSubject)).toEqual([
      'employee',
      'manager',
      'project_manager',
      'resource_manager',
      'hr_admin',
      'system_admin',
      'super_admin',
    ]);
  });
});

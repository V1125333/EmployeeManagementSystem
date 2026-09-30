export const USER_ROLES = [
  'employee',
  'manager',
  'project_manager',
  'resource_manager',
  'hr_admin',
  'system_admin',
  'super_admin',
] as const;

export type UserRole = typeof USER_ROLES[number];
export type PermissionScope = 'self' | 'direct_reports' | 'managed_projects' | 'department' | 'organization';

export const ROLE_LABELS: Record<UserRole, string> = {
  employee: 'Employee',
  manager: 'Manager',
  project_manager: 'Project Manager',
  resource_manager: 'Resource Manager',
  hr_admin: 'HR Admin',
  system_admin: 'System Admin',
  super_admin: 'Super Admin',
};

export interface PermissionSubject {
  role?: string;
  permissions?: readonly string[];
  scopes?: Readonly<Record<string, readonly string[]>>;
}

const SELF_SERVICE_PERMISSIONS = [
  'portal.access',
  'employee.read',
  'employee.update',
  'leave.request',
  'attendance.read',
  'timesheet.manage',
  'project.read',
  'allocation.read',
  'document.read',
] as const;

const ROLE_PERMISSION_FALLBACKS: Record<UserRole, readonly string[]> = {
  employee: SELF_SERVICE_PERMISSIONS,
  manager: [
    ...SELF_SERVICE_PERMISSIONS,
    'leave.approve',
    'attendance.correct',
    'timesheet.approve',
    'allocation.manage',
    'staffing.request',
    'forecast.read',
  ],
  project_manager: [
    ...SELF_SERVICE_PERMISSIONS,
    'project.manage',
    'allocation.manage',
    'staffing.request',
    'staffing.manage',
    'timesheet.approve',
  ],
  resource_manager: [
    ...SELF_SERVICE_PERMISSIONS,
    'staffing.request',
    'staffing.manage',
    'forecast.read',
    'talent.read',
    'allocation.manage',
  ],
  hr_admin: [
    ...SELF_SERVICE_PERMISSIONS,
    'employee.create',
    'employee.read_sensitive',
    'employee.role.assign',
    'role.assign',
    'leave.approve',
    'leave.manage',
    'attendance.correct',
    'attendance.manage',
    'timesheet.approve',
    'document.manage_hr',
    'onboarding.manage',
    'hr_policy.manage',
    'certificate.manage',
    'hr_report.export',
    'audit.read_hr',
  ],
  system_admin: [
    ...SELF_SERVICE_PERMISSIONS,
    'security.account.manage',
    'security.policy.manage',
    'system.settings.manage',
    'integration.manage',
    'asset.manage',
    'role.assign',
    'audit.read_security',
  ],
  super_admin: [
    ...SELF_SERVICE_PERMISSIONS,
    'employee.create',
    'employee.read_sensitive',
    'employee.role.assign',
    'role.assign',
    'leave.approve',
    'leave.manage',
    'attendance.correct',
    'attendance.manage',
    'timesheet.approve',
    'document.manage_hr',
    'onboarding.manage',
    'hr_policy.manage',
    'certificate.manage',
    'hr_report.export',
    'security.account.manage',
    'security.policy.manage',
    'system.settings.manage',
    'integration.manage',
    'asset.manage',
    'audit.read_hr',
    'audit.read_security',
    'project.manage',
    'allocation.manage',
    'staffing.request',
    'staffing.manage',
    'forecast.read',
    'talent.read',
    'client.manage',
    'payroll.export',
    'audit.export',
    'role.manage',
    'super_admin.assign',
  ],
};

const ORGANIZATION_PERMISSIONS = new Set([
  'employee.read',
  'employee.create',
  'employee.update',
  'employee.read_sensitive',
  'employee.role.assign',
  'role.assign',
  'leave.approve',
  'leave.manage',
  'attendance.read',
  'attendance.correct',
  'attendance.manage',
  'timesheet.manage',
  'timesheet.approve',
  'project.read',
  'project.manage',
  'allocation.read',
  'allocation.manage',
  'staffing.request',
  'staffing.manage',
  'forecast.read',
  'talent.read',
  'document.manage_hr',
  'onboarding.manage',
  'hr_policy.manage',
  'certificate.manage',
  'hr_report.export',
  'payroll.export',
  'client.manage',
  'asset.manage',
  'security.account.manage',
  'security.policy.manage',
  'system.settings.manage',
  'integration.manage',
  'audit.read_hr',
  'audit.read_security',
  'audit.export',
  'role.manage',
  'super_admin.assign',
]);

function normalizeRole(value?: string): UserRole | null {
  const normalized = (value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'global_access') return 'super_admin';
  if (normalized === 'hr') return 'hr_admin';
  return USER_ROLES.includes(normalized as UserRole) ? normalized as UserRole : null;
}

function fallbackPermissions(subject: PermissionSubject | null | undefined): readonly string[] {
  const role = normalizeRole(subject?.role);
  return role ? ROLE_PERMISSION_FALLBACKS[role] : [];
}

function effectivePermissions(subject: PermissionSubject | null | undefined): readonly string[] {
  return subject?.permissions?.length ? subject.permissions : fallbackPermissions(subject);
}

function fallbackScopes(subject: PermissionSubject | null | undefined, permission: string): readonly string[] {
  const role = normalizeRole(subject?.role);
  if (!role) return [];
  if (role === 'employee') return ['self'];
  if (role === 'manager') {
    if (ORGANIZATION_PERMISSIONS.has(permission)) return ['direct_reports'];
    return ['self'];
  }
  if (role === 'project_manager') {
    if (['project.read', 'project.manage', 'allocation.read', 'allocation.manage', 'staffing.request', 'staffing.manage', 'timesheet.approve'].includes(permission)) {
      return ['managed_projects'];
    }
    return ['self'];
  }
  if (['resource_manager', 'hr_admin', 'system_admin', 'super_admin'].includes(role)) {
    return ORGANIZATION_PERMISSIONS.has(permission) ? ['organization'] : ['self'];
  }
  return [];
}

function effectiveScopes(subject: PermissionSubject | null | undefined, permission: string): readonly string[] {
  const scopes = subject?.scopes?.[permission];
  return scopes?.length ? scopes : fallbackScopes(subject, permission);
}

export function hasPermission(subject: PermissionSubject | null | undefined, permission: string): boolean {
  return effectivePermissions(subject).includes(permission);
}

export function hasPermissionScope(
  subject: PermissionSubject | null | undefined,
  permission: string,
  scope: PermissionScope,
): boolean {
  return hasPermission(subject, permission) && effectiveScopes(subject, permission).includes(scope);
}

export function canAccess(
  subject: PermissionSubject | null | undefined,
  permission: string,
  scopes?: readonly PermissionScope[],
): boolean {
  if (!hasPermission(subject, permission)) return false;
  return !scopes?.length || scopes.some((scope) => hasPermissionScope(subject, permission, scope));
}

export function canAssignRole(subject: PermissionSubject | null | undefined, target: UserRole): boolean {
  if (!hasPermission(subject, 'role.assign')) return false;
  if (target === 'super_admin') return hasPermission(subject, 'super_admin.assign');
  if (['hr_admin', 'system_admin'].includes(target)) return hasPermission(subject, 'role.manage');
  return true;
}

export function assignableRoles(subject: PermissionSubject | null | undefined): UserRole[] {
  return USER_ROLES.filter((role) => canAssignRole(subject, role));
}

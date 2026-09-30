"""Canonical role, permission, and scope definitions for Reknew EMS.

This module is the single backend source of truth.  Roles answer *who* the
actor is; permissions answer *what* they may do; scopes answer *which records*
the permission applies to.  Domain services still validate the concrete
employee, reporting, or project relationship before returning data.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Mapping


class UserRole(str, Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    PROJECT_MANAGER = "project_manager"
    RESOURCE_MANAGER = "resource_manager"
    HR_ADMIN = "hr_admin"
    SYSTEM_ADMIN = "system_admin"
    SUPER_ADMIN = "super_admin"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACTOR = "contractor"
    INTERN = "intern"
    TRAINEE = "trainee"
    CONSULTANT = "consultant"


class Scope(str, Enum):
    SELF = "self"
    DIRECT_REPORTS = "direct_reports"
    MANAGED_PROJECTS = "managed_projects"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"


class Permission(str, Enum):
    PORTAL_ACCESS = "portal.access"
    EMPLOYEE_READ = "employee.read"
    EMPLOYEE_CREATE = "employee.create"
    EMPLOYEE_UPDATE = "employee.update"
    EMPLOYEE_READ_SENSITIVE = "employee.read_sensitive"
    EMPLOYEE_ROLE_ASSIGN = "employee.role.assign"
    LEAVE_REQUEST = "leave.request"
    LEAVE_APPROVE = "leave.approve"
    LEAVE_MANAGE = "leave.manage"
    ATTENDANCE_READ = "attendance.read"
    ATTENDANCE_CORRECT = "attendance.correct"
    ATTENDANCE_MANAGE = "attendance.manage"
    TIMESHEET_MANAGE = "timesheet.manage"
    TIMESHEET_APPROVE = "timesheet.approve"
    PROJECT_READ = "project.read"
    PROJECT_MANAGE = "project.manage"
    ALLOCATION_READ = "allocation.read"
    ALLOCATION_MANAGE = "allocation.manage"
    STAFFING_REQUEST = "staffing.request"
    STAFFING_MANAGE = "staffing.manage"
    FORECAST_READ = "forecast.read"
    TALENT_READ = "talent.read"
    DOCUMENT_READ = "document.read"
    DOCUMENT_MANAGE_HR = "document.manage_hr"
    ONBOARDING_MANAGE = "onboarding.manage"
    HR_POLICY_MANAGE = "hr_policy.manage"
    CERTIFICATE_MANAGE = "certificate.manage"
    HR_REPORT_EXPORT = "hr_report.export"
    PAYROLL_EXPORT = "payroll.export"
    CLIENT_MANAGE = "client.manage"
    ASSET_MANAGE = "asset.manage"
    SECURITY_ACCOUNT_MANAGE = "security.account.manage"
    SECURITY_POLICY_MANAGE = "security.policy.manage"
    SYSTEM_SETTINGS_MANAGE = "system.settings.manage"
    INTEGRATION_MANAGE = "integration.manage"
    AUDIT_READ_HR = "audit.read_hr"
    AUDIT_READ_SECURITY = "audit.read_security"
    AUDIT_EXPORT = "audit.export"
    ROLE_ASSIGN = "role.assign"
    ROLE_MANAGE = "role.manage"
    SUPER_ADMIN_ASSIGN = "super_admin.assign"
    # Existing Orbit AI self-service contracts retained during migration.
    LEAVE_BALANCE_READ_SELF = "leave.balance.read.self"
    LEAVE_REQUEST_READ_SELF = "leave.request.read.self"
    LEAVE_ASSESS_SELF = "leave.assess.self"
    LEAVE_REQUEST_PREPARE_SELF = "leave.request.prepare.self"
    EMPLOYEE_MANAGER_READ_SELF = "employee.manager.read.self"
    EMPLOYEE_DIRECTORY_READ = "employee.directory.read"
    TIMESHEET_READ_SELF = "timesheet.read.self"
    PROJECT_ASSIGNMENTS_READ_SELF = "project.assignments.read.self"


GrantMap = Mapping[Permission, frozenset[Scope]]


def _grant(*scopes: Scope) -> frozenset[Scope]:
    return frozenset(scopes)


_EMPLOYEE: dict[Permission, frozenset[Scope]] = {
    Permission.PORTAL_ACCESS: _grant(Scope.SELF),
    Permission.EMPLOYEE_READ: _grant(Scope.SELF),
    Permission.EMPLOYEE_UPDATE: _grant(Scope.SELF),
    Permission.LEAVE_REQUEST: _grant(Scope.SELF),
    Permission.ATTENDANCE_READ: _grant(Scope.SELF),
    Permission.TIMESHEET_MANAGE: _grant(Scope.SELF),
    Permission.PROJECT_READ: _grant(Scope.MANAGED_PROJECTS),
    Permission.ALLOCATION_READ: _grant(Scope.SELF),
    Permission.DOCUMENT_READ: _grant(Scope.SELF),
    Permission.LEAVE_BALANCE_READ_SELF: _grant(Scope.SELF),
    Permission.LEAVE_REQUEST_READ_SELF: _grant(Scope.SELF),
    Permission.LEAVE_ASSESS_SELF: _grant(Scope.SELF),
    Permission.LEAVE_REQUEST_PREPARE_SELF: _grant(Scope.SELF),
    Permission.EMPLOYEE_MANAGER_READ_SELF: _grant(Scope.SELF),
    Permission.EMPLOYEE_DIRECTORY_READ: _grant(Scope.SELF),
    Permission.TIMESHEET_READ_SELF: _grant(Scope.SELF),
    Permission.PROJECT_ASSIGNMENTS_READ_SELF: _grant(Scope.SELF),
}


def _with(base: GrantMap, additions: GrantMap) -> dict[Permission, frozenset[Scope]]:
    merged = {permission: frozenset(scopes) for permission, scopes in base.items()}
    for permission, scopes in additions.items():
        merged[permission] = merged.get(permission, frozenset()) | scopes
    return merged


_MANAGER = _with(_EMPLOYEE, {
    Permission.EMPLOYEE_READ: _grant(Scope.DIRECT_REPORTS),
    Permission.LEAVE_APPROVE: _grant(Scope.DIRECT_REPORTS),
    Permission.ATTENDANCE_READ: _grant(Scope.DIRECT_REPORTS),
    Permission.ATTENDANCE_CORRECT: _grant(Scope.DIRECT_REPORTS),
    Permission.TIMESHEET_APPROVE: _grant(Scope.DIRECT_REPORTS),
    Permission.ALLOCATION_READ: _grant(Scope.DIRECT_REPORTS),
    Permission.ALLOCATION_MANAGE: _grant(Scope.DIRECT_REPORTS),
    Permission.STAFFING_REQUEST: _grant(Scope.DIRECT_REPORTS),
    Permission.FORECAST_READ: _grant(Scope.DIRECT_REPORTS),
})

_PROJECT_MANAGER = _with(_EMPLOYEE, {
    Permission.PROJECT_READ: _grant(Scope.MANAGED_PROJECTS),
    Permission.PROJECT_MANAGE: _grant(Scope.MANAGED_PROJECTS),
    Permission.ALLOCATION_READ: _grant(Scope.MANAGED_PROJECTS),
    Permission.ALLOCATION_MANAGE: _grant(Scope.MANAGED_PROJECTS),
    Permission.STAFFING_REQUEST: _grant(Scope.MANAGED_PROJECTS),
    Permission.STAFFING_MANAGE: _grant(Scope.MANAGED_PROJECTS),
    Permission.TIMESHEET_APPROVE: _grant(Scope.MANAGED_PROJECTS),
})

_RESOURCE_MANAGER = _with(_EMPLOYEE, {
    Permission.EMPLOYEE_READ: _grant(Scope.ORGANIZATION),
    Permission.ALLOCATION_READ: _grant(Scope.ORGANIZATION),
    Permission.ALLOCATION_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.STAFFING_REQUEST: _grant(Scope.ORGANIZATION),
    Permission.STAFFING_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.FORECAST_READ: _grant(Scope.ORGANIZATION),
    Permission.TALENT_READ: _grant(Scope.ORGANIZATION),
})

_HR_ADMIN = _with(_EMPLOYEE, {
    Permission.EMPLOYEE_READ: _grant(Scope.ORGANIZATION),
    Permission.EMPLOYEE_READ_SENSITIVE: _grant(Scope.ORGANIZATION),
    Permission.EMPLOYEE_CREATE: _grant(Scope.ORGANIZATION),
    Permission.EMPLOYEE_UPDATE: _grant(Scope.ORGANIZATION),
    Permission.EMPLOYEE_ROLE_ASSIGN: _grant(Scope.ORGANIZATION),
    Permission.ROLE_ASSIGN: _grant(Scope.ORGANIZATION),
    Permission.LEAVE_APPROVE: _grant(Scope.ORGANIZATION),
    Permission.LEAVE_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.ATTENDANCE_READ: _grant(Scope.ORGANIZATION),
    Permission.ATTENDANCE_CORRECT: _grant(Scope.ORGANIZATION),
    Permission.ATTENDANCE_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.TIMESHEET_APPROVE: _grant(Scope.ORGANIZATION),
    Permission.DOCUMENT_MANAGE_HR: _grant(Scope.ORGANIZATION),
    Permission.ONBOARDING_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.HR_POLICY_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.CERTIFICATE_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.HR_REPORT_EXPORT: _grant(Scope.ORGANIZATION),
    Permission.AUDIT_READ_HR: _grant(Scope.ORGANIZATION),
})

_SYSTEM_ADMIN = _with(_EMPLOYEE, {
    Permission.SECURITY_ACCOUNT_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.SECURITY_POLICY_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.SYSTEM_SETTINGS_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.INTEGRATION_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.ASSET_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.ROLE_ASSIGN: _grant(Scope.ORGANIZATION),
    Permission.AUDIT_READ_SECURITY: _grant(Scope.ORGANIZATION),
})

_SUPER_ADMIN = _with(_with(_with(_with(_HR_ADMIN, _SYSTEM_ADMIN), _RESOURCE_MANAGER), _PROJECT_MANAGER), {
    Permission.PROJECT_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.CLIENT_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.PAYROLL_EXPORT: _grant(Scope.ORGANIZATION),
    Permission.AUDIT_EXPORT: _grant(Scope.ORGANIZATION),
    Permission.ROLE_MANAGE: _grant(Scope.ORGANIZATION),
    Permission.SUPER_ADMIN_ASSIGN: _grant(Scope.ORGANIZATION),
})


ROLE_GRANTS: Mapping[UserRole, GrantMap] = MappingProxyType({
    UserRole.EMPLOYEE: MappingProxyType(_EMPLOYEE),
    UserRole.MANAGER: MappingProxyType(_MANAGER),
    UserRole.PROJECT_MANAGER: MappingProxyType(_PROJECT_MANAGER),
    UserRole.RESOURCE_MANAGER: MappingProxyType(_RESOURCE_MANAGER),
    UserRole.HR_ADMIN: MappingProxyType(_HR_ADMIN),
    UserRole.SYSTEM_ADMIN: MappingProxyType(_SYSTEM_ADMIN),
    UserRole.SUPER_ADMIN: MappingProxyType(_SUPER_ADMIN),
})


SAFE_LEGACY_ROLE_MAPPINGS: Mapping[str, UserRole] = MappingProxyType({
    "employee": UserRole.EMPLOYEE,
    "manager": UserRole.MANAGER,
    "project_manager": UserRole.PROJECT_MANAGER,
    "resource_manager": UserRole.RESOURCE_MANAGER,
    "hr": UserRole.HR_ADMIN,
    "hr_admin": UserRole.HR_ADMIN,
    "system_admin": UserRole.SYSTEM_ADMIN,
    "super_admin": UserRole.SUPER_ADMIN,
    # Employment classifications never grant authorization.
    "trainee": UserRole.EMPLOYEE,
    "intern": UserRole.EMPLOYEE,
    "contractor": UserRole.EMPLOYEE,
    "consultant": UserRole.EMPLOYEE,
    "guest": UserRole.EMPLOYEE,
})

AMBIGUOUS_LEGACY_ROLES = frozenset({"admin", "global_access"})


def normalize_identifier(value: str | Enum | None) -> str:
    raw = value.value if isinstance(value, Enum) else value
    return str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")


def canonical_role(value: str | UserRole | None, *, allow_safe_legacy: bool = True) -> UserRole:
    normalized = normalize_identifier(value)
    if normalized in AMBIGUOUS_LEGACY_ROLES:
        raise ValueError(f"Role '{normalized}' requires manual security review.")
    if allow_safe_legacy and normalized in SAFE_LEGACY_ROLE_MAPPINGS:
        return SAFE_LEGACY_ROLE_MAPPINGS[normalized]
    try:
        return UserRole(normalized)
    except ValueError as exc:
        raise ValueError(f"Unknown role '{normalized or value}'.") from exc


def canonical_employment_type(value: str | EmploymentType | None) -> EmploymentType:
    normalized = normalize_identifier(value)
    aliases = {
        "full_time_employee": "full_time",
        "fulltime": "full_time",
        "contract": "contractor",
        "part_time_employee": "part_time",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        return EmploymentType(normalized)
    except ValueError as exc:
        raise ValueError(f"Unknown employment type '{normalized or value}'.") from exc


def grants_for_role(value: str | UserRole) -> GrantMap:
    return ROLE_GRANTS[canonical_role(value)]


def role_has_permission(value: str | UserRole, permission: str | Permission) -> bool:
    permission_value = permission.value if isinstance(permission, Permission) else permission
    return any(item.value == permission_value for item in grants_for_role(value))


def can_assign_role(actor_role: str | UserRole, target_role: str | UserRole) -> bool:
    actor = canonical_role(actor_role)
    target = canonical_role(target_role, allow_safe_legacy=False)
    if actor is UserRole.SUPER_ADMIN:
        return True
    if not role_has_permission(actor, Permission.ROLE_ASSIGN):
        return False
    return target not in {UserRole.HR_ADMIN, UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN}


def serialized_grants(value: str | UserRole) -> tuple[list[str], dict[str, list[str]]]:
    grants = grants_for_role(value)
    permissions = sorted(permission.value for permission in grants)
    scopes = {
        permission.value: sorted(scope.value for scope in permission_scopes)
        for permission, permission_scopes in grants.items()
    }
    return permissions, scopes

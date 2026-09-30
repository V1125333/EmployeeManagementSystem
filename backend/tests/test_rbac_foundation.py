from fastapi import HTTPException

from app.api.admin_security import require_security_admin
from app.api.employees import require_role_assignment, serialize_employee_for_actor
from app.core.authorization import employee_can
from app.core.rbac import Permission, Scope, UserRole, canonical_role, serialized_grants
from app.models.employee import Employee
from app.services.security_service import can_access_export_level


def employee(employee_id: str, role: str, **overrides) -> Employee:
    values = {
        "id": employee_id,
        "first_name": f"First {employee_id}",
        "last_name": "User",
        "work_email": f"{employee_id}@example.com",
        "phone": "5550100",
        "department": "Engineering",
        "designation": "Engineer",
        "role": role,
        "workforce_type": "full_time",
        "employment_type": "full_time",
        "employment_status": "active",
        "work_location": "Remote",
        "reporting_manager": "",
        "is_active": True,
        "is_first_login": False,
        "setup_code": "123456",
        "access_level": "standard",
        "mfa_enabled": False,
        "device_assigned": False,
    }
    values.update(overrides)
    return Employee(**values)


def assert_403(callable_obj, *args):
    try:
        callable_obj(*args)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Expected HTTP 403")


def test_safe_legacy_roles_are_canonicalized_without_granting_ambiguous_admin():
    assert canonical_role("Employee") is UserRole.EMPLOYEE
    assert canonical_role("Manager") is UserRole.MANAGER
    assert canonical_role("Trainee") is UserRole.EMPLOYEE
    for ambiguous in ("admin", "global_access"):
        try:
            canonical_role(ambiguous)
        except ValueError as exc:
            assert "manual security review" in str(exc)
        else:
            raise AssertionError(f"{ambiguous} should require manual review")


def test_hr_admin_and_system_admin_have_separate_permission_sets():
    hr_permissions, _ = serialized_grants(UserRole.HR_ADMIN)
    system_permissions, _ = serialized_grants(UserRole.SYSTEM_ADMIN)

    assert Permission.EMPLOYEE_READ_SENSITIVE.value in hr_permissions
    assert Permission.HR_REPORT_EXPORT.value in hr_permissions
    assert Permission.SECURITY_ACCOUNT_MANAGE.value not in hr_permissions
    assert Permission.SECURITY_POLICY_MANAGE.value not in hr_permissions

    assert Permission.SECURITY_ACCOUNT_MANAGE.value in system_permissions
    assert Permission.SECURITY_POLICY_MANAGE.value in system_permissions
    assert Permission.EMPLOYEE_READ_SENSITIVE.value not in system_permissions
    assert Permission.PAYROLL_EXPORT.value not in system_permissions


def test_role_assignment_denies_super_admin_for_non_super_admins():
    hr = employee("hr", "hr_admin")
    system = employee("system", "system_admin")
    super_admin = employee("super", "super_admin")

    assert_403(require_role_assignment, hr, "super_admin")
    assert_403(require_role_assignment, system, "super_admin")
    require_role_assignment(super_admin, "super_admin")


def test_security_admin_endpoints_allow_system_admin_not_hr_admin():
    assert_403(require_security_admin, employee("hr", "hr_admin"))
    assert require_security_admin(employee("system", "system_admin")).role == "system_admin"
    assert require_security_admin(employee("super", "super_admin")).role == "super_admin"


def test_employee_export_permissions_do_not_leak_hr_or_payroll_to_system_admin():
    resource = employee("resource", "resource_manager")
    hr = employee("hr", "hr_admin")
    system = employee("system", "system_admin")
    super_admin = employee("super", "super_admin")

    assert can_access_export_level(resource, "basic")
    assert not can_access_export_level(resource, "hr")
    assert can_access_export_level(hr, "hr")
    assert not can_access_export_level(hr, "payroll")
    assert not can_access_export_level(system, "basic")
    assert not can_access_export_level(system, "hr")
    assert can_access_export_level(super_admin, "payroll")


def test_employee_serializer_filters_sensitive_fields_by_access_level():
    target = employee(
        "target",
        "employee",
        emergency_contact_name="Private Contact",
        personal_email="private@example.com",
        manager_id="manager",
    )
    manager = employee("manager", "manager")
    resource = employee("resource", "resource_manager")
    hr = employee("hr", "hr_admin")
    system = employee("system", "system_admin")

    team_payload = serialize_employee_for_actor(target, manager)
    directory_payload = serialize_employee_for_actor(target, resource)
    hr_payload = serialize_employee_for_actor(target, hr)
    security_payload = serialize_employee_for_actor(target, system)

    assert "phone" in team_payload
    assert "emergency_contact_name" not in team_payload
    assert "phone" not in directory_payload
    assert "personal_email" in hr_payload
    assert "emergency_contact_name" in hr_payload
    assert "setup_code" in security_payload
    assert "personal_email" not in security_payload
    assert "emergency_contact_name" not in security_payload


def test_employee_can_checks_scope_not_only_permission_name():
    manager = employee("manager", "manager")
    assert employee_can(manager, Permission.EMPLOYEE_READ, Scope.DIRECT_REPORTS)
    assert not employee_can(manager, Permission.EMPLOYEE_READ, Scope.ORGANIZATION)

from datetime import date

from app.api.employees import ADMIN_EMPLOYEE_FIELDS, SELF_PROFILE_FIELDS, SENSITIVE_EMPLOYMENT_FIELDS
from app.schemas.employee import UpdateEmployeeRequest


def test_employee_self_service_fields_are_limited_to_personal_information():
    assert {"personal_email", "phone", "date_of_birth", "current_address"} <= SELF_PROFILE_FIELDS
    assert {"department", "role", "reporting_manager", "work_city", "joining_date"}.isdisjoint(SELF_PROFILE_FIELDS)


def test_admin_fields_include_employment_data_but_exclude_security_controls():
    assert {"department", "role", "reporting_manager", "work_city", "joining_date"} <= ADMIN_EMPLOYEE_FIELDS
    assert {"access_level", "mfa_enabled", "device_assigned"}.isdisjoint(ADMIN_EMPLOYEE_FIELDS)
    assert {"department", "role", "reporting_manager", "joining_date"} <= SENSITIVE_EMPLOYMENT_FIELDS


def test_update_schema_preserves_admin_employment_fields_and_reason():
    payload = UpdateEmployeeRequest(
        department="Engineering",
        role="manager",
        reporting_manager="Super Admin",
        joining_date=date(2026, 7, 1),
        change_reason="Promotion and reporting-line change",
    ).model_dump(exclude_unset=True)

    assert payload == {
        "department": "Engineering",
        "role": "manager",
        "reporting_manager": "Super Admin",
        "joining_date": date(2026, 7, 1),
        "change_reason": "Promotion and reporting-line change",
    }

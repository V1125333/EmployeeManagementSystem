import pytest
from fastapi import HTTPException

from app.models.employee import Employee
from app.services.document_service import _ensure_upload_allowed, infer_category


def employee(role: str) -> Employee:
    return Employee(
        id=f"{role}-document-user",
        first_name="Document",
        last_name="User",
        work_email=f"{role}@example.com",
        phone="5550100",
        workforce_type="full_time",
        role=role,
    )


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("May_2026_Payslip.pdf", "payroll"),
        ("Employee Handbook.pdf", "policy"),
        ("Passport Scan.pdf", "personal"),
        ("College Degree Certificate.pdf", "certificate"),
    ],
)
def test_document_category_inference_matches_taxonomy(file_name, expected):
    assert infer_category(file_name) == expected


def test_employee_uploads_are_limited_to_personal_and_certificates():
    actor = employee("employee")

    _ensure_upload_allowed(actor, "personal")
    _ensure_upload_allowed(actor, "certificate")
    with pytest.raises(HTTPException) as payroll_error:
        _ensure_upload_allowed(actor, "payroll")
    with pytest.raises(HTTPException):
        _ensure_upload_allowed(actor, "policy")

    assert payroll_error.value.status_code == 403


def test_admin_can_upload_all_document_categories():
    actor = employee("super_admin")

    for category in ("payroll", "policy", "personal", "certificate"):
        _ensure_upload_allowed(actor, category)

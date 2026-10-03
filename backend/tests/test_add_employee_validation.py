from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.employee import AddEmployeeRequest


def valid_payload(**overrides):
    payload = {
        "first_name": "Asha",
        "last_name": "Rao",
        "work_email": "asha.rao@example.com",
        "country_code": "+1",
        "phone": "(860) 555-0142",
        "date_of_birth": date(1993, 4, 12),
        "workforce_type": "full_time",
        "employment_type": "full_time",
        "role": "employee",
        "department": "Engineering",
        "designation": "Software Engineer",
        "reporting_manager": "David Park",
        "joining_date": date.today() + timedelta(days=14),
        "work_location": "Hybrid",
        "work_city": "Hartford",
        "work_state": "CT",
        "work_country": "United States",
    }
    payload.update(overrides)
    return payload


def test_add_employee_schema_accepts_formatted_valid_values():
    request = AddEmployeeRequest(**valid_payload(first_name=" José ", last_name=" O’Connor ", phone="+91 98765-43210"))
    assert request.first_name == "José"
    assert request.last_name == "O’Connor"
    assert request.phone == "+91 98765-43210"


@pytest.mark.parametrize("phone", ["letters", "123456", "1234567890123456"])
def test_add_employee_schema_rejects_invalid_phone_values(phone):
    with pytest.raises(ValidationError, match="7 to 15 digits"):
        AddEmployeeRequest(**valid_payload(phone=phone))


def test_add_employee_schema_rejects_future_birth_date_and_blank_required_text():
    with pytest.raises(ValidationError, match="cannot be in the future"):
        AddEmployeeRequest(**valid_payload(date_of_birth=date.today() + timedelta(days=1)))
    with pytest.raises(ValidationError, match="must not be blank"):
        AddEmployeeRequest(**valid_payload(department="   "))


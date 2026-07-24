from datetime import date
from io import BytesIO

from openpyxl import Workbook

from app.api.employees import _parse_bulk_employee_file, _validate_bulk_employee_rows
from app.models.employee import Employee


class _EmployeeQuery:
    def __init__(self, employees):
        self.employees = employees

    def all(self):
        return self.employees


class _FakeDb:
    def __init__(self, employees):
        self.employees = employees

    def query(self, _model):
        return _EmployeeQuery(self.employees)


def existing_manager():
    return Employee(
        id="manager-1",
        first_name="David",
        last_name="Park",
        work_email="david.park@reknew.ai",
        phone="5550000000",
        workforce_type="Full-Time Employee",
        role="manager",
        employment_status="active",
        department="Engineering",
        reporting_manager="Executive Team",
        joining_date=date(2024, 1, 1),
        work_location="Remote",
        is_active=True,
    )


def test_csv_parsing_and_validation_returns_ready_and_specific_errors():
    content = (
        "first_name,last_name,work_email,phone,country_code,department,designation,role,"
        "reporting_manager,workforce_type,work_arrangement,work_city,work_state,work_country,joining_date\n"
        "Asha,Rao,asha.rao@reknew.ai,5550101000,+1,Engineering,Engineer,employee,David Park,Full-Time Employee,Remote,Hartford,CT,USA,2026-08-01\n"
        "Bad,Email,not-an-email,5550102000,+1,Engineering,Engineer,employee,David Park,Full-Time Employee,Remote,Hartford,CT,USA,2026-08-01\n"
    ).encode("utf-8")
    parsed = _parse_bulk_employee_file("employees.csv", content)
    validated = _validate_bulk_employee_rows(_FakeDb([existing_manager()]), parsed)

    assert len(validated) == 2
    assert validated[0]["valid"] is True
    assert validated[0]["payload"]["work_email"] == "asha.rao@reknew.ai"
    assert validated[1]["valid"] is False
    assert validated[1]["error"] == "Invalid email"


def test_validation_rejects_existing_email_unknown_department_and_manager():
    rows = [{
        "first_name": "Asha", "last_name": "Rao", "work_email": "DAVID.PARK@REKNEW.AI",
        "phone": "5550101000", "country_code": "+1", "department": "Unknown",
        "designation": "Engineer", "role": "employee", "reporting_manager": "Missing Manager",
        "workforce_type": "Full-Time Employee", "work_arrangement": "Remote",
        "work_city": "", "work_state": "", "work_country": "USA", "joining_date": "2026-08-01",
    }]
    result = _validate_bulk_employee_rows(_FakeDb([existing_manager()]), rows)[0]

    assert result["valid"] is False
    assert "Duplicate email" in result["errors"]
    assert "Unknown department" in result["errors"]
    assert "Manager not found" in result["errors"]


def test_xlsx_parser_preserves_excel_date_cells():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["first_name", "last_name", "work_email", "joining_date"])
    sheet.append(["Asha", "Rao", "asha@example.com", date(2026, 8, 1)])
    stream = BytesIO()
    workbook.save(stream)

    rows = _parse_bulk_employee_file("employees.xlsx", stream.getvalue())

    assert rows[0]["joining_date"] == "2026-08-01"

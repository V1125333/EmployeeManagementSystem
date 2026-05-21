"""
Employee Service — handles employee creation with DB persistence.
"""

import logging
from sqlalchemy.orm import Session
from app.models.employee import Employee
from app.schemas.employee import AddEmployeeRequest, AddEmployeeResponse
from app.services.auth_service import generate_setup_code

logger = logging.getLogger(__name__)


def create_employee(db: Session, data: AddEmployeeRequest) -> AddEmployeeResponse:
    """Create a new employee record in the database."""

    full_name = f"{data.first_name} {data.last_name}"
    logger.info(f"Creating employee: {full_name} ({data.work_email})")

    # Check if email already exists
    existing = db.query(Employee).filter(Employee.work_email == data.work_email).first()
    if existing:
        return AddEmployeeResponse(
            success=False,
            message=f"Employee with email {data.work_email} already exists",
        )

    # Generate setup code
    setup_code = generate_setup_code(data.last_name, data.date_of_birth)

    # Create employee record
    employee = Employee(
        first_name=data.first_name,
        last_name=data.last_name,
        work_email=data.work_email,
        country_code=data.country_code,
        phone=data.phone,
        date_of_birth=data.date_of_birth,
        workforce_type=data.workforce_type,
        role=data.role,
        department=data.department,
        designation=data.designation,
        reporting_manager=data.reporting_manager,
        joining_date=data.joining_date,
        work_location=data.work_location,
        employment_status="active",
        setup_code=setup_code,
        is_first_login=True,
        is_active=True,
    )

    db.add(employee)
    db.commit()
    db.refresh(employee)

    logger.info(f"Employee created: {employee.id} | Setup code: {setup_code}")

    return AddEmployeeResponse(
        success=True,
        message=f"Employee {full_name} added successfully",
        employee_id=employee.id,
        setup_code=setup_code,
    )

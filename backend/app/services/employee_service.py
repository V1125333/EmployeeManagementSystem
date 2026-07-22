"""
Employee Service — handles employee creation with DB persistence.
"""

import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.employee import Employee
from app.schemas.employee import AddEmployeeRequest, AddEmployeeResponse
from app.services.transactional_email_service import issue_activation

logger = logging.getLogger(__name__)


def create_employee(db: Session, data: AddEmployeeRequest) -> AddEmployeeResponse:
    """Create a new employee record in the database."""

    full_name = f"{data.first_name} {data.last_name}"
    normalized_email = str(data.work_email).strip().lower()
    logger.info(f"Creating employee: {full_name} ({normalized_email})")

    # Check if email already exists
    existing = db.query(Employee).filter(func.lower(Employee.work_email) == normalized_email).first()
    if existing:
        return AddEmployeeResponse(
            success=False,
            message=f"Employee with email {normalized_email} already exists",
        )

    # Create employee record
    employee = Employee(
        first_name=data.first_name,
        last_name=data.last_name,
        work_email=normalized_email,
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
        work_city=data.work_city.strip() if data.work_city else None,
        work_state=data.work_state.strip() if data.work_state else None,
        work_country=data.work_country.strip() if data.work_country else None,
        employment_status="active",
        setup_code=None,
        is_first_login=True,
        is_active=True,
    )

    db.add(employee)
    db.flush()
    if settings.TRANSACTIONAL_EMAIL_ENABLED:
        issue_activation(db, employee)
    db.commit()
    db.refresh(employee)

    logger.info("Employee created: %s; activation email queued", employee.id)

    return AddEmployeeResponse(
        success=True,
        message=f"Employee {full_name} added successfully",
        employee_id=employee.id,
        setup_code=None,
    )

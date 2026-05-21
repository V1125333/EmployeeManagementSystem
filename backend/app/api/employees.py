"""
Employee API endpoints.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.core.database import get_db
from app.models.employee import Employee
from app.schemas.employee import AddEmployeeRequest, AddEmployeeResponse, UpdateEmployeeRequest
from app.services.employee_service import create_employee
import base64

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("/")
async def list_employees(
    search: Optional[str] = Query(None, description="Search by name or email"),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List employees with search, filters, and pagination."""
    query = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai")

    # Search
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Employee.first_name.ilike(search_term),
                Employee.last_name.ilike(search_term),
                Employee.work_email.ilike(search_term),
            )
        )

    # Filters
    if department:
        query = query.filter(Employee.department == department)
    if status:
        query = query.filter(Employee.employment_status == status)
    if role:
        query = query.filter(Employee.role == role)
    if location:
        query = query.filter(Employee.work_location == location)

    # Count total before pagination
    total = query.count()

    # Pagination
    employees = query.order_by(Employee.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return {
        "employees": [
            {
                "id": emp.id,
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "work_email": emp.work_email,
                "phone": emp.phone,
                "department": emp.department,
                "designation": emp.designation,
                "role": emp.role,
                "workforce_type": emp.workforce_type,
                "employment_status": emp.employment_status,
                "work_location": emp.work_location,
                "joining_date": str(emp.joining_date) if emp.joining_date else None,
                "reporting_manager": emp.reporting_manager,
                "profile_image_url": emp.profile_image_url,
                "is_active": emp.is_active,
                "is_first_login": emp.is_first_login,
                "setup_code": emp.setup_code,
                "created_at": str(emp.created_at),
            }
            for emp in employees
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/{employee_id}")
async def get_employee(employee_id: str, db: Session = Depends(get_db)):
    """Get single employee details."""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {
        "id": emp.id,
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "work_email": emp.work_email,
        "personal_email": emp.personal_email,
        "phone": emp.phone,
        "country_code": emp.country_code,
        "date_of_birth": str(emp.date_of_birth) if emp.date_of_birth else None,
        "gender": emp.gender,
        "department": emp.department,
        "designation": emp.designation,
        "role": emp.role,
        "workforce_type": emp.workforce_type,
        "employment_status": emp.employment_status,
        "work_location": emp.work_location,
        "location": emp.location,
        "joining_date": str(emp.joining_date) if emp.joining_date else None,
        "reporting_manager": emp.reporting_manager,
        "onboarding_type": emp.onboarding_type,
        "profile_image_url": emp.profile_image_url,
        "emergency_contact_name": emp.emergency_contact_name,
        "emergency_contact_phone": emp.emergency_contact_phone,
        "emergency_contact_relation": emp.emergency_contact_relation,
        "current_address": emp.current_address,
        "is_active": emp.is_active,
        "is_first_login": emp.is_first_login,
        "setup_code": emp.setup_code,
        "created_at": str(emp.created_at),
    }


@router.post("/", response_model=AddEmployeeResponse)
async def add_employee(data: AddEmployeeRequest, db: Session = Depends(get_db)):
    """Add a new employee with setup code for first-time login."""
    try:
        result = create_employee(db, data)
        return result
    except Exception as e:
        logger.error(f"Error adding employee: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{employee_id}")
async def update_employee(
    employee_id: str,
    data: UpdateEmployeeRequest,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_role: str = Header(None, alias="x-user-role"),
    db: Session = Depends(get_db),
):
    """Update employee details. Current user must be the employee or super_admin."""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Authorization: user can only update their own profile OR super_admin can update anyone
    is_self = current_user_id == employee_id
    is_super_admin = current_user_role == "super_admin"

    if not (is_self or is_super_admin):
        raise HTTPException(status_code=403, detail="Not authorized to update this employee")

    # Fields that only super_admin can edit
    restricted_fields = {"date_of_birth", "employment_status", "date_of_exit", "inactive_reason"}

    # Check if user is trying to edit restricted fields without being super_admin
    updates = data.dict(exclude_unset=True)
    if not is_super_admin:
        for field in restricted_fields:
            if field in updates:
                raise HTTPException(
                    status_code=403,
                    detail=f"Only super admin can modify {field.replace('_', ' ')}",
                )

    # Apply updates
    for field, value in updates.items():
        if hasattr(emp, field):
            setattr(emp, field, value)

    db.commit()
    db.refresh(emp)

    return {
        "success": True,
        "message": "Employee updated successfully",
        "id": emp.id,
    }


@router.post("/{employee_id}/upload-profile-picture")
async def upload_profile_picture(
    employee_id: str,
    file: UploadFile = File(...),
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_role: str = Header(None, alias="x-user-role"),
    db: Session = Depends(get_db),
):
    """Upload profile picture for an employee. User can only upload for their own profile or super_admin can upload for anyone."""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Authorization: user can only update their own profile OR super_admin can update anyone
    is_self = current_user_id == employee_id
    is_super_admin = current_user_role == "super_admin"

    if not (is_self or is_super_admin):
        raise HTTPException(status_code=403, detail="Not authorized to upload profile picture for this employee")

    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Allowed: JPEG, PNG, WebP, GIF"
        )

    # Validate file size (max 5MB)
    file_content = await file.read()
    if len(file_content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")

    # Convert to base64
    image_base64 = base64.b64encode(file_content).decode('utf-8')
    data_uri = f"data:{file.content_type};base64,{image_base64}"

    # Update employee profile picture
    emp.profile_image_url = data_uri
    db.commit()
    db.refresh(emp)

    return {
        "success": True,
        "message": "Profile picture uploaded successfully",
        "profile_image_url": emp.profile_image_url,
    }



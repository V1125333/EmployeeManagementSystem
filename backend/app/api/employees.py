"""
Employee API endpoints.
"""

import logging
from typing import Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Header, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.core.database import get_db
from app.models.employee import Employee, EmployeeAuditLog, EmployeePerformanceSnapshot
from app.models.leave_attendance import LeaveBalance, LeaveRequest
from app.models.operations import Allocation, Project
from app.models.training import TrainingEnrollment
from app.schemas.employee import AddEmployeeRequest, AddEmployeeResponse, UpdateEmployeeRequest
from app.services.employee_service import create_employee
import base64

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/employees", tags=["Employees"])


def serialize_employee(emp: Employee) -> dict:
    """Serialize employee data used by profile and employee screens."""
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
        "workforce_status": emp.workforce_status,
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
        "permanent_address": emp.permanent_address,
        "is_active": emp.is_active,
        "is_first_login": emp.is_first_login,
        "last_login_at": str(emp.last_login_at) if emp.last_login_at else None,
        "last_active_at": str(emp.last_active_at) if emp.last_active_at else None,
        "access_level": emp.access_level,
        "mfa_enabled": emp.mfa_enabled,
        "device_assigned": emp.device_assigned,
        "setup_code": emp.setup_code,
        "created_at": str(emp.created_at),
        "last_updated_at": str(emp.last_updated_at) if emp.last_updated_at else None,
        "updated_by": emp.updated_by,
    }


def changed_by_value(email: str | None, name: str | None, user_id: str | None) -> str:
    return email or name or user_id or "unknown"


def stringify_audit_value(value) -> str | None:
    if value is None:
        return None
    return str(value)


def log_employee_changes(
    db: Session,
    employee_id: str,
    old_values: dict,
    updates: dict,
    changed_by: str,
):
    important_fields = {
        "role",
        "department",
        "designation",
        "reporting_manager",
        "work_location",
        "access_level",
        "employment_status",
        "workforce_type",
        "workforce_status",
        "mfa_enabled",
        "device_assigned",
    }

    for field in important_fields.intersection(updates.keys()):
        old_value = stringify_audit_value(old_values.get(field))
        new_value = stringify_audit_value(updates.get(field))
        if old_value == new_value:
            continue

        db.add(EmployeeAuditLog(
            employee_id=employee_id,
            action_type="field_changed",
            field_name=field,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            changed_at=datetime.utcnow(),
        ))


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
                "country_code": emp.country_code,
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

    return serialize_employee(emp)


@router.get("/{employee_id}/preview")
async def get_employee_preview(employee_id: str, db: Session = Depends(get_db)):
    """Executive employee preview drawer data."""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    today = date.today()
    current_leave = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == "approved",
        LeaveRequest.start_date <= today,
        LeaveRequest.end_date >= today,
    ).first()
    upcoming_leave = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_(["approved", "pending"]),
        LeaveRequest.start_date > today,
    ).order_by(LeaveRequest.start_date.asc()).first()

    leave_balance_query = db.query(
        func.sum(LeaveBalance.total_days - LeaveBalance.used_days)
    ).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.year == today.year,
    )
    leave_balance = leave_balance_query.scalar()
    has_leave_balance = db.query(LeaveBalance.id).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.year == today.year,
    ).first() is not None

    active_allocations = db.query(Allocation).filter(
        Allocation.employee_id == employee_id,
        Allocation.is_active == True,
        Allocation.start_date <= today,
        or_(Allocation.end_date.is_(None), Allocation.end_date >= today),
    ).all()
    allocation_status = "allocated" if active_allocations else None

    completed_courses = db.query(TrainingEnrollment).filter(
        TrainingEnrollment.employee_id == employee_id,
        TrainingEnrollment.status == "completed",
    ).count()
    total_courses = db.query(TrainingEnrollment).filter(
        TrainingEnrollment.employee_id == employee_id,
    ).count()
    learning_percent = round((completed_courses / total_courses) * 100) if total_courses else 0

    performance = db.query(EmployeePerformanceSnapshot).filter(
        EmployeePerformanceSnapshot.employee_id == employee_id,
    ).order_by(EmployeePerformanceSnapshot.updated_at.desc()).first()

    audit_logs = db.query(EmployeeAuditLog).filter(
        EmployeeAuditLog.employee_id == employee_id,
    ).order_by(EmployeeAuditLog.changed_at.desc()).limit(5).all()

    days_inactive = None
    if emp.last_active_at:
        days_inactive = (datetime.utcnow() - emp.last_active_at).days

    stored_access_level = (emp.access_level or "").strip()
    access_level = stored_access_level if stored_access_level and stored_access_level.lower() != "standard" else emp.role
    mfa_status = "not_available"
    if emp.mfa_enabled or (emp.totp_secret and not emp.is_first_login):
        mfa_status = "enabled"
    elif emp.totp_secret and emp.is_first_login:
        mfa_status = "pending_setup"

    return {
        "employee": serialize_employee(emp),
        "account_activation": {
            "account_status": "pending_activation" if emp.is_first_login else ("active" if emp.is_active else "inactive"),
            "activation_code": emp.setup_code if emp.is_first_login else None,
            "invite_status": "pending" if emp.is_first_login else "accepted",
        },
        "workforce_status": {
            "employment_status": emp.employment_status,
            "availability": "on_leave" if current_leave else None,
            "allocation_status": allocation_status,
            "employment_type": emp.workforce_type,
            "active_allocations": len(active_allocations),
        },
        "last_activity": {
            "last_login_at": str(emp.last_login_at) if emp.last_login_at else None,
            "last_active_at": str(emp.last_active_at) if emp.last_active_at else None,
            "last_active_status": "active_recently" if days_inactive is not None and days_inactive <= 7 else "inactive_or_unknown",
            "days_inactive": days_inactive,
        },
        "leave_summary": {
            "available_leave_days": float(leave_balance) if has_leave_balance and leave_balance is not None else None,
            "current_leave_status": "on_leave" if current_leave else "available",
            "upcoming_leave_start": str(upcoming_leave.start_date) if upcoming_leave else None,
            "upcoming_leave_end": str(upcoming_leave.end_date) if upcoming_leave else None,
            "upcoming_leave_status": upcoming_leave.status if upcoming_leave else None,
        },
        "learning_progress": {
            "completed_courses": completed_courses,
            "total_courses": total_courses,
            "completion_percentage": learning_percent,
        },
        "performance_snapshot": {
            "latest_rating": float(performance.latest_rating) if performance and performance.latest_rating is not None else None,
            "last_review_date": str(performance.last_review_date) if performance and performance.last_review_date else None,
            "kpi_score": float(performance.kpi_score) if performance and performance.kpi_score is not None else None,
        },
        "it_access": {
            "access_level": access_level,
            "mfa_enabled": True if mfa_status == "enabled" else None,
            "mfa_status": mfa_status,
            "assigned_systems_count": len(active_allocations) if active_allocations else None,
            "last_login_at": str(emp.last_login_at) if emp.last_login_at else None,
            "device_tracking_available": False,
            "device_assigned": None,
        },
        "audit_changes": [
            {
                "id": log.id,
                "action_type": log.action_type,
                "field_name": log.field_name,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "changed_by": log.changed_by,
                "changed_at": str(log.changed_at),
            }
            for log in audit_logs
        ],
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
    current_user_email: str = Header(None, alias="x-user-email"),
    current_user_name: str = Header(None, alias="x-user-name"),
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
    restricted_fields = {"employment_status", "date_of_exit", "inactive_reason"}

    # Check if user is trying to edit restricted fields without being super_admin
    updates = data.dict(exclude_unset=True)
    if not is_super_admin:
        for field in restricted_fields:
            if field in updates:
                raise HTTPException(
                    status_code=403,
                    detail=f"Only super admin can modify {field.replace('_', ' ')}",
                )

    old_values = {field: getattr(emp, field) for field in updates.keys() if hasattr(emp, field)}

    # Apply updates
    for field, value in updates.items():
        if hasattr(emp, field):
            setattr(emp, field, value)

    emp.last_updated_at = datetime.utcnow()
    emp.updated_by = changed_by_value(current_user_email, current_user_name, current_user_id)
    log_employee_changes(db, employee_id, old_values, updates, emp.updated_by)

    db.commit()
    db.refresh(emp)

    return {
        "success": True,
        "message": "Employee updated successfully",
        "id": emp.id,
        "employee": serialize_employee(emp),
    }


@router.post("/{employee_id}/upload-profile-picture")
async def upload_profile_picture(
    employee_id: str,
    file: UploadFile = File(...),
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_role: str = Header(None, alias="x-user-role"),
    current_user_email: str = Header(None, alias="x-user-email"),
    current_user_name: str = Header(None, alias="x-user-name"),
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
    emp.last_updated_at = datetime.utcnow()
    emp.updated_by = current_user_email or current_user_name or current_user_id or "unknown"
    db.commit()
    db.refresh(emp)

    return {
        "success": True,
        "message": "Profile picture uploaded successfully",
        "profile_image_url": emp.profile_image_url,
        "employee": serialize_employee(emp),
    }

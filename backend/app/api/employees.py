"""
Employee API endpoints.
"""

import logging
from urllib.parse import quote
from typing import Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Header, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, literal, or_
from app.core.database import get_db
from app.models.employee import Employee, EmployeeAuditLog, EmployeePerformanceSnapshot
from app.models.leave_attendance import LeaveBalance, LeaveRequest
from app.models.operations import ActionInboxItem, Allocation, Notification, Project
from app.models.training import TrainingEnrollment
from app.schemas.employee import AddEmployeeRequest, AddEmployeeResponse, UpdateEmployeeRequest
from app.services.employee_service import create_employee
from app.services.audit_service import changed_fields, log_audit, log_authorization_failure
from app.services.settings_service import get_current_employee, is_admin_role, normalize_role, require_admin_employee
from app.services.security_service import (
    export_employee_csv,
    log_sensitive_access,
    require_export_level,
)
import base64

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/employees", tags=["Employees"])


SELF_PROFILE_FIELDS = {
    "first_name",
    "last_name",
    "personal_email",
    "phone",
    "country_code",
    "date_of_birth",
    "gender",
    "emergency_contact_name",
    "emergency_contact_phone",
    "emergency_contact_relation",
    "current_address",
    "permanent_address",
    "profile_image_url",
}


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


def employee_name(emp: Employee) -> str:
    return " ".join(part.strip() for part in [emp.first_name, emp.last_name] if part and part.strip())


def can_view_employee_detail(actor: Employee, target: Employee) -> bool:
    if actor.id == target.id or is_admin_role(actor.role):
        return True
    if normalize_role(actor.role) != "manager":
        return False
    actor_name = employee_name(actor)
    return bool(
        target.manager_id == actor.id
        or target.reporting_manager == actor_name
        or target.reporting_manager == actor.work_email
    )


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
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    """List employees with search, filters, and pagination."""
    require_admin_employee(db, current_user_id, current_user_email)
    query = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai")
    organization_total = query.count()

    # Search
    if search:
        normalized_search = " ".join(search.strip().split())
        if normalized_search:
            full_name = (
                func.coalesce(Employee.first_name, "")
                + literal(" ")
                + func.coalesce(Employee.last_name, "")
            )
            searchable_fields = [
                Employee.first_name,
                Employee.last_name,
                Employee.work_email,
                Employee.department,
                Employee.designation,
                Employee.role,
                Employee.work_location,
                Employee.location,
                full_name,
            ]
            token_filters = []
            for token in normalized_search.split(" "):
                token_term = f"%{token}%"
                token_filters.append(or_(*[field.ilike(token_term) for field in searchable_fields]))

            phrase_term = f"%{normalized_search}%"
            query = query.filter(or_(
                full_name.ilike(phrase_term),
                Employee.work_email.ilike(phrase_term),
                and_(*token_filters),
            ))

    # Filters
    if department:
        query = query.filter(Employee.department.ilike(department))
    if status:
        query = query.filter(Employee.employment_status.ilike(status))
    if role:
        normalized_role = role.strip().lower().replace(" ", "_").replace("-", "_")
        role_value = func.lower(func.replace(func.replace(Employee.role, " ", "_"), "-", "_"))
        query = query.filter(role_value == normalized_role)
    if location:
        query = query.filter(Employee.work_location.ilike(location))

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
        "organization_total": organization_total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/export")
async def export_employees(
    search: Optional[str] = Query(None, description="Search by name or email"),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    level: str = Query("basic", pattern="^(basic|hr|payroll)$"),
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    """Export employees with server-side role checks and sensitive-access audit."""
    actor = require_admin_employee(db, current_user_id, current_user_email)
    require_export_level(actor, level)

    query = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai")
    if search:
        normalized_search = " ".join(search.strip().split())
        if normalized_search:
            full_name = (
                func.coalesce(Employee.first_name, "")
                + literal(" ")
                + func.coalesce(Employee.last_name, "")
            )
            searchable_fields = [
                Employee.first_name,
                Employee.last_name,
                Employee.work_email,
                Employee.department,
                Employee.designation,
                Employee.role,
                Employee.work_location,
                Employee.location,
                full_name,
            ]
            token_filters = []
            for token in normalized_search.split(" "):
                token_term = f"%{token}%"
                token_filters.append(or_(*[field.ilike(token_term) for field in searchable_fields]))
            phrase_term = f"%{normalized_search}%"
            query = query.filter(or_(
                full_name.ilike(phrase_term),
                Employee.work_email.ilike(phrase_term),
                and_(*token_filters),
            ))
    if department:
        query = query.filter(Employee.department.ilike(department))
    if status:
        query = query.filter(Employee.employment_status.ilike(status))
    if role:
        normalized_role = role.strip().lower().replace(" ", "_").replace("-", "_")
        role_value = func.lower(func.replace(func.replace(Employee.role, " ", "_"), "-", "_"))
        query = query.filter(role_value == normalized_role)
    if location:
        query = query.filter(Employee.work_location.ilike(location))

    employees = query.order_by(Employee.created_at.desc()).limit(10000).all()
    log_sensitive_access(
        db,
        actor,
        action="employee_csv_export",
        target_type="employees",
        target_id=None,
        sensitivity_level="restricted" if level == "basic" else "confidential",
        reason=f"{level} employee export",
        metadata={
            "level": level,
            "row_count": len(employees),
            "filters": {
                "search": search,
                "department": department,
                "status": status,
                "role": role,
                "location": location,
            },
        },
    )
    db.commit()

    csv_content = export_employee_csv(employees, level)
    filename = quote(f"reknew-employees-{level}-{date.today().isoformat()}.csv")
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{employee_id}")
async def get_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    """Get single employee details."""
    actor = get_current_employee(db, current_user_id, current_user_email)
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if not can_view_employee_detail(actor, emp):
        raise HTTPException(status_code=403, detail="Not authorized to view this employee.")

    if actor.id != employee_id:
        log_sensitive_access(
            db,
            actor,
            action="employee_profile_view",
            target_type="employee",
            target_id=employee_id,
            sensitivity_level="confidential",
            reason="Admin profile lookup",
        )
        db.commit()

    return serialize_employee(emp)


@router.get("/{employee_id}/preview")
async def get_employee_preview(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    """Executive employee preview drawer data."""
    actor = require_admin_employee(db, current_user_id, current_user_email)
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    log_sensitive_access(
        db,
        actor,
        action="employee_preview_view",
        target_type="employee",
        target_id=employee_id,
        sensitivity_level="confidential",
        reason="Admin employee preview",
    )
    db.commit()

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
        Allocation.status == "active",
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


@router.post("/{employee_id}/remind-emergency-contact")
async def remind_emergency_contact(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    """Ask an employee to update missing emergency contact information."""
    actor = require_admin_employee(db, current_user_id, current_user_email)
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if not emp.is_active:
        raise HTTPException(status_code=400, detail="Reminders can only be sent to active employees.")

    emergency_contact_complete = all([
        bool((emp.emergency_contact_name or "").strip()),
        bool((emp.emergency_contact_phone or "").strip()),
        bool((emp.emergency_contact_relation or "").strip()),
    ])
    if emergency_contact_complete:
        db.query(ActionInboxItem).filter(
            ActionInboxItem.assigned_to_user_id == emp.id,
            ActionInboxItem.item_type == "profile_update",
            ActionInboxItem.related_entity_type == "employee",
            ActionInboxItem.related_entity_id == emp.id,
            ActionInboxItem.status == "pending",
        ).update(
            {
                ActionInboxItem.status: "completed",
                ActionInboxItem.updated_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
        db.query(Notification).filter(
            Notification.user_id == emp.id,
            Notification.notification_type == "profile_update",
            Notification.related_entity_type == "employee",
            Notification.related_entity_id == emp.id,
        ).delete(synchronize_session=False)
        db.commit()
        return {"success": True, "message": "Emergency contact details are already complete."}

    existing_action = db.query(ActionInboxItem).filter(
        ActionInboxItem.assigned_to_user_id == emp.id,
        ActionInboxItem.item_type == "profile_update",
        ActionInboxItem.related_entity_type == "employee",
        ActionInboxItem.related_entity_id == emp.id,
        ActionInboxItem.status == "pending",
    ).first()
    if not existing_action:
        db.add(ActionInboxItem(
            assigned_to_user_id=emp.id,
            item_type="profile_update",
            title="Update emergency contact",
            description="Please add or update your emergency contact details in My Profile.",
            status="pending",
            priority="normal",
            related_entity_type="employee",
            related_entity_id=emp.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ))

    # This is an action the employee must complete, so keep it in Inbox only.
    # Remove older duplicate notification reminders created before this was separated.
    db.query(Notification).filter(
        Notification.user_id == emp.id,
        Notification.notification_type == "profile_update",
        Notification.related_entity_type == "employee",
        Notification.related_entity_id == emp.id,
    ).delete(synchronize_session=False)
    log_sensitive_access(
        db,
        actor,
        action="emergency_contact_reminder_sent",
        target_type="employee",
        target_id=emp.id,
        sensitivity_level="restricted",
        reason="Admin requested employee emergency contact update",
    )
    log_audit(
        db,
        actor,
        action="employee.emergency_contact_reminder_sent",
        entity_type="employee",
        entity_id=emp.id,
        reason="Admin requested employee emergency contact update",
        metadata={"target_employee": f"{emp.first_name} {emp.last_name}".strip()},
    )
    db.commit()
    return {"success": True, "message": "Reminder sent to employee."}


@router.post("/", response_model=AddEmployeeResponse)
async def add_employee(
    data: AddEmployeeRequest,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    """Add a new employee with setup code for first-time login."""
    actor = require_admin_employee(db, current_user_id, current_user_email)
    try:
        result = create_employee(db, data)
        if result.success and result.employee_id:
            log_audit(
                db,
                actor,
                action="employee.created",
                entity_type="employee",
                entity_id=result.employee_id,
                new_values=data.model_dump(),
                metadata={"security_event": False},
            )
            db.commit()
        return result
    except Exception as e:
        logger.error(f"Error adding employee: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{employee_id}")
async def update_employee(
    employee_id: str,
    data: UpdateEmployeeRequest,
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
    current_user_name: str | None = Header(None, alias="x-user-name"),
    db: Session = Depends(get_db),
):
    """Update employee details. Current user must be the employee or an admin."""
    actor = get_current_employee(db, current_user_id, current_user_email)
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    is_self = actor.id == employee_id
    is_admin = is_admin_role(actor.role)

    if not (is_self or is_admin):
        log_authorization_failure(
            db,
            actor,
            action="employee.update",
            entity_type="employee",
            entity_id=employee_id,
            reason="User attempted to update an employee they do not own.",
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Not authorized to update this employee")

    updates = data.dict(exclude_unset=True)
    if is_self and not is_admin:
        blocked_fields = sorted(set(updates) - SELF_PROFILE_FIELDS)
        if blocked_fields:
            log_authorization_failure(
                db,
                actor,
                action="employee.update_restricted_fields",
                entity_type="employee",
                entity_id=employee_id,
                reason=f"Restricted fields attempted: {', '.join(blocked_fields)}",
            )
            db.commit()
            raise HTTPException(
                status_code=403,
                detail=f"Employees cannot modify restricted profile fields: {', '.join(blocked_fields)}.",
            )

    emergency_contact_fields = (
        "emergency_contact_name",
        "emergency_contact_phone",
        "emergency_contact_relation",
    )
    if any(field in updates for field in emergency_contact_fields):
        emergency_contact_values = {
            "Contact name": (updates.get("emergency_contact_name", emp.emergency_contact_name) or "").strip(),
            "Contact phone": (updates.get("emergency_contact_phone", emp.emergency_contact_phone) or "").strip(),
            "Relationship": (updates.get("emergency_contact_relation", emp.emergency_contact_relation) or "").strip(),
        }
        has_any_emergency_contact = any(emergency_contact_values.values())
        has_all_emergency_contact = all(emergency_contact_values.values())
        if has_any_emergency_contact and not has_all_emergency_contact:
            missing = [label for label, value in emergency_contact_values.items() if not value]
            raise HTTPException(
                status_code=422,
                detail=f"Emergency contact is incomplete. Missing: {', '.join(missing)}.",
            )

    old_values = {field: getattr(emp, field) for field in updates.keys() if hasattr(emp, field)}

    # Apply updates
    for field, value in updates.items():
        if hasattr(emp, field):
            setattr(emp, field, value)

    emp.last_updated_at = datetime.utcnow()
    emp.updated_by = changed_by_value(actor.work_email, current_user_name, actor.id)

    emergency_contact_complete = all([
        bool((emp.emergency_contact_name or "").strip()),
        bool((emp.emergency_contact_phone or "").strip()),
        bool((emp.emergency_contact_relation or "").strip()),
    ])
    if emergency_contact_complete:
        db.query(ActionInboxItem).filter(
            ActionInboxItem.assigned_to_user_id == emp.id,
            ActionInboxItem.item_type == "profile_update",
            ActionInboxItem.related_entity_type == "employee",
            ActionInboxItem.related_entity_id == emp.id,
            ActionInboxItem.status == "pending",
        ).update(
            {
                ActionInboxItem.status: "completed",
                ActionInboxItem.updated_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
        db.query(Notification).filter(
            Notification.user_id == emp.id,
            Notification.notification_type == "profile_update",
            Notification.related_entity_type == "employee",
            Notification.related_entity_id == emp.id,
        ).delete(synchronize_session=False)

    log_employee_changes(db, employee_id, old_values, updates, emp.updated_by)
    action = "user_profile_updated" if is_self and not is_admin else "employee.updated"
    field_changes = changed_fields(old_values, updates)
    if field_changes:
        log_audit(
            db,
            actor,
            action=action,
            entity_type="employee",
            entity_id=employee_id,
            old_values=old_values,
            new_values=updates,
            changed_fields_payload=field_changes,
            metadata={"changed_by": emp.updated_by},
        )

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
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
    current_user_name: str | None = Header(None, alias="x-user-name"),
    db: Session = Depends(get_db),
):
    """Upload profile picture for an employee. User can only upload for their own profile or super_admin can upload for anyone."""
    actor = get_current_employee(db, current_user_id, current_user_email)
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if actor.id != employee_id and not is_admin_role(actor.role):
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
    emp.updated_by = actor.work_email or current_user_name or actor.id or "unknown"
    log_audit(
        db,
        actor,
        action="employee.profile_picture_uploaded",
        entity_type="employee",
        entity_id=employee_id,
        old_values={"profile_image_url": "[IMAGE_PREVIOUS]"},
        new_values={"profile_image_url": "[IMAGE_UPDATED]"},
        metadata={"content_type": file.content_type, "file_size": len(file_content)},
    )
    db.commit()
    db.refresh(emp)

    return {
        "success": True,
        "message": "Profile picture uploaded successfully",
        "profile_image_url": emp.profile_image_url,
        "employee": serialize_employee(emp),
    }

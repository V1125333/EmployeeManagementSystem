"""
Action inbox and notification APIs.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.employee import Employee
from app.models.leave_attendance import AttendanceCorrection, LeaveBalance, LeaveRequest, LeaveType
from app.models.operations import ActionInboxItem, Notification
from app.services.settings_service import get_current_employee, is_manager_or_admin_role, is_admin_role

router = APIRouter(tags=["Inbox & Notifications"])
MANAGER_ROLES = {"super_admin", "admin", "hr_admin", "global_access", "manager"}


def normalize_role(role: str | None) -> str:
    return (role or "").strip().lower().replace(" ", "_")


def numeric(value) -> float:
    return float(value or 0)


def has_complete_emergency_contact(employee: Employee | None) -> bool:
    if not employee:
        return False
    return all([
        bool((employee.emergency_contact_name or "").strip()),
        bool((employee.emergency_contact_phone or "").strip()),
        bool((employee.emergency_contact_relation or "").strip()),
    ])


def current_employee(db: Session, user_id: str | None, user_email: str | None) -> Employee | None:
    employee = None
    if user_id:
        employee = db.query(Employee).filter(Employee.id == user_id).first()
    if not employee and user_email:
        employee = db.query(Employee).filter(
            func.lower(Employee.work_email) == user_email.strip().lower()
        ).first()
    return employee


def actor_context(db: Session, user_id: str | None, user_email: str | None):
    employee = get_current_employee(db, user_id, user_email)
    return employee, normalize_role(employee.role)


def serialize_notification(item: Notification) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "message": item.message,
        "notification_type": item.notification_type or item.type,
        "type": item.type,
        "related_entity_type": item.related_entity_type,
        "related_entity_id": item.related_entity_id,
        "is_read": item.is_read,
        "link_url": item.link_url,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def serialize_action_item(item: ActionInboxItem, employee_name: str | None = None) -> dict:
    return {
        "id": item.id,
        "item_type": item.item_type,
        "type": item.item_type,
        "title": item.title,
        "description": item.description,
        "employee_name": employee_name,
        "status": item.status,
        "priority": item.priority,
        "related_entity_type": item.related_entity_type,
        "related_entity_id": item.related_entity_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def employee_name(db: Session, employee_id: str) -> str:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return "Unknown employee"
    return f"{employee.first_name} {employee.last_name}"


def create_notification(
    db: Session,
    user_id: str,
    title: str,
    message: str,
    notification_type: str,
    related_entity_type: str,
    related_entity_id: str,
) -> None:
    db.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type,
        notification_type=notification_type,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    ))


def manager_action_items(db: Session, actor: Employee) -> list[dict]:
    items: list[dict] = []
    pending_leave_query = db.query(LeaveRequest).filter(LeaveRequest.status == "pending")
    if not is_admin_role(actor.role):
        pending_leave_query = pending_leave_query.join(Employee, Employee.id == LeaveRequest.employee_id).filter(
            Employee.reporting_manager == f"{actor.first_name} {actor.last_name}".strip(),
        )
    pending_leaves = pending_leave_query.order_by(LeaveRequest.created_at.desc()).limit(10).all()
    for leave in pending_leaves:
        items.append({
            "id": f"leave:{leave.id}",
            "item_type": "leave_request",
            "type": "Leave Request",
            "title": "Leave approval required",
            "description": f"{leave.start_date} to {leave.end_date} ({leave.total_days} days)",
            "employee_name": employee_name(db, leave.employee_id),
            "status": leave.status,
            "priority": "normal",
            "related_entity_type": "leave_request",
            "related_entity_id": leave.id,
            "created_at": leave.created_at.isoformat() if leave.created_at else None,
        })

    corrections_query = db.query(AttendanceCorrection).filter(AttendanceCorrection.status == "pending")
    if not is_admin_role(actor.role):
        corrections_query = corrections_query.join(Employee, Employee.id == AttendanceCorrection.employee_id).filter(
            Employee.reporting_manager == f"{actor.first_name} {actor.last_name}".strip(),
        )
    corrections = corrections_query.order_by(AttendanceCorrection.created_at.desc()).limit(10).all()
    for correction in corrections:
        items.append({
            "id": f"attendance:{correction.id}",
            "item_type": "attendance_correction",
            "type": "Attendance Correction",
            "title": "Attendance correction requested",
            "description": correction.reason,
            "employee_name": employee_name(db, correction.employee_id),
            "status": correction.status,
            "priority": "normal",
            "related_entity_type": "attendance_correction",
            "related_entity_id": correction.id,
            "created_at": correction.created_at.isoformat() if correction.created_at else None,
        })
    return items


@router.get("/inbox")
async def get_inbox(
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    employee, role = actor_context(db, current_user_id, current_user_email)
    items: list[dict] = []

    if employee:
        stored_items = db.query(ActionInboxItem).filter(
            ActionInboxItem.assigned_to_user_id == employee.id,
            ActionInboxItem.status == "pending",
        ).order_by(ActionInboxItem.created_at.desc()).all()
        stale_profile_items = [
            item for item in stored_items
            if item.item_type == "profile_update"
            and item.related_entity_type == "employee"
            and item.related_entity_id == employee.id
            and has_complete_emergency_contact(employee)
        ]
        if stale_profile_items:
            for item in stale_profile_items:
                item.status = "completed"
                item.updated_at = datetime.utcnow()
            db.query(Notification).filter(
                Notification.user_id == employee.id,
                Notification.notification_type == "profile_update",
                Notification.related_entity_type == "employee",
                Notification.related_entity_id == employee.id,
            ).delete(synchronize_session=False)
            db.commit()

        items.extend(
            serialize_action_item(item)
            for item in stored_items
            if item.status == "pending"
        )

    if role in MANAGER_ROLES:
        items.extend(manager_action_items(db, employee))

    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return {"items": items[:20]}


@router.get("/inbox/count")
async def get_inbox_count(
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    data = await get_inbox(current_user_id, current_user_email, db)
    return {"count": len(data["items"])}


@router.post("/inbox/{item_id}/complete")
async def complete_inbox_item(
    item_id: str,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    employee = current_employee(db, current_user_id, current_user_email)
    if not employee:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    item = db.query(ActionInboxItem).filter(
        ActionInboxItem.id == item_id,
        ActionInboxItem.assigned_to_user_id == employee.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    item.status = "completed"
    item.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True}


@router.post("/inbox/leave-requests/{request_id}/{decision}")
async def decide_leave_request(
    request_id: str,
    decision: str,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    reviewer, role = actor_context(db, current_user_id, current_user_email)
    if not is_manager_or_admin_role(reviewer.role):
        raise HTTPException(status_code=403, detail="Not authorized to review leave requests")
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Decision must be approve or reject")

    leave = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status != "pending":
        raise HTTPException(status_code=400, detail="Leave request is no longer pending")
    employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if leave.employee_id == reviewer.id:
        raise HTTPException(status_code=403, detail="You cannot review your own leave request")
    if not is_admin_role(reviewer.role) and employee.reporting_manager != f"{reviewer.first_name} {reviewer.last_name}".strip():
        raise HTTPException(status_code=403, detail="Not authorized to review this employee's leave request")

    new_status = "approved" if decision == "approve" else "rejected"
    leave.status = new_status
    leave.reviewed_by = reviewer.id if reviewer else current_user_id
    leave.reviewed_at = datetime.utcnow()
    leave.updated_at = datetime.utcnow()
    if decision == "approve":
        leave_type = db.query(LeaveType).filter(LeaveType.id == leave.leave_type_id).first()
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == leave.employee_id,
            LeaveBalance.leave_type_id == leave.leave_type_id,
            LeaveBalance.year == leave.start_date.year,
        ).first()
        if not balance and leave_type:
            balance = LeaveBalance(
                employee_id=leave.employee_id,
                leave_type_id=leave.leave_type_id,
                year=leave.start_date.year,
                total_days=leave_type.default_days_per_year,
                used_days=0,
                carry_forward_days=0,
            )
            db.add(balance)
            db.flush()
        if balance:
            balance.used_days = numeric(balance.used_days) + numeric(leave.total_days)
            balance.updated_at = datetime.utcnow()
    create_notification(
        db,
        leave.employee_id,
        f"Leave request {new_status}",
        f"Your leave request from {leave.start_date} to {leave.end_date} was {new_status}.",
        "leave",
        "leave_request",
        leave.id,
    )
    db.commit()
    return {"success": True, "status": new_status}


@router.post("/inbox/attendance-corrections/{correction_id}/{decision}")
async def decide_attendance_correction(
    correction_id: str,
    decision: str,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    reviewer, role = actor_context(db, current_user_id, current_user_email)
    if not is_manager_or_admin_role(reviewer.role):
        raise HTTPException(status_code=403, detail="Not authorized to review attendance corrections")
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Decision must be approve or reject")

    correction = db.query(AttendanceCorrection).filter(AttendanceCorrection.id == correction_id).first()
    if not correction:
        raise HTTPException(status_code=404, detail="Attendance correction not found")
    if correction.status != "pending":
        raise HTTPException(status_code=400, detail="Attendance correction is no longer pending")
    employee = db.query(Employee).filter(Employee.id == correction.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if correction.employee_id == reviewer.id:
        raise HTTPException(status_code=403, detail="You cannot review your own attendance correction")
    if not is_admin_role(reviewer.role) and employee.reporting_manager != f"{reviewer.first_name} {reviewer.last_name}".strip():
        raise HTTPException(status_code=403, detail="Not authorized to review this employee's attendance correction")

    new_status = "approved" if decision == "approve" else "rejected"
    correction.status = new_status
    correction.reviewed_by = reviewer.id if reviewer else current_user_id
    correction.reviewed_at = datetime.utcnow()
    correction.updated_at = datetime.utcnow()
    create_notification(
        db,
        correction.employee_id,
        f"Attendance correction {new_status}",
        f"Your attendance correction request was {new_status}.",
        "attendance",
        "attendance_correction",
        correction.id,
    )
    db.commit()
    return {"success": True, "status": new_status}


@router.get("/notifications")
async def get_notifications(
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    employee = current_employee(db, current_user_id, current_user_email)
    if not employee:
        return {"notifications": []}
    query = db.query(Notification).filter(Notification.user_id == employee.id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return {"notifications": [serialize_notification(item) for item in notifications]}


@router.get("/notifications/unread-count")
async def get_unread_count(
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    employee = current_employee(db, current_user_id, current_user_email)
    if not employee:
        return {"count": 0}
    count = db.query(Notification).filter(Notification.user_id == employee.id, Notification.is_read == False).count()
    return {"count": count}


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    employee = current_employee(db, current_user_id, current_user_email)
    if not employee:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == employee.id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    return {"success": True}


@router.put("/notifications/mark-all-read")
async def mark_all_notifications_read(
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    employee = current_employee(db, current_user_id, current_user_email)
    if not employee:
        return {"success": True}
    db.query(Notification).filter(Notification.user_id == employee.id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"success": True}

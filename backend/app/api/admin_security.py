"""
Admin security operations: locked accounts and unlock request review.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.employee import Employee
from app.models.unlock_request import AccountUnlockRequest
from app.schemas.employee import ReviewUnlockRequest
from app.services.auth_service import approve_unlock, direct_unlock, reject_unlock
from app.services.settings_service import get_current_employee, is_admin_role

router = APIRouter(prefix="/admin/security", tags=["Admin Security"])


def require_security_admin(db: Session, user_id: str | None, user_email: str | None) -> Employee:
    actor = get_current_employee(db, user_id, user_email)
    if not is_admin_role(actor.role):
        raise HTTPException(status_code=403, detail="Only Super Admin, Admin, and HR can access security administration.")
    return actor


def employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown employee"
    return f"{employee.first_name} {employee.last_name}".strip() or employee.work_email


def serialize_locked_employee(employee: Employee) -> dict:
    return {
        "id": employee.id,
        "name": employee_name(employee),
        "email": employee.work_email,
        "department": employee.department,
        "role": employee.role,
        "locked_at": employee.locked_at.isoformat() if employee.locked_at else None,
        "locked_reason": employee.locked_reason,
        "failed_login_attempts": employee.failed_login_attempts or 0,
    }


def serialize_request(db: Session, row: AccountUnlockRequest) -> dict:
    target = db.query(Employee).filter(Employee.id == row.locked_user_id).first()
    requester = db.query(Employee).filter(Employee.id == row.requested_by_user_id).first() if row.requested_by_user_id else None
    reviewer = db.query(Employee).filter(Employee.id == row.reviewed_by_user_id).first() if row.reviewed_by_user_id else None
    return {
        "id": row.id,
        "locked_user_id": row.locked_user_id,
        "employee_name": employee_name(target),
        "employee_email": target.work_email if target else row.requested_email,
        "requested_by": employee_name(requester) if requester else "Self / Login screen",
        "requested_email": row.requested_email,
        "reason": row.request_reason,
        "status": row.status,
        "reviewed_by": employee_name(reviewer) if reviewer else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "admin_notes": row.admin_notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/locked-accounts")
async def locked_accounts(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    require_security_admin(db, x_user_id, x_user_email)
    query = db.query(Employee).filter(Employee.account_locked == True).order_by(Employee.locked_at.desc().nullslast())
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": [serialize_locked_employee(row) for row in rows], "total": total, "page": page, "per_page": per_page}


@router.get("/unlock-requests")
async def unlock_requests(
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    require_security_admin(db, x_user_id, x_user_email)
    query = db.query(AccountUnlockRequest)
    if status != "all":
        query = query.filter(AccountUnlockRequest.status == status)
    query = query.order_by(AccountUnlockRequest.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": [serialize_request(db, row) for row in rows], "total": total, "page": page, "per_page": per_page}


@router.post("/unlock-requests/{request_id}/approve")
async def approve_unlock_request(
    request_id: str,
    payload: ReviewUnlockRequest,
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    actor = require_security_admin(db, x_user_id, x_user_email)
    return approve_unlock(db, actor, request_id, payload.admin_notes)


@router.post("/unlock-requests/{request_id}/reject")
async def reject_unlock_request(
    request_id: str,
    payload: ReviewUnlockRequest,
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    actor = require_security_admin(db, x_user_id, x_user_email)
    return reject_unlock(db, actor, request_id, payload.admin_notes)


@router.post("/locked-accounts/{employee_id}/unlock")
async def unlock_locked_account(
    employee_id: str,
    payload: ReviewUnlockRequest,
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    actor = require_security_admin(db, x_user_id, x_user_email)
    return direct_unlock(db, actor, employee_id, payload.admin_notes)


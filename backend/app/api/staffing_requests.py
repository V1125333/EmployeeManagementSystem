from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditLog
from app.models.employee import Employee
from app.models.allocation import Allocation
from app.models.operations import Project
from app.models.organization import Department, Designation
from app.models.staffing_request import StaffingRequest, StaffingRequestCandidate
from app.schemas.staffing_request import (
    CandidateOut,
    CreateAllocationFromRequestBody,
    StaffingRequestCreate,
    StaffingFulfillmentResult,
    StaffingRequestListResponse,
    StaffingRequestOptions,
    StaffingRequestOut,
    StaffingRequestStatusUpdate,
    StaffingRequestUpdate,
)
from app.services.audit_service import log_audit, log_authorization_failure
from app.services.settings_service import get_current_employee, normalize_role
from app.services.staffing_service import (
    cancel_request,
    change_status,
    create_staffing_request,
    refresh_system_candidates,
    reject_candidate,
    select_candidate,
    serialize_candidate,
    serialize_request,
    serialize_summary,
    shortlist_candidate,
    update_staffing_request,
    fulfilled_allocation_ids,
)
from app.services.allocation_service import serialize_allocation
from app.services.staffing_allocation_service import create_allocation_from_staffing_request

router = APIRouter(prefix="/staffing-requests", tags=["Staffing Requests"])


def _is_hr_admin(actor: Employee) -> bool:
    return normalize_role(actor.role) in {"super_admin", "hr_admin", "admin", "global_access"}


def _is_manager(actor: Employee) -> bool:
    return normalize_role(actor.role) == "manager"


def _actor_name(actor: Employee) -> str:
    parts = [actor.first_name, getattr(actor, "middle_name", None), actor.last_name]
    return " ".join(part.strip() for part in parts if part and part.strip())


def _require_module_access(db: Session, actor: Employee) -> None:
    if _is_hr_admin(actor) or _is_manager(actor):
        return
    log_authorization_failure(
        db,
        actor,
        action="staffing_request.access",
        entity_type="staffing_request",
        entity_id=actor.id,
        reason="Employee attempted to access staffing request module.",
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Staffing Requests are available only to managers, HR, and admins.")


def _scope_query(db: Session, actor: Employee):
    query = db.query(StaffingRequest)
    if _is_hr_admin(actor):
        return query
    return query.filter(or_(StaffingRequest.requested_by == actor.id, StaffingRequest.hiring_manager_id == actor.id))


def _get_request_or_404(db: Session, request_id: str) -> StaffingRequest:
    row = db.query(StaffingRequest).filter(StaffingRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Staffing request not found.")
    return row


def _require_request_read(db: Session, actor: Employee, row: StaffingRequest) -> None:
    _require_module_access(db, actor)
    if _is_hr_admin(actor) or row.requested_by == actor.id or row.hiring_manager_id == actor.id:
        return
    log_authorization_failure(
        db,
        actor,
        action="staffing_request.read",
        entity_type="staffing_request",
        entity_id=row.id,
        reason="Manager attempted to read staffing request outside their scope.",
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Not authorized to view this staffing request.")


def _require_request_edit(db: Session, actor: Employee, row: StaffingRequest) -> None:
    _require_request_read(db, actor, row)
    if _is_hr_admin(actor):
        return
    if row.requested_by == actor.id and row.status == "open":
        return
    log_authorization_failure(
        db,
        actor,
        action="staffing_request.write",
        entity_type="staffing_request",
        entity_id=row.id,
        reason="Manager attempted to edit a request that is not open or not owned by them.",
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Managers can edit only their own open staffing requests.")


def _require_hr_action(db: Session, actor: Employee, row: StaffingRequest, action: str) -> None:
    _require_request_read(db, actor, row)
    if _is_hr_admin(actor):
        return
    log_authorization_failure(
        db,
        actor,
        action=action,
        entity_type="staffing_request",
        entity_id=row.id,
        reason="Non-HR user attempted an HR staffing request action.",
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Only HR and admins can perform this action.")


def _require_hr_only(db: Session, actor: Employee, action: str, entity_id: str | None = None) -> None:
    if normalize_role(actor.role) in {"super_admin", "hr_admin", "global_access"}:
        return
    log_authorization_failure(
        db,
        actor,
        action=action,
        entity_type="staffing_request",
        entity_id=entity_id or actor.id,
        reason="Non-HR user attempted an HR-only staffing fulfillment action.",
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Only HR and admins can perform this action.")


def _employee_option(employee: Employee) -> dict[str, Any]:
    return {
        "id": employee.id,
        "name": _actor_name(employee),
        "email": employee.work_email,
        "department": employee.department,
        "designation": employee.designation,
        "role": employee.role,
    }


def _audit_row(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "action": row.action,
        "old_values": row.old_values,
        "new_values": row.new_values,
        "metadata": row.metadata_json,
        "performed_by": row.actor_name,
        "performed_at": row.created_at,
    }


@router.get("/options", response_model=StaffingRequestOptions)
async def staffing_request_options(
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_module_access(db, actor)

    departments = [item.name for item in db.query(Department).order_by(Department.sort_order.asc(), Department.name.asc()).all()]
    designations = [item.name for item in db.query(Designation).order_by(Designation.level.asc(), Designation.name.asc()).all()]
    employees = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai").order_by(Employee.first_name.asc(), Employee.last_name.asc()).all()
    managers = [
        _employee_option(employee)
        for employee in employees
        if normalize_role(employee.role) in {"manager", "hr_admin", "admin", "super_admin", "global_access"}
    ]
    projects = [
        {"id": item.id, "name": item.name, "code": item.code, "status": item.status}
        for item in db.query(Project).order_by(Project.name.asc()).all()
    ]
    return {
        "departments": departments,
        "designations": designations,
        "managers": managers,
        "projects": projects,
        "employees": [_employee_option(employee) for employee in employees],
    }


@router.get("/", response_model=StaffingRequestListResponse)
async def list_staffing_requests(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    department: str | None = Query(None),
    role_needed: str | None = Query(None),
    project_name: str | None = Query(None),
    hiring_manager_id: str | None = Query(None),
    start_date_from: str | None = Query(None),
    start_date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_module_access(db, actor)
    query = _scope_query(db, actor)

    if status:
        statuses = [item.strip() for item in status.split(",") if item.strip()]
        if statuses:
            query = query.filter(StaffingRequest.status.in_(statuses))
    if priority:
        query = query.filter(StaffingRequest.priority == priority)
    if department:
        query = query.filter(StaffingRequest.department.ilike(department))
    if role_needed:
        query = query.filter(StaffingRequest.role_needed.ilike(f"%{role_needed}%"))
    if project_name:
        query = query.filter(StaffingRequest.project_name.ilike(f"%{project_name}%"))
    if hiring_manager_id:
        query = query.filter(StaffingRequest.hiring_manager_id == hiring_manager_id)
    if start_date_from:
        query = query.filter(StaffingRequest.start_date >= start_date_from)
    if start_date_to:
        query = query.filter(StaffingRequest.start_date <= start_date_to)

    total = query.count()
    rows = query.order_by(StaffingRequest.updated_at.desc(), StaffingRequest.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {"items": [serialize_summary(db, row) for row in rows], "total": total, "page": page, "per_page": per_page}


@router.post("/", response_model=StaffingRequestOut)
async def create_staffing_request_endpoint(
    data: StaffingRequestCreate,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_module_access(db, actor)
    return create_staffing_request(db, data, actor.id)


@router.get("/{request_id}", response_model=StaffingRequestOut)
async def get_staffing_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_request_read(db, actor, row)
    return serialize_request(db, row, include_candidates=True)


@router.patch("/{request_id}", response_model=StaffingRequestOut)
async def update_staffing_request_endpoint(
    request_id: str,
    data: StaffingRequestUpdate,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_request_edit(db, actor, row)
    return update_staffing_request(db, request_id, data, actor.id)


@router.patch("/{request_id}/status", response_model=StaffingRequestOut)
async def update_staffing_request_status(
    request_id: str,
    data: StaffingRequestStatusUpdate,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_hr_action(db, actor, row, "staffing_request.status")
    return change_status(db, request_id, data.status, data.rejection_reason, actor.id)


@router.delete("/{request_id}", response_model=StaffingRequestOut)
async def cancel_staffing_request_endpoint(
    request_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_request_edit(db, actor, row)
    return cancel_request(db, request_id, actor.id)


@router.get("/{request_id}/candidates", response_model=list[CandidateOut])
async def get_staffing_candidates(
    request_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_request_read(db, actor, row)
    candidates = db.query(StaffingRequestCandidate).filter(
        StaffingRequestCandidate.staffing_request_id == request_id,
    ).order_by(StaffingRequestCandidate.created_at.asc()).all()
    return [serialize_candidate(db, item) for item in candidates]


@router.post("/{request_id}/create-allocation", response_model=StaffingFulfillmentResult)
async def create_allocation_from_request_endpoint(
    request_id: str,
    data: CreateAllocationFromRequestBody,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_hr_only(db, actor, "staffing_request.create_allocation", request_id)
    return create_allocation_from_staffing_request(
        db,
        staffing_request_id=request_id,
        employee_id=data.employee_id,
        actor_id=actor.id,
        overrides=data.overrides,
    )


@router.get("/{request_id}/allocations")
async def get_staffing_request_allocations(
    request_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_request_read(db, actor, row)
    allocation_ids = fulfilled_allocation_ids(row)
    if not allocation_ids:
        return []
    allocations = db.query(Allocation).filter(Allocation.id.in_(allocation_ids)).order_by(Allocation.created_at.desc()).all()
    return [serialize_allocation(db, allocation) for allocation in allocations]


@router.post("/{request_id}/candidates/refresh", response_model=StaffingRequestOut)
async def refresh_staffing_candidates(
    request_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_hr_action(db, actor, row, "staffing_request.candidates.refresh")
    refresh_system_candidates(db, row)
    row.updated_by = actor.id
    row.updated_at = datetime.utcnow()
    log_audit(db, actor, "staffing_candidates_refreshed", "staffing_request", row.id, metadata={"actor": actor.id, "changed_at": datetime.utcnow().isoformat()})
    db.commit()
    return serialize_request(db, row, include_candidates=True)


@router.post("/{request_id}/candidates/{employee_id}/shortlist", response_model=StaffingRequestOut)
async def shortlist_staffing_candidate(
    request_id: str,
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_hr_action(db, actor, row, "staffing_request.candidates.shortlist")
    return shortlist_candidate(db, request_id, employee_id, actor.id)


@router.post("/{request_id}/candidates/{employee_id}/select", response_model=StaffingRequestOut)
async def select_staffing_candidate(
    request_id: str,
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_hr_action(db, actor, row, "staffing_request.candidates.select")
    return select_candidate(db, request_id, employee_id, actor.id)


@router.post("/{request_id}/candidates/{employee_id}/reject", response_model=StaffingRequestOut)
async def reject_staffing_candidate(
    request_id: str,
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_hr_action(db, actor, row, "staffing_request.candidates.reject")
    return reject_candidate(db, request_id, employee_id, actor.id)


@router.get("/{request_id}/activity")
async def staffing_request_activity(
    request_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    row = _get_request_or_404(db, request_id)
    _require_request_read(db, actor, row)
    logs = db.query(AuditLog).filter(
        AuditLog.entity_type == "staffing_request",
        AuditLog.entity_id == request_id,
    ).order_by(AuditLog.performed_at.desc()).all()
    return [_audit_row(item) for item in logs]

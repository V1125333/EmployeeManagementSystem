from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.operations import Project
from app.models.staffing_request import StaffingRequest, StaffingRequestCandidate
from app.schemas.staffing_request import StaffingRequestCreate, StaffingRequestOut, StaffingRequestUpdate
from app.services.allocation_service import get_allocation_summary
from app.services.audit_service import log_audit
from app.services.settings_service import normalize_role


PRIORITIES = {"low", "medium", "high", "urgent"}
STATUSES = {"open", "in_review", "fulfilled", "partially_fulfilled", "cancelled", "rejected"}
TERMINAL_STATUSES = {"fulfilled", "cancelled", "rejected"}
ALLOWED_TRANSITIONS = {
    "open": {"in_review", "cancelled", "rejected"},
    "in_review": {"open", "fulfilled", "partially_fulfilled", "cancelled", "rejected"},
    "partially_fulfilled": {"fulfilled", "cancelled"},
    "fulfilled": set(),
    "cancelled": set(),
    "rejected": set(),
}


@dataclass
class CandidateMatch:
    employee_id: str
    available_capacity_percentage: int
    current_allocation_percentage: int
    next_available_date: Any
    designation_rank: int
    department_rank: int


def employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown"
    middle_name = getattr(employee, "middle_name", None)
    parts = [employee.first_name, middle_name, employee.last_name]
    return " ".join(part.strip() for part in parts if part and part.strip()) or employee.work_email


def fulfilled_allocation_ids(row: StaffingRequest) -> list[str]:
    value = row.fulfilled_allocation_ids or []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return list(value)


def _values(row: StaffingRequest) -> dict[str, Any]:
    return {
        "project_id": row.project_id,
        "project_name": row.project_name,
        "hiring_manager_id": row.hiring_manager_id,
        "department": row.department,
        "role_needed": row.role_needed,
        "designation_needed": row.designation_needed,
        "skills_required": row.skills_required or [],
        "allocation_percentage": row.allocation_percentage,
        "headcount_needed": row.headcount_needed,
        "headcount_fulfilled": row.headcount_fulfilled,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "priority": row.priority,
        "status": row.status,
        "reason": row.reason,
        "notes": row.notes,
        "rejection_reason": row.rejection_reason,
        "fulfilled_allocation_ids": fulfilled_allocation_ids(row),
        "fulfilled_at": row.fulfilled_at,
        "fulfilled_by": row.fulfilled_by,
    }


def validate_request_data(db: Session, values: dict[str, Any]) -> None:
    if not (values.get("project_name") or "").strip():
        raise HTTPException(status_code=422, detail="Project name is required.")
    if not (values.get("role_needed") or "").strip():
        raise HTTPException(status_code=422, detail="Role needed is required.")
    allocation_percentage = values.get("allocation_percentage")
    if allocation_percentage is None or allocation_percentage < 1 or allocation_percentage > 100:
        raise HTTPException(status_code=422, detail="Allocation percentage must be between 1 and 100.")
    headcount_needed = values.get("headcount_needed")
    if headcount_needed is None or headcount_needed < 1:
        raise HTTPException(status_code=422, detail="Headcount needed must be at least 1.")
    if not values.get("start_date"):
        raise HTTPException(status_code=422, detail="Start date is required.")
    if values.get("end_date") and values["end_date"] < values["start_date"]:
        raise HTTPException(status_code=422, detail="End date must be on or after start date.")
    if values.get("priority") not in PRIORITIES:
        raise HTTPException(status_code=422, detail="Priority must be low, medium, high, or urgent.")

    hiring_manager = db.query(Employee).filter(Employee.id == values.get("hiring_manager_id")).first()
    if not hiring_manager:
        raise HTTPException(status_code=422, detail="Hiring manager must reference an existing employee.")
    if normalize_role(hiring_manager.role) not in {"manager", "hr_admin", "super_admin", "admin", "global_access"}:
        raise HTTPException(status_code=422, detail="Hiring manager must be a manager, HR admin, admin, or super admin.")


def candidate_snapshot(db: Session, employee_id: str) -> dict[str, Any]:
    summary = get_allocation_summary(db, employee_id)
    return {
        "available_capacity_percentage": int(summary["available_capacity_percentage"]),
        "current_allocation_percentage": int(summary["total_active_allocation_percentage"]),
        "next_available_date": summary["next_end_date"],
    }


def find_candidates(db: Session, staffing_request: StaffingRequest) -> list[CandidateMatch]:
    employees = db.query(Employee).filter(
        Employee.work_email != "superadmin@reknew.ai",
        Employee.is_active == True,  # noqa: E712
    ).order_by(Employee.first_name.asc(), Employee.last_name.asc()).all()
    matches: list[CandidateMatch] = []
    needed_designation = (staffing_request.designation_needed or "").strip().lower()
    needed_department = (staffing_request.department or "").strip().lower()

    for employee in employees:
        summary = get_allocation_summary(db, employee.id)
        available = int(summary["available_capacity_percentage"])
        current = int(summary["total_active_allocation_percentage"])
        next_end = summary["next_end_date"]
        include = (
            available >= staffing_request.allocation_percentage
            or (next_end is not None and next_end <= staffing_request.start_date)
            or (0 < available < staffing_request.allocation_percentage)
        )
        if not include:
            continue

        employee_designation = (employee.designation or "").strip().lower()
        employee_department = (employee.department or "").strip().lower()
        if needed_designation and employee_designation == needed_designation:
            designation_rank = 0
        elif needed_designation and (needed_designation in employee_designation or employee_designation in needed_designation):
            designation_rank = 1
        else:
            designation_rank = 2
        department_rank = 0 if needed_department and employee_department == needed_department else 1
        matches.append(CandidateMatch(employee.id, available, current, next_end, designation_rank, department_rank))

    matches.sort(key=lambda item: (
        -item.available_capacity_percentage,
        item.next_available_date is None,
        item.next_available_date,
        item.designation_rank,
        item.department_rank,
    ))
    return matches[:20]


def refresh_system_candidates(db: Session, staffing_request: StaffingRequest) -> None:
    db.query(StaffingRequestCandidate).filter(
        StaffingRequestCandidate.staffing_request_id == staffing_request.id,
        StaffingRequestCandidate.suggested_by == "system",
        StaffingRequestCandidate.match_status != "selected",
    ).delete(synchronize_session=False)
    db.flush()
    existing_employee_ids = {
        row.employee_id for row in db.query(StaffingRequestCandidate).filter(
            StaffingRequestCandidate.staffing_request_id == staffing_request.id,
        ).all()
    }
    for match in find_candidates(db, staffing_request):
        if match.employee_id in existing_employee_ids:
            continue
        db.add(StaffingRequestCandidate(
            staffing_request_id=staffing_request.id,
            employee_id=match.employee_id,
            match_status="suggested",
            available_capacity_percentage=match.available_capacity_percentage,
            current_allocation_percentage=match.current_allocation_percentage,
            next_available_date=match.next_available_date,
            suggested_by="system",
        ))


def serialize_candidate(db: Session, row: StaffingRequestCandidate) -> dict[str, Any]:
    employee = db.query(Employee).filter(Employee.id == row.employee_id).first()
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "allocation_id": row.allocation_id,
        "employee_name": employee_name(employee),
        "department": employee.department if employee else None,
        "designation": employee.designation if employee else None,
        "profile_image_url": employee.profile_image_url if employee else None,
        "match_status": row.match_status,
        "available_capacity_percentage": row.available_capacity_percentage,
        "current_allocation_percentage": row.current_allocation_percentage,
        "next_available_date": row.next_available_date,
        "suggested_by": row.suggested_by,
        "notes": row.notes,
        "created_at": row.created_at,
    }


def serialize_request(db: Session, row: StaffingRequest, include_candidates: bool = False) -> StaffingRequestOut:
    requested_by = db.query(Employee).filter(Employee.id == row.requested_by).first()
    hiring_manager = db.query(Employee).filter(Employee.id == row.hiring_manager_id).first()
    fulfilled_by = db.query(Employee).filter(Employee.id == row.fulfilled_by).first() if row.fulfilled_by else None
    candidates = []
    if include_candidates:
        candidate_rows = db.query(StaffingRequestCandidate).filter(
            StaffingRequestCandidate.staffing_request_id == row.id,
        ).order_by(StaffingRequestCandidate.created_at.asc()).all()
        candidates = [serialize_candidate(db, item) for item in candidate_rows]
    return StaffingRequestOut(
        id=row.id,
        project_name=row.project_name,
        project_id=row.project_id,
        requested_by_name=employee_name(requested_by),
        hiring_manager_id=row.hiring_manager_id,
        hiring_manager_name=employee_name(hiring_manager),
        department=row.department,
        role_needed=row.role_needed,
        designation_needed=row.designation_needed,
        skills_required=row.skills_required or [],
        allocation_percentage=row.allocation_percentage,
        headcount_needed=row.headcount_needed,
        headcount_fulfilled=row.headcount_fulfilled,
        start_date=row.start_date,
        end_date=row.end_date,
        priority=row.priority,
        status=row.status,
        reason=row.reason,
        notes=row.notes,
        rejection_reason=row.rejection_reason,
        fulfilled_allocation_ids=fulfilled_allocation_ids(row),
        fulfilled_at=row.fulfilled_at,
        fulfilled_by=row.fulfilled_by,
        fulfilled_by_name=employee_name(fulfilled_by) if fulfilled_by else None,
        candidates=candidates,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def serialize_summary(db: Session, row: StaffingRequest) -> dict[str, Any]:
    requested_by = db.query(Employee).filter(Employee.id == row.requested_by).first()
    hiring_manager = db.query(Employee).filter(Employee.id == row.hiring_manager_id).first()
    return {
        "id": row.id,
        "project_name": row.project_name,
        "project_id": row.project_id,
        "role_needed": row.role_needed,
        "allocation_percentage": row.allocation_percentage,
        "headcount_needed": row.headcount_needed,
        "headcount_fulfilled": row.headcount_fulfilled,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "priority": row.priority,
        "status": row.status,
        "requested_by_name": employee_name(requested_by),
        "hiring_manager_name": employee_name(hiring_manager),
        "created_at": row.created_at,
    }


def create_staffing_request(db: Session, data: StaffingRequestCreate, created_by_id: str) -> StaffingRequestOut:
    values = data.model_dump()
    validate_request_data(db, values)
    row = StaffingRequest(
        **values,
        requested_by=created_by_id,
        created_by=created_by_id,
        status="open",
        headcount_fulfilled=0,
        skills_required=values.get("skills_required") or [],
    )
    db.add(row)
    db.flush()
    refresh_system_candidates(db, row)
    log_audit(db, db.query(Employee).filter(Employee.id == created_by_id).first(), "staffing_request_created", "staffing_request", row.id, new_values=_values(row), metadata={"changed_at": datetime.utcnow().isoformat(), "actor": created_by_id})
    db.commit()
    return serialize_request(db, row, include_candidates=True)


def update_staffing_request(db: Session, request_id: str, data: StaffingRequestUpdate, updated_by_id: str) -> StaffingRequestOut:
    row = db.query(StaffingRequest).filter(StaffingRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Staffing request not found.")
    old_values = _values(row)
    patch = data.model_dump(exclude_unset=True)
    merged = {**old_values, **patch}
    validate_request_data(db, merged)
    rerun_fields = {"allocation_percentage", "start_date", "end_date", "role_needed", "designation_needed", "department"}
    should_refresh = bool(rerun_fields.intersection(patch.keys()))
    for key, value in patch.items():
        setattr(row, key, value)
    row.updated_by = updated_by_id
    row.updated_at = datetime.utcnow()
    if row.skills_required is None:
        row.skills_required = []
    if should_refresh:
        db.flush()
        refresh_system_candidates(db, row)
    new_values = _values(row)
    log_audit(db, db.query(Employee).filter(Employee.id == updated_by_id).first(), "staffing_request_updated", "staffing_request", row.id, old_values=old_values, new_values=new_values, metadata={"changed_at": datetime.utcnow().isoformat(), "actor": updated_by_id, "changed_fields": sorted(patch.keys())})
    db.commit()
    return serialize_request(db, row, include_candidates=True)


def change_status(db: Session, request_id: str, new_status: str, rejection_reason: str | None, actor_id: str) -> StaffingRequestOut:
    row = db.query(StaffingRequest).filter(StaffingRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Staffing request not found.")
    if new_status not in STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported staffing request status.")
    if row.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=422, detail=f"{row.status} requests are terminal and cannot be changed.")
    if new_status not in ALLOWED_TRANSITIONS[row.status]:
        raise HTTPException(status_code=422, detail=f"Cannot change status from {row.status} to {new_status}.")
    if new_status == "rejected" and not (rejection_reason or "").strip():
        raise HTTPException(status_code=422, detail="Rejection reason is required when rejecting a staffing request.")
    old_status = row.status
    row.status = new_status
    row.rejection_reason = rejection_reason if new_status == "rejected" else row.rejection_reason
    row.updated_by = actor_id
    row.updated_at = datetime.utcnow()
    log_audit(db, db.query(Employee).filter(Employee.id == actor_id).first(), "staffing_request_status_changed", "staffing_request", row.id, old_values={"status": old_status}, new_values={"status": new_status, "rejection_reason": rejection_reason}, metadata={"changed_at": datetime.utcnow().isoformat(), "actor": actor_id, "staffing_request_id": row.id, "old_status": old_status, "new_status": new_status})
    db.commit()
    return serialize_request(db, row, include_candidates=True)


def cancel_request(db: Session, request_id: str, actor_id: str) -> StaffingRequestOut:
    row = db.query(StaffingRequest).filter(StaffingRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Staffing request not found.")
    if row.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=422, detail=f"{row.status} requests are terminal and cannot be cancelled.")
    old_status = row.status
    row.status = "cancelled"
    row.updated_by = actor_id
    row.updated_at = datetime.utcnow()
    log_audit(db, db.query(Employee).filter(Employee.id == actor_id).first(), "staffing_request_cancelled", "staffing_request", row.id, old_values={"status": old_status}, new_values={"status": "cancelled"}, metadata={"changed_at": datetime.utcnow().isoformat(), "actor": actor_id, "staffing_request_id": row.id, "project_name": row.project_name})
    db.commit()
    return serialize_request(db, row, include_candidates=True)


def ensure_candidate(db: Session, request_id: str, employee_id: str, suggested_by: str = "manual") -> StaffingRequestCandidate:
    candidate = db.query(StaffingRequestCandidate).filter(
        StaffingRequestCandidate.staffing_request_id == request_id,
        StaffingRequestCandidate.employee_id == employee_id,
    ).first()
    if candidate:
        return candidate
    if not db.query(Employee).filter(Employee.id == employee_id).first():
        raise HTTPException(status_code=404, detail="Employee not found.")
    snapshot = candidate_snapshot(db, employee_id)
    candidate = StaffingRequestCandidate(
        staffing_request_id=request_id,
        employee_id=employee_id,
        match_status="suggested",
        suggested_by=suggested_by,
        **snapshot,
    )
    db.add(candidate)
    db.flush()
    return candidate


def recalculate_headcount(db: Session, row: StaffingRequest) -> None:
    selected_count = db.query(func.count(StaffingRequestCandidate.id)).filter(
        StaffingRequestCandidate.staffing_request_id == row.id,
        StaffingRequestCandidate.match_status.in_(["selected", "allocated"]),
    ).scalar() or 0
    row.headcount_fulfilled = int(selected_count)
    if row.status not in TERMINAL_STATUSES and row.headcount_fulfilled > 0:
        row.status = "partially_fulfilled"


def shortlist_candidate(db: Session, request_id: str, employee_id: str, actor_id: str) -> StaffingRequestOut:
    row = db.query(StaffingRequest).filter(StaffingRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Staffing request not found.")
    if row.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=422, detail="Staffing request is no longer accepting candidate changes.")
    candidate = ensure_candidate(db, request_id, employee_id)
    if candidate.match_status == "allocated":
        raise HTTPException(status_code=422, detail="Allocated candidates cannot be changed.")
    old_status = candidate.match_status
    candidate.match_status = "shortlisted"
    candidate.updated_at = datetime.utcnow()
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    log_audit(db, db.query(Employee).filter(Employee.id == actor_id).first(), "staffing_candidate_shortlisted", "staffing_request", row.id, old_values={"match_status": old_status}, new_values={"match_status": "shortlisted"}, metadata={"changed_at": datetime.utcnow().isoformat(), "actor": actor_id, "staffing_request_id": row.id, "employee_id": employee_id, "employee_name": employee_name(employee)})
    db.commit()
    return serialize_request(db, row, include_candidates=True)


def select_candidate(db: Session, request_id: str, employee_id: str, actor_id: str) -> StaffingRequestOut:
    row = db.query(StaffingRequest).filter(StaffingRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Staffing request not found.")
    if row.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=422, detail="Staffing request is no longer accepting candidate changes.")
    candidate = ensure_candidate(db, request_id, employee_id)
    if candidate.match_status == "rejected":
        raise HTTPException(status_code=422, detail="Rejected candidates cannot be selected.")
    if candidate.match_status == "allocated":
        raise HTTPException(status_code=422, detail="Allocated candidates cannot be selected again.")
    old_status = candidate.match_status
    candidate.match_status = "selected"
    candidate.updated_at = datetime.utcnow()
    recalculate_headcount(db, row)
    row.updated_by = actor_id
    row.updated_at = datetime.utcnow()
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    log_audit(db, db.query(Employee).filter(Employee.id == actor_id).first(), "staffing_candidate_selected", "staffing_request", row.id, old_values={"match_status": old_status}, new_values={"match_status": "selected", "headcount_fulfilled": row.headcount_fulfilled, "status": row.status}, metadata={"changed_at": datetime.utcnow().isoformat(), "actor": actor_id, "staffing_request_id": row.id, "employee_id": employee_id, "employee_name": employee_name(employee), "headcount_fulfilled": row.headcount_fulfilled, "headcount_needed": row.headcount_needed})
    db.commit()
    return serialize_request(db, row, include_candidates=True)


def reject_candidate(db: Session, request_id: str, employee_id: str, actor_id: str) -> StaffingRequestOut:
    row = db.query(StaffingRequest).filter(StaffingRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Staffing request not found.")
    if row.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=422, detail="Staffing request is no longer accepting candidate changes.")
    candidate = ensure_candidate(db, request_id, employee_id)
    if candidate.match_status in {"selected", "allocated"}:
        raise HTTPException(status_code=422, detail="Selected or allocated candidates cannot be rejected.")
    old_status = candidate.match_status
    candidate.match_status = "rejected"
    candidate.updated_at = datetime.utcnow()
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    log_audit(db, db.query(Employee).filter(Employee.id == actor_id).first(), "staffing_candidate_rejected", "staffing_request", row.id, old_values={"match_status": old_status}, new_values={"match_status": "rejected"}, metadata={"changed_at": datetime.utcnow().isoformat(), "actor": actor_id, "staffing_request_id": row.id, "employee_id": employee_id, "employee_name": employee_name(employee)})
    db.commit()
    return serialize_request(db, row, include_candidates=True)

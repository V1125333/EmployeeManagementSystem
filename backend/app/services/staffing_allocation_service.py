from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.employee import Employee
from app.models.staffing_request import StaffingRequest, StaffingRequestCandidate
from app.schemas.allocation import AllocationCreate
from app.schemas.staffing_request import AllocationOverrides, StaffingFulfillmentResult
from app.services.allocation_service import create_allocation, serialize_allocation
from app.services.audit_service import log_audit
from app.services.staffing_service import employee_name, fulfilled_allocation_ids, serialize_candidate, serialize_request


@dataclass
class CapacityValidationResult:
    is_valid: bool
    current_overlapping_total: int
    projected_total: int
    overlapping_allocations: list[dict[str, Any]]


def _allocation_overlap_dict(allocation: Allocation) -> dict[str, Any]:
    return {
        "allocation_id": allocation.id,
        "project_name": allocation.project_name or allocation.project_id,
        "allocation_percentage": allocation.allocation_percentage,
        "allocation_role": allocation.allocation_role,
        "status": allocation.status,
        "start_date": allocation.start_date.isoformat() if allocation.start_date else None,
        "end_date": allocation.end_date.isoformat() if allocation.end_date else None,
    }


def _date_plus_one(value: date | None) -> date:
    if value is None or value == date.max:
        return date.max
    return value + timedelta(days=1)


def _active_total_on(day: date, allocations: list[Allocation]) -> int:
    total = 0
    for allocation in allocations:
        allocation_end = allocation.end_date or date.max
        if allocation.start_date <= day <= allocation_end:
            total += int(allocation.allocation_percentage or 0)
    return total


def validate_employee_capacity_for_period(
    db: Session,
    employee_id: str,
    new_allocation_percentage: int,
    start_date: date,
    end_date: date | None,
    exclude_allocation_id: str | None = None,
) -> CapacityValidationResult:
    new_end = end_date or date.max
    query = db.query(Allocation).filter(
        Allocation.employee_id == employee_id,
        Allocation.status.in_(["active", "upcoming"]),
        Allocation.start_date <= new_end,
        or_(Allocation.end_date == None, Allocation.end_date >= start_date),  # noqa: E711
    )
    if exclude_allocation_id:
        query = query.filter(Allocation.id != exclude_allocation_id)

    overlapping = query.order_by(Allocation.start_date.asc()).all()
    sample_days = {start_date}
    if end_date:
        sample_days.add(end_date)
    for allocation in overlapping:
        overlap_start = max(start_date, allocation.start_date)
        overlap_end = min(new_end, allocation.end_date or date.max)
        sample_days.add(overlap_start)
        if overlap_end != date.max:
            sample_days.add(overlap_end)
        if allocation.start_date > start_date and allocation.start_date <= new_end:
            sample_days.add(allocation.start_date)
        end_plus_one = _date_plus_one(allocation.end_date)
        if start_date <= end_plus_one <= new_end:
            sample_days.add(end_plus_one)

    current_total = max((_active_total_on(day, overlapping) for day in sample_days), default=0)
    projected_total = current_total + int(new_allocation_percentage or 0)
    return CapacityValidationResult(
        is_valid=projected_total <= 100,
        current_overlapping_total=current_total,
        projected_total=projected_total,
        overlapping_allocations=[_allocation_overlap_dict(item) for item in overlapping],
    )


def _capacity_error(result: CapacityValidationResult, requested: int) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "message": "Employee allocation would exceed 100% during this period.",
            "current_total": result.current_overlapping_total,
            "requested": requested,
            "projected_total": result.projected_total,
            "overlapping_allocations": result.overlapping_allocations,
        },
    )


def capacity_check_payload(
    db: Session,
    employee_id: str,
    allocation_percentage: int,
    start_date: date,
    end_date: date | None,
    exclude_allocation_id: str | None = None,
) -> dict[str, Any]:
    result = validate_employee_capacity_for_period(
        db,
        employee_id=employee_id,
        new_allocation_percentage=allocation_percentage,
        start_date=start_date,
        end_date=end_date,
        exclude_allocation_id=exclude_allocation_id,
    )
    return {
        "is_valid": result.is_valid,
        "current_overlapping_total": result.current_overlapping_total,
        "requested": allocation_percentage,
        "projected_total": result.projected_total,
        "overlapping_allocations": result.overlapping_allocations,
    }


def _build_allocation_payload(
    request: StaffingRequest,
    employee_id: str,
    overrides: AllocationOverrides | None,
) -> AllocationCreate:
    override_values = overrides.model_dump(exclude_unset=True) if overrides else {}
    start_date = override_values.get("start_date") or request.start_date
    end_date = override_values.get("end_date", request.end_date)
    allocation_percentage = override_values.get("allocation_percentage") or request.allocation_percentage
    allocation_role = (override_values.get("allocation_role") or request.role_needed).strip()
    manager_id = override_values.get("manager_id") or request.hiring_manager_id
    billing_type = override_values.get("billing_type") or "billable"
    notes = override_values.get("notes")
    if notes is None:
        notes = f"Created from Staffing Request {request.id}"
    status = "upcoming" if start_date > date.today() else "active"

    return AllocationCreate(
        employee_id=employee_id,
        project_id=request.project_id,
        project_name=request.project_name,
        manager_id=manager_id,
        allocation_percentage=allocation_percentage,
        allocation_role=allocation_role,
        billing_type=billing_type,
        start_date=start_date,
        end_date=end_date,
        status=status,
        notes=notes,
    )


def _ensure_request_can_allocate(request: StaffingRequest) -> None:
    if request.status == "fulfilled":
        raise HTTPException(status_code=422, detail="Staffing request is already fulfilled.")
    if request.status in {"cancelled", "rejected"}:
        raise HTTPException(status_code=422, detail="Staffing request is no longer accepting allocations.")
    if request.status not in {"open", "in_review", "partially_fulfilled"}:
        raise HTTPException(status_code=422, detail="Staffing request is no longer accepting allocations.")


def create_allocation_from_staffing_request(
    db: Session,
    staffing_request_id: str,
    employee_id: str,
    actor_id: str,
    overrides: AllocationOverrides | None = None,
) -> StaffingFulfillmentResult:
    request = db.query(StaffingRequest).filter(StaffingRequest.id == staffing_request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Staffing request not found.")
    _ensure_request_can_allocate(request)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    already_allocated = db.query(StaffingRequestCandidate).filter(
        StaffingRequestCandidate.staffing_request_id == staffing_request_id,
        StaffingRequestCandidate.employee_id == employee_id,
        StaffingRequestCandidate.match_status == "allocated",
    ).first()
    if already_allocated:
        raise HTTPException(status_code=422, detail="Allocation already created for this candidate.")

    candidate = db.query(StaffingRequestCandidate).filter(
        StaffingRequestCandidate.staffing_request_id == staffing_request_id,
        StaffingRequestCandidate.employee_id == employee_id,
    ).first()
    if not candidate:
        raise HTTPException(status_code=422, detail="Employee is not a candidate for this staffing request.")
    if candidate.match_status == "allocated":
        raise HTTPException(status_code=422, detail="An allocation has already been created for this candidate from this request.")
    if candidate.match_status != "selected":
        raise HTTPException(status_code=422, detail="Candidate must be in 'selected' status before creating an allocation.")

    allocation_data = _build_allocation_payload(request, employee_id, overrides)
    capacity = validate_employee_capacity_for_period(
        db,
        employee_id=employee_id,
        new_allocation_percentage=allocation_data.allocation_percentage,
        start_date=allocation_data.start_date,
        end_date=allocation_data.end_date,
    )
    if not capacity.is_valid:
        raise _capacity_error(capacity, allocation_data.allocation_percentage)

    actor = db.query(Employee).filter(Employee.id == actor_id).first()
    old_request_status = request.status
    old_candidate_status = candidate.match_status

    try:
        allocation = create_allocation(db, allocation_data, created_by_id=actor_id, commit=False)
        candidate.match_status = "allocated"
        candidate.allocation_id = allocation.id
        candidate.updated_at = datetime.utcnow()

        allocation_ids = fulfilled_allocation_ids(request)
        if allocation.id not in allocation_ids:
            allocation_ids.append(allocation.id)
        request.fulfilled_allocation_ids = allocation_ids

        if request.headcount_fulfilled >= request.headcount_needed:
            request.status = "fulfilled"
            request.fulfilled_at = datetime.utcnow()
            request.fulfilled_by = actor_id
        else:
            request.status = "partially_fulfilled"
            request.fulfilled_at = None
            request.fulfilled_by = None
        request.updated_by = actor_id
        request.updated_at = datetime.utcnow()

        audit_details = {
            "staffing_request_id": request.id,
            "allocation_id": allocation.id,
            "employee_id": employee_id,
            "employee_name": employee_name(employee),
            "project_name": request.project_name,
            "allocation_percentage": allocation.allocation_percentage,
            "start_date": allocation.start_date.isoformat() if allocation.start_date else None,
            "end_date": allocation.end_date.isoformat() if allocation.end_date else None,
            "billing_type": allocation.billing_type,
            "created_by": actor_id,
        }
        log_audit(
            db,
            actor,
            "allocation_created_from_staffing_request",
            "staffing_request",
            request.id,
            new_values=audit_details,
            metadata=audit_details,
        )
        log_audit(
            db,
            actor,
            "staffing_candidate_allocated",
            "staffing_request",
            request.id,
            old_values={"match_status": old_candidate_status},
            new_values={"match_status": "allocated", "allocation_id": allocation.id},
            metadata={
                "staffing_request_id": request.id,
                "candidate_id": candidate.id,
                "employee_id": employee_id,
                "employee_name": employee_name(employee),
                "allocation_id": allocation.id,
            },
        )
        status_action = "staffing_request_fulfilled" if request.status == "fulfilled" else "staffing_request_partially_fulfilled"
        metadata = {
            "staffing_request_id": request.id,
            "project_name": request.project_name,
            "headcount_fulfilled": request.headcount_fulfilled,
            "headcount_needed": request.headcount_needed,
        }
        if request.status == "fulfilled":
            metadata.update({
                "fulfilled_by": actor_id,
                "fulfilled_at": request.fulfilled_at.isoformat() if request.fulfilled_at else None,
                "fulfilled_allocation_ids": request.fulfilled_allocation_ids,
            })
        log_audit(
            db,
            actor,
            status_action,
            "staffing_request",
            request.id,
            old_values={"status": old_request_status},
            new_values={"status": request.status},
            metadata=metadata,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail="Allocation already created for this candidate.") from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(allocation)
    db.refresh(request)
    db.refresh(candidate)
    return StaffingFulfillmentResult(
        allocation=serialize_allocation(db, allocation),
        staffing_request=serialize_request(db, request, include_candidates=True),
        candidate=serialize_candidate(db, candidate),
        overlap_warning=capacity.overlapping_allocations or None,
    )

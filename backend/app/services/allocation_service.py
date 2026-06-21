from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.employee import Employee
from app.models.operations import Project
from app.schemas.allocation import AllocationCreate, AllocationUpdate
from app.services.audit_service import changed_fields, log_audit

VALID_BILLING_TYPES = {"billable", "non_billable", "internal"}
VALID_STATUSES = {"active", "upcoming", "completed", "cancelled"}


def _values(allocation: Allocation) -> dict[str, Any]:
    return {
        "id": allocation.id,
        "employee_id": allocation.employee_id,
        "project_id": allocation.project_id,
        "project_name": allocation.project_name,
        "manager_id": allocation.manager_id,
        "allocation_percentage": allocation.allocation_percentage,
        "allocation_role": allocation.allocation_role,
        "billing_type": allocation.billing_type,
        "status": allocation.status,
        "start_date": allocation.start_date,
        "end_date": allocation.end_date,
        "notes": allocation.notes,
        "created_by": allocation.created_by,
        "updated_by": allocation.updated_by,
        "created_at": allocation.created_at,
        "updated_at": allocation.updated_at,
    }


def _require_employee(db: Session, employee_id: str, label: str) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=422, detail=f"{label} not found.")
    return employee


def _validate_project(db: Session, project_id: str | None, project_name: str | None) -> str | None:
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=422, detail="Project not found.")
        return project_name or project.name
    if not project_name or not project_name.strip():
        raise HTTPException(status_code=422, detail="Either project_id or project_name is required.")
    return project_name.strip()


def _validate_state(db: Session, state: dict[str, Any], allocation_id: str | None = None) -> None:
    required_fields = [
        "employee_id",
        "manager_id",
        "allocation_role",
        "allocation_percentage",
        "start_date",
        "billing_type",
    ]
    missing = [field for field in required_fields if state.get(field) in (None, "")]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {', '.join(missing)}.")

    percentage = int(state["allocation_percentage"])
    if percentage < 1 or percentage > 100:
        raise HTTPException(status_code=422, detail="allocation_percentage must be between 1 and 100.")

    if state["billing_type"] not in VALID_BILLING_TYPES:
        raise HTTPException(status_code=422, detail="billing_type must be billable, non_billable, or internal.")

    if state.get("status", "active") not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="status must be active, upcoming, completed, or cancelled.")

    if state.get("end_date") and state["end_date"] < state["start_date"]:
        raise HTTPException(status_code=422, detail="end_date cannot be before start_date.")

    _require_employee(db, state["employee_id"], "Employee")
    _require_employee(db, state["manager_id"], "Manager")
    state["project_name"] = _validate_project(db, state.get("project_id"), state.get("project_name"))

    if state.get("status") == "active":
        query = db.query(func.coalesce(func.sum(Allocation.allocation_percentage), 0)).filter(
            Allocation.employee_id == state["employee_id"],
            Allocation.status == "active",
        )
        if allocation_id:
            query = query.filter(Allocation.id != allocation_id)
        active_total = int(query.scalar() or 0)
        if active_total + percentage > 100:
            raise HTTPException(
                status_code=422,
                detail=f"Total active allocation cannot exceed 100%. Current active total is {active_total}%.",
            )


def create_allocation(db: Session, data: AllocationCreate, created_by_id: str) -> Allocation:
    state = data.model_dump()
    _validate_state(db, state)

    allocation = Allocation(
        **state,
        created_by=created_by_id,
        updated_by=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(allocation)
    db.flush()
    log_audit(
        db,
        db.query(Employee).filter(Employee.id == created_by_id).first(),
        action="allocation_created",
        entity_type="allocation",
        entity_id=allocation.id,
        new_values=_values(allocation),
        metadata={
            "employee_id": allocation.employee_id,
            "allocation_id": allocation.id,
            "changed_by": created_by_id,
            "changed_at": datetime.utcnow().isoformat(),
        },
    )
    db.commit()
    db.refresh(allocation)
    return allocation


def update_allocation(db: Session, allocation_id: str, data: AllocationUpdate, updated_by_id: str) -> Allocation:
    allocation = db.query(Allocation).filter(Allocation.id == allocation_id).first()
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found.")

    old_values = _values(allocation)
    patch = data.model_dump(exclude_unset=True)
    next_state = {**old_values, **patch}
    _validate_state(db, next_state, allocation_id=allocation_id)

    for field, value in patch.items():
        setattr(allocation, field, value)
    allocation.project_name = next_state["project_name"]
    allocation.updated_by = updated_by_id
    allocation.updated_at = datetime.utcnow()

    db.flush()
    new_values = _values(allocation)
    changes = changed_fields(old_values, new_values)
    if changes:
        log_audit(
            db,
            db.query(Employee).filter(Employee.id == updated_by_id).first(),
            action="allocation_updated",
            entity_type="allocation",
            entity_id=allocation.id,
            old_values=old_values,
            new_values=new_values,
            changed_fields_payload=changes,
            metadata={
                "employee_id": allocation.employee_id,
                "allocation_id": allocation.id,
                "changed_by": updated_by_id,
                "changed_at": datetime.utcnow().isoformat(),
            },
        )
    db.commit()
    db.refresh(allocation)
    return allocation


def cancel_allocation(db: Session, allocation_id: str, cancelled_by_id: str) -> Allocation:
    allocation = db.query(Allocation).filter(Allocation.id == allocation_id).first()
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found.")

    old_values = _values(allocation)
    allocation.status = "cancelled"
    allocation.updated_by = cancelled_by_id
    allocation.updated_at = datetime.utcnow()
    db.flush()
    log_audit(
        db,
        db.query(Employee).filter(Employee.id == cancelled_by_id).first(),
        action="allocation_cancelled",
        entity_type="allocation",
        entity_id=allocation.id,
        old_values=old_values,
        new_values=_values(allocation),
        metadata={
            "employee_id": allocation.employee_id,
            "allocation_id": allocation.id,
            "cancelled_by": cancelled_by_id,
            "cancelled_at": datetime.utcnow().isoformat(),
        },
    )
    db.commit()
    db.refresh(allocation)
    return allocation


def get_allocations_by_employee(db: Session, employee_id: str) -> list[Allocation]:
    return db.query(Allocation).filter(Allocation.employee_id == employee_id).order_by(
        Allocation.start_date.desc(),
        Allocation.updated_at.desc(),
    ).all()


def get_active_allocations(db: Session, employee_id: str) -> list[Allocation]:
    return db.query(Allocation).filter(
        Allocation.employee_id == employee_id,
        Allocation.status == "active",
    ).order_by(Allocation.start_date.desc()).all()


def get_allocation_summary(db: Session, employee_id: str) -> dict[str, Any]:
    active_allocations = get_active_allocations(db, employee_id)
    total_active = sum(int(allocation.allocation_percentage or 0) for allocation in active_allocations)
    available_capacity = max(0, 100 - total_active)

    if total_active == 0:
        allocation_status = "bench"
    elif total_active < 100:
        allocation_status = "partially_allocated"
    elif total_active == 100:
        allocation_status = "fully_allocated"
    else:
        allocation_status = "overallocated"

    end_dates = [allocation.end_date for allocation in active_allocations if allocation.end_date]

    return {
        "total_active_allocation_percentage": total_active,
        "available_capacity_percentage": available_capacity,
        "allocation_status": allocation_status,
        "active_projects_count": len(active_allocations),
        "next_end_date": min(end_dates) if end_dates else None,
    }


def get_upcoming_allocations(db: Session, employee_id: str) -> list[Allocation]:
    return db.query(Allocation).filter(
        Allocation.employee_id == employee_id,
        Allocation.status == "upcoming",
    ).order_by(Allocation.start_date.asc()).all()


def serialize_allocation(db: Session, allocation: Allocation) -> dict[str, Any]:
    manager = db.query(Employee).filter(Employee.id == allocation.manager_id).first()
    return {
        **_values(allocation),
        "manager_name": f"{manager.first_name} {manager.last_name}".strip() if manager else None,
    }

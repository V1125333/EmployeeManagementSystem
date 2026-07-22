from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.employee import Employee
from app.models.operations import Notification, Project
from app.schemas.allocation import AllocationCreate, AllocationUpdate
from app.services.audit_service import changed_fields, log_audit

VALID_BILLING_TYPES = {"billable", "non_billable", "internal"}
VALID_STATUSES = {"active", "upcoming", "completed", "cancelled"}


def _overlapping_capacity_total(
    db: Session,
    employee_id: str,
    start_date: date,
    end_date: date | None,
    allocation_id: str | None = None,
) -> int:
    query = db.query(func.coalesce(func.sum(Allocation.allocation_percentage), 0)).filter(
        Allocation.employee_id == employee_id,
        Allocation.status.in_(["active", "upcoming"]),
        Allocation.start_date <= (end_date or date.max),
        (Allocation.end_date == None) | (Allocation.end_date >= start_date),  # noqa: E711
    )
    if allocation_id:
        query = query.filter(Allocation.id != allocation_id)
    return int(query.scalar() or 0)


def _has_overlapping_project_assignment(
    db: Session,
    employee_id: str,
    project_id: str,
    start_date: date,
    end_date: date | None,
    allocation_id: str | None = None,
) -> bool:
    query = db.query(Allocation.id).filter(
        Allocation.employee_id == employee_id,
        Allocation.project_id == project_id,
        Allocation.status.in_(["active", "upcoming"]),
        Allocation.start_date <= (end_date or date.max),
        (Allocation.end_date == None) | (Allocation.end_date >= start_date),  # noqa: E711
    )
    if allocation_id:
        query = query.filter(Allocation.id != allocation_id)
    return db.query(query.exists()).scalar()


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


def _employee_name(employee: Employee | None) -> str | None:
    if not employee:
        return None
    middle_name = getattr(employee, "middle_name", None)
    parts = [employee.first_name, middle_name, employee.last_name]
    return " ".join(part.strip() for part in parts if part and part.strip()) or employee.work_email


def _validate_project(db: Session, project_id: str | None, project_name: str | None, require_active: bool = False) -> str | None:
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=422, detail="Project not found.")
        if require_active and project.status != "active":
            raise HTTPException(status_code=422, detail="Target project must be active before moving an assignment.")
        return project_name or project.name
    if not project_name or not project_name.strip():
        raise HTTPException(status_code=422, detail="Either project_id or project_name is required.")
    return project_name.strip()


def _validate_state(
    db: Session,
    state: dict[str, Any],
    allocation_id: str | None = None,
    require_active_project: bool = False,
) -> None:
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
    state["project_name"] = _validate_project(
        db,
        state.get("project_id"),
        state.get("project_name"),
        require_active=require_active_project,
    )

    if state.get("status") in {"active", "upcoming"}:
        if state.get("project_id") and _has_overlapping_project_assignment(
            db,
            employee_id=state["employee_id"],
            project_id=state["project_id"],
            start_date=state["start_date"],
            end_date=state.get("end_date"),
            allocation_id=allocation_id,
        ):
            raise HTTPException(
                status_code=422,
                detail="Employee is already assigned to this project for the selected date range.",
            )

        active_total = _overlapping_capacity_total(
            db,
            employee_id=state["employee_id"],
            start_date=state["start_date"],
            end_date=state.get("end_date"),
            allocation_id=allocation_id,
        )
        if active_total + percentage > 100:
            raise HTTPException(
                status_code=422,
                detail=f"Total allocation cannot exceed 100% for the selected period. Current overlapping total is {active_total}%.",
            )


def create_allocation(db: Session, data: AllocationCreate, created_by_id: str, commit: bool = True) -> Allocation:
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
    employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
    project = db.query(Project).filter(Project.id == allocation.project_id).first() if allocation.project_id else None
    log_audit(
        db,
        db.query(Employee).filter(Employee.id == created_by_id).first(),
        action="project_employee_assigned" if allocation.project_id else "allocation_created",
        entity_type="project" if allocation.project_id else "allocation",
        entity_id=allocation.project_id or allocation.id,
        new_values=_values(allocation),
        metadata={
            "employee_id": allocation.employee_id,
            "allocation_id": allocation.id,
            "project_name": project.name if project else allocation.project_name,
            "allocation_percentage": allocation.allocation_percentage,
            "allocation_role": allocation.allocation_role,
            "changed_by": created_by_id,
            "changed_at": datetime.utcnow().isoformat(),
        },
    )
    if employee:
        db.add(
            Notification(
                user_id=employee.id,
                title="Project assignment updated",
                message=f"You have been assigned to {allocation.project_name or 'a project'} as {allocation.allocation_role}.",
                type="allocation",
                notification_type="project_assignment",
                related_entity_type="allocation",
                related_entity_id=allocation.id,
                link_url="/profile?tab=allocations",
            )
        )
    if commit:
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
    project_changed = "project_id" in patch and patch.get("project_id") != old_values.get("project_id")
    _validate_state(db, next_state, allocation_id=allocation_id, require_active_project=project_changed)

    for field, value in patch.items():
        setattr(allocation, field, value)
    allocation.project_name = next_state["project_name"]
    allocation.updated_by = updated_by_id
    allocation.updated_at = datetime.utcnow()

    db.flush()
    new_values = _values(allocation)
    changes = changed_fields(old_values, new_values)
    if changes:
        actor = db.query(Employee).filter(Employee.id == updated_by_id).first()
        metadata = {
            "employee_id": allocation.employee_id,
            "allocation_id": allocation.id,
            "changed_by": updated_by_id,
            "changed_at": datetime.utcnow().isoformat(),
        }
        log_audit(
            db,
            actor,
            action="ALLOCATION_UPDATED",
            entity_type="allocation",
            entity_id=allocation.id,
            old_values=old_values,
            new_values=new_values,
            changed_fields_payload=changes,
            metadata=metadata,
        )
        event_fields = [
            ("allocation_percentage", "ALLOCATION_PERCENTAGE_CHANGED"),
            ("manager_id", "ALLOCATION_MANAGER_CHANGED"),
            ("project_id", "ALLOCATION_PROJECT_CHANGED"),
        ]
        for field, action in event_fields:
            if field in changes:
                log_audit(
                    db,
                    actor,
                    action=action,
                    entity_type="allocation",
                    entity_id=allocation.id,
                    old_values={field: old_values.get(field)},
                    new_values={field: new_values.get(field)},
                    changed_fields_payload={field: changes[field]},
                    metadata=metadata,
                )
        if old_values.get("status") != "completed" and new_values.get("status") == "completed":
            log_audit(
                db,
                actor,
                action="ALLOCATION_ENDED",
                entity_type="allocation",
                entity_id=allocation.id,
                old_values={"status": old_values.get("status"), "end_date": old_values.get("end_date")},
                new_values={"status": new_values.get("status"), "end_date": new_values.get("end_date")},
                changed_fields_payload={field: changes[field] for field in ("status", "end_date") if field in changes},
                metadata=metadata,
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
        action="ALLOCATION_REMOVED",
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


def get_active_allocations(db: Session, employee_id: str, reference_date: date | None = None) -> list[Allocation]:
    day = reference_date or date.today()
    return db.query(Allocation).filter(
        Allocation.employee_id == employee_id,
        Allocation.status == "active",
        Allocation.start_date <= day,
        or_(Allocation.end_date.is_(None), Allocation.end_date >= day),
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
    employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
    project_name = allocation.project_name
    project_code = None
    project_client_name = None
    project_status = None
    project_start_date = None
    project_end_date = None
    if allocation.project_id:
        from app.models.operations import Project
        project = db.query(Project).filter(Project.id == allocation.project_id).first()
        if project:
            project_name = project.name
            project_code = project.code
            project_client_name = project.client_name
            project_status = project.status
            project_start_date = project.start_date
            project_end_date = project.end_date
    return {
        **_values(allocation),
        "project_name": project_name,
        "project_code": project_code,
        "project_client_name": project_client_name,
        "project_status": project_status,
        "project_start_date": project_start_date,
        "project_end_date": project_end_date,
        "project_location": employee.work_location if employee else None,
        "employee_name": _employee_name(employee),
        "employee_email": employee.work_email if employee else None,
        "manager_name": f"{manager.first_name} {manager.last_name}".strip() if manager else None,
    }


def ensure_allocation_ending_notifications(db: Session, reference_date: date | None = None) -> int:
    today = reference_date or date.today()
    notify_until = today + timedelta(days=7)
    ending_allocations = db.query(Allocation).filter(
        Allocation.status == "active",
        Allocation.end_date.isnot(None),
        Allocation.end_date >= today,
        Allocation.end_date <= notify_until,
    ).all()
    created = 0
    for allocation in ending_allocations:
        if not allocation.manager_id:
            continue
        exists = db.query(Notification.id).filter(
            Notification.user_id == allocation.manager_id,
            Notification.notification_type == "allocation_ending",
            Notification.related_entity_type == "allocation",
            Notification.related_entity_id == allocation.id,
        ).first()
        if exists:
            continue
        employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
        project = db.query(Project).filter(Project.id == allocation.project_id).first() if allocation.project_id else None
        employee_name = _employee_name(employee) or "An employee"
        project_label = project.name if project else allocation.project_name or "an allocation"
        db.add(Notification(
            user_id=allocation.manager_id,
            title="Allocation ending soon",
            message=f"{employee_name}'s allocation on {project_label} ends on {allocation.end_date}.",
            type="allocation",
            notification_type="allocation_ending",
            related_entity_type="allocation",
            related_entity_id=allocation.id,
            link_url=f"/profile?employee_id={allocation.employee_id}&tab=allocations",
        ))
        created += 1

    recently_ended_since = today - timedelta(days=30)
    ended_allocations = db.query(Allocation).filter(
        Allocation.status.in_(["active", "completed"]),
        Allocation.end_date.isnot(None),
        Allocation.end_date < today,
        Allocation.end_date >= recently_ended_since,
    ).all()
    for allocation in ended_allocations:
        if not allocation.manager_id or not allocation.end_date:
            continue
        exists = db.query(Notification.id).filter(
            Notification.user_id == allocation.manager_id,
            Notification.notification_type == "allocation_available",
            Notification.related_entity_type == "allocation",
            Notification.related_entity_id == allocation.id,
        ).first()
        if exists:
            continue
        employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
        project = db.query(Project).filter(Project.id == allocation.project_id).first() if allocation.project_id else None
        employee_name = _employee_name(employee) or "An employee"
        project_label = project.name if project else allocation.project_name or "an allocation"
        availability_start = allocation.end_date + timedelta(days=1)
        active_after_end = get_active_allocations(db, allocation.employee_id, availability_start)
        active_total = sum(int(row.allocation_percentage or 0) for row in active_after_end)
        available_capacity = max(0, 100 - active_total)
        if available_capacity <= 0:
            continue
        availability_label = "is now on bench" if active_total == 0 else f"has {available_capacity}% available capacity"
        db.add(Notification(
            user_id=allocation.manager_id,
            title="Allocation ended",
            message=(
                f"{employee_name}'s allocation on {project_label} ended on {allocation.end_date}. "
                f"From {availability_start}, {employee_name} {availability_label}."
            ),
            type="allocation",
            notification_type="allocation_available",
            related_entity_type="allocation",
            related_entity_id=allocation.id,
            link_url=f"/profile?employee_id={allocation.employee_id}&tab=allocations",
        ))
        created += 1
    if created:
        db.commit()
    return created

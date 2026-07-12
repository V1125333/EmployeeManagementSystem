from datetime import date, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.allocation import Allocation
from app.models.employee import Employee
from app.models.operations import Project
from app.schemas.allocation import AllocationCreate, AllocationOut, AllocationSummaryOut, AllocationUpdate, BenchEmployeeOut
from app.services.allocation_service import (
    cancel_allocation,
    create_allocation,
    get_active_allocations,
    get_allocation_summary,
    get_allocations_by_employee,
    get_upcoming_allocations,
    serialize_allocation,
    update_allocation,
)
from app.services.audit_service import log_authorization_failure
from app.services.settings_service import get_current_employee, normalize_role
from app.services.staffing_allocation_service import capacity_check_payload

router = APIRouter(prefix="/allocations", tags=["Allocations"])


def _is_hr_admin(actor: Employee) -> bool:
    return normalize_role(actor.role) in {"super_admin", "hr_admin", "admin", "global_access"}


def _is_manager(actor: Employee) -> bool:
    return normalize_role(actor.role) == "manager"


def _is_direct_manager(db: Session, actor: Employee, employee_id: str) -> bool:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    actor_name = f"{actor.first_name} {actor.last_name}".strip()
    return bool(
        employee
        and (
            (employee.manager_id and employee.manager_id == actor.id)
            or (employee.reporting_manager and employee.reporting_manager == actor_name)
        )
    )


def _require_read_access(db: Session, actor: Employee, employee_id: str) -> None:
    if _is_hr_admin(actor) or actor.id == employee_id or _is_direct_manager(db, actor, employee_id):
        return
    log_authorization_failure(
        db,
        actor,
        action="allocation.read",
        entity_type="allocation",
        entity_id=employee_id,
        reason="User attempted to read allocations outside their scope.",
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Not authorized to view these allocations.")


def _require_write_access(db: Session, actor: Employee, employee_id: str) -> None:
    if _is_hr_admin(actor):
        return

    if normalize_role(actor.role) == "manager" and _is_direct_manager(db, actor, employee_id):
        return

    log_authorization_failure(
        db,
        actor,
        action="allocation.write",
        entity_type="allocation",
        entity_id=employee_id,
        reason="User attempted to create, update, or cancel allocations outside their scope.",
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Not authorized to manage allocations.")


def _require_bench_access(db: Session, actor: Employee) -> None:
    if _is_hr_admin(actor) or _is_manager(actor):
        return
    log_authorization_failure(
        db,
        actor,
        action="allocation.bench",
        entity_type="allocation",
        entity_id=actor.id,
        reason="User attempted to view bench availability without permission.",
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Not authorized to view bench availability.")


def _employee_name(employee: Employee) -> str:
    middle_name = getattr(employee, "middle_name", None)
    parts = [employee.first_name, middle_name, employee.last_name]
    return " ".join(part.strip() for part in parts if part and part.strip())


def _active_project_names(db: Session, employee_id: str) -> list[str]:
    allocations = get_active_allocations(db, employee_id)
    names: list[str] = []
    for allocation in allocations:
        name = allocation.project_name or allocation.project_id
        if name and name not in names:
            names.append(name)
    return names


@router.post("/", response_model=AllocationOut)
async def create_allocation_endpoint(
    data: AllocationCreate,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_write_access(db, actor, data.employee_id)
    allocation = create_allocation(db, data, actor.id)
    return serialize_allocation(db, allocation)


@router.patch("/{allocation_id}", response_model=AllocationOut)
async def update_allocation_endpoint(
    allocation_id: str,
    data: AllocationUpdate,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    allocation = db.query(Allocation).filter(Allocation.id == allocation_id).first()
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found.")
    _require_write_access(db, actor, allocation.employee_id)
    if data.employee_id and data.employee_id != allocation.employee_id:
        _require_write_access(db, actor, data.employee_id)
    updated = update_allocation(db, allocation_id, data, actor.id)
    return serialize_allocation(db, updated)


@router.delete("/{allocation_id}", response_model=AllocationOut)
async def cancel_allocation_endpoint(
    allocation_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    allocation = db.query(Allocation).filter(Allocation.id == allocation_id).first()
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found.")
    _require_write_access(db, actor, allocation.employee_id)
    cancelled = cancel_allocation(db, allocation_id, actor.id)
    return serialize_allocation(db, cancelled)


@router.get("/bench", response_model=list[BenchEmployeeOut])
async def bench_availability(
    department: str | None = Query(None),
    designation: str | None = Query(None),
    max_allocation: int | None = Query(None, ge=0),
    available_within_days: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_bench_access(db, actor)

    query = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai")
    if _is_manager(actor) and not _is_hr_admin(actor):
        actor_name = f"{actor.first_name} {actor.last_name}".strip()
        query = query.filter((Employee.manager_id == actor.id) | (Employee.reporting_manager == actor_name))
    if department:
        query = query.filter(Employee.department.ilike(department))
    if designation:
        query = query.filter(Employee.designation.ilike(designation))

    employees = query.order_by(Employee.first_name.asc(), Employee.last_name.asc()).all()
    cutoff = date.today() + timedelta(days=available_within_days) if available_within_days is not None else None
    rows: list[dict] = []

    for employee in employees:
        summary = get_allocation_summary(db, employee.id)
        if max_allocation is not None and summary["total_active_allocation_percentage"] > max_allocation:
            continue
        if cutoff is not None:
            next_end_date = summary["next_end_date"]
            is_available_now = summary["total_active_allocation_percentage"] < 100
            if next_end_date is not None:
                if next_end_date > cutoff:
                    continue
            elif not is_available_now:
                continue

        rows.append(
            {
                "employee_id": employee.id,
                "employee_name": _employee_name(employee),
                "department": employee.department,
                "designation": employee.designation,
                "profile_image_url": employee.profile_image_url,
                "total_active_allocation_percentage": summary["total_active_allocation_percentage"],
                "available_capacity_percentage": summary["available_capacity_percentage"],
                "allocation_status": summary["allocation_status"],
                "active_project_names": _active_project_names(db, employee.id),
                "next_available_date": summary["next_end_date"],
            }
        )

    rows.sort(key=lambda item: (-item["available_capacity_percentage"], item["employee_name"].lower()))
    return rows


@router.get("/employee/{employee_id}", response_model=list[AllocationOut])
async def employee_allocations(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_read_access(db, actor, employee_id)
    return [serialize_allocation(db, item) for item in get_allocations_by_employee(db, employee_id)]


@router.get("/project/{project_id}", response_model=list[AllocationOut])
async def project_allocations(
    project_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    get_current_employee(db, current_user_id, current_user_email)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    allocations = (
        db.query(Allocation)
        .filter(Allocation.project_id == project_id)
        .order_by(Allocation.status.asc(), Allocation.start_date.desc(), Allocation.updated_at.desc())
        .all()
    )
    return [serialize_allocation(db, item) for item in allocations]


@router.get("/employee/{employee_id}/summary", response_model=AllocationSummaryOut)
async def employee_allocation_summary(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_read_access(db, actor, employee_id)
    return get_allocation_summary(db, employee_id)


@router.get("/employee/{employee_id}/capacity-check")
async def employee_capacity_check(
    employee_id: str,
    allocation_percentage: int = Query(..., ge=1, le=100),
    start_date: date = Query(...),
    end_date: date | None = Query(None),
    exclude_allocation_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_read_access(db, actor, employee_id)
    return capacity_check_payload(
        db,
        employee_id=employee_id,
        allocation_percentage=allocation_percentage,
        start_date=start_date,
        end_date=end_date,
        exclude_allocation_id=exclude_allocation_id,
    )


@router.get("/employee/{employee_id}/active", response_model=list[AllocationOut])
async def employee_active_allocations(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_read_access(db, actor, employee_id)
    return [serialize_allocation(db, item) for item in get_active_allocations(db, employee_id)]


@router.get("/employee/{employee_id}/upcoming", response_model=list[AllocationOut])
async def employee_upcoming_allocations(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_read_access(db, actor, employee_id)
    return [serialize_allocation(db, item) for item in get_upcoming_allocations(db, employee_id)]

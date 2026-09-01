"""Canonical employee-scoped read model for current project assignments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.employee import Employee
from app.models.operations import Project

MAX_CURRENT_PROJECT_ASSIGNMENTS = 20


class CurrentProjectAssignmentsStatus(str, Enum):
    AVAILABLE = "available"
    NO_CURRENT_ASSIGNMENTS = "no_current_assignments"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CurrentProjectAssignmentView:
    project_name: str
    project_code: str
    project_status: str
    allocation_role: str
    allocation_percentage: int
    allocation_start_date: date
    allocation_end_date: date | None
    project_manager_name: str | None


@dataclass(frozen=True)
class CurrentProjectAssignmentsView:
    status: CurrentProjectAssignmentsStatus
    as_of: date
    assignments: tuple[CurrentProjectAssignmentView, ...]
    truncated: bool = False
    safe_warnings: tuple[str, ...] = ()

    @property
    def assignment_count(self) -> int:
        return len(self.assignments)


def _employee_name(employee: Employee | None) -> str | None:
    if employee is None:
        return None
    parts = (employee.first_name, getattr(employee, "middle_name", None), employee.last_name)
    value = " ".join(part.strip() for part in parts if part and part.strip())
    return value or employee.work_email


def list_current_project_assignments(
    db: Session,
    actor_employee: Employee,
    as_of: date,
) -> CurrentProjectAssignmentsView:
    """Return current allocation-backed projects without mutating persistence."""

    allocations = (
        db.query(Allocation)
        .execution_options(autoflush=False)
        .filter(
            Allocation.employee_id == actor_employee.id,
            Allocation.status == "active",
            Allocation.project_id.isnot(None),
            Allocation.start_date <= as_of,
            or_(Allocation.end_date.is_(None), Allocation.end_date >= as_of),
        )
        .order_by(
            Allocation.project_id.asc(),
            Allocation.updated_at.desc(),
            Allocation.created_at.desc(),
            Allocation.id.desc(),
        )
        .all()
    )
    if not allocations:
        return CurrentProjectAssignmentsView(
            status=CurrentProjectAssignmentsStatus.NO_CURRENT_ASSIGNMENTS,
            as_of=as_of,
            assignments=(),
        )

    project_ids = tuple(dict.fromkeys(row.project_id for row in allocations if row.project_id))
    projects = {
        row.id: row
        for row in db.query(Project).execution_options(autoflush=False).filter(
            Project.id.in_(project_ids), Project.status == "active"
        ).all()
    }
    warnings: set[str] = set()
    if len(projects) != len(project_ids):
        warnings.add("inactive_or_missing_project_excluded")

    grouped: dict[str, list[Allocation]] = {}
    for allocation in allocations:
        if allocation.project_id in projects:
            grouped.setdefault(allocation.project_id, []).append(allocation)

    manager_ids = {
        project.project_manager_id
        for project in projects.values()
        if project.project_manager_id
    }
    managers = {
        row.id: _employee_name(row)
        for row in db.query(Employee).execution_options(autoflush=False).filter(Employee.id.in_(manager_ids)).all()
    } if manager_ids else {}

    assignments: list[CurrentProjectAssignmentView] = []
    for project_id, rows in grouped.items():
        project = projects[project_id]
        if len(rows) > 1:
            warnings.add("duplicate_active_allocations_combined")
        percentage = sum(int(row.allocation_percentage) for row in rows)
        if percentage > 100:
            percentage = 100
            warnings.add("allocation_percentage_capped")
        canonical = rows[0]
        assignments.append(CurrentProjectAssignmentView(
            project_name=" ".join(project.name.split()),
            project_code=" ".join(project.code.split()),
            project_status=project.status,
            allocation_role=" ".join(canonical.allocation_role.split()),
            allocation_percentage=percentage,
            allocation_start_date=min(row.start_date for row in rows),
            allocation_end_date=(
                None if any(row.end_date is None for row in rows)
                else max(row.end_date for row in rows if row.end_date is not None)
            ),
            project_manager_name=managers.get(project.project_manager_id),
        ))

    assignments.sort(key=lambda item: (item.project_name.casefold(), item.project_code.casefold()))
    truncated = len(assignments) > MAX_CURRENT_PROJECT_ASSIGNMENTS
    if truncated:
        assignments = assignments[:MAX_CURRENT_PROJECT_ASSIGNMENTS]
        warnings.add("assignment_results_truncated")
    status = (
        CurrentProjectAssignmentsStatus.AVAILABLE
        if assignments else CurrentProjectAssignmentsStatus.NO_CURRENT_ASSIGNMENTS
    )
    return CurrentProjectAssignmentsView(
        status=status,
        as_of=as_of,
        assignments=tuple(assignments),
        truncated=truncated,
        safe_warnings=tuple(sorted(warnings)),
    )

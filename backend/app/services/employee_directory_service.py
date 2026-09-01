"""Canonical read-only employee directory projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.organization import Department, Designation


class EmployeeManagerStatus(str, Enum):
    AVAILABLE = "available"
    NOT_ASSIGNED = "not_assigned"
    INVALID_REFERENCE = "invalid_reference"
    INACTIVE_MANAGER = "inactive_manager"
    AMBIGUOUS_LEGACY_REFERENCE = "ambiguous_legacy_reference"
    SELF_REFERENCE = "self_reference"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class EmployeeManagerView:
    status: EmployeeManagerStatus
    display_name: str | None
    job_title: str | None
    department: str | None
    work_email: str | None
    source: str | None
    as_of: datetime
    safe_warning: str | None = None


@dataclass(frozen=True)
class EmployeeDirectoryProfile:
    employee_id: str
    display_name: str
    work_email: str | None
    job_title: str | None
    department: str | None
    manager_name: str | None
    employment_status: str | None
    work_location: str | None
    source: str
    as_of: datetime


def _normalize(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _name(employee: Employee) -> str:
    return " ".join(f"{employee.first_name} {employee.last_name}".split())


def _searchable_text(profile: EmployeeDirectoryProfile, role: str | None) -> str:
    return _normalize(
        " ".join(
            value
            for value in (
                profile.display_name,
                profile.work_email,
                profile.job_title,
                profile.department,
                profile.manager_name,
                profile.work_location,
                role,
            )
            if value
        )
    )


def _active_directory_employees(db: Session) -> list[Employee]:
    return (
        db.query(Employee)
        .filter(
            Employee.is_active.is_(True),
            Employee.employment_status == "active",
            Employee.account_locked.is_(False),
            Employee.work_email != "superadmin@reknew.ai",
        )
        .order_by(Employee.first_name.asc(), Employee.last_name.asc())
        .all()
    )


def _manager_name(
    employee: Employee,
    *,
    employees_by_id: dict[str, Employee],
    employees: list[Employee],
) -> str | None:
    if employee.manager_id and employee.manager_id in employees_by_id and employee.manager_id != employee.id:
        return _name(employees_by_id[employee.manager_id])

    legacy = _normalize(employee.reporting_manager)
    if not legacy or legacy in {"self", _normalize(employee.work_email), _normalize(_name(employee))}:
        return None
    matches = [
        row for row in employees
        if row.id != employee.id and legacy in {_normalize(_name(row)), _normalize(row.work_email)}
    ]
    if len(matches) == 1:
        return _name(matches[0])
    return None


def build_employee_directory_profile(
    db: Session,
    employee: Employee,
    *,
    employees_by_id: dict[str, Employee] | None = None,
    employees: list[Employee] | None = None,
    source: str = "directory",
) -> EmployeeDirectoryProfile:
    employees = employees or _active_directory_employees(db)
    employees_by_id = employees_by_id or {row.id: row for row in employees}
    designation = (
        db.query(Designation).filter(Designation.id == employee.designation_id).first()
        if employee.designation_id else None
    )
    department = (
        db.query(Department).filter(Department.id == employee.department_id).first()
        if employee.department_id else None
    )
    return EmployeeDirectoryProfile(
        employee_id=employee.id,
        display_name=_name(employee),
        work_email=employee.work_email,
        job_title=(designation.name if designation and designation.is_active else employee.designation),
        department=(department.name if department and department.is_active else (employee.department or None)),
        manager_name=_manager_name(employee, employees_by_id=employees_by_id, employees=employees),
        employment_status=employee.employment_status,
        work_location=employee.work_location or employee.work_city or employee.work_state or employee.work_country,
        source=source,
        as_of=datetime.now(timezone.utc),
    )


def get_employee_directory_self_profile(db: Session, actor_employee: Employee) -> EmployeeDirectoryProfile:
    employees = _active_directory_employees(db)
    employees_by_id = {row.id: row for row in employees}
    current = employees_by_id.get(actor_employee.id, actor_employee)
    return build_employee_directory_profile(
        db,
        current,
        employees_by_id=employees_by_id,
        employees=employees,
        source="self",
    )


def search_employee_directory(
    db: Session,
    *,
    search: str | None = None,
    department: str | None = None,
    title: str | None = None,
    manager_only: bool = False,
    limit: int = 5,
) -> list[EmployeeDirectoryProfile]:
    employees = _active_directory_employees(db)
    employees_by_id = {row.id: row for row in employees}
    profiles = [
        build_employee_directory_profile(
            db,
            employee,
            employees_by_id=employees_by_id,
            employees=employees,
        )
        for employee in employees
    ]

    normalized_search = _normalize(search)
    search_tokens = tuple(token for token in normalized_search.split() if token)
    normalized_department = _normalize(department)
    normalized_title = _normalize(title)

    def matches(profile: EmployeeDirectoryProfile, role: str | None) -> bool:
        haystack = _searchable_text(profile, role)
        if manager_only and "manager" not in haystack:
            return False
        if normalized_department and normalized_department not in _normalize(profile.department):
            return False
        if normalized_title and normalized_title not in _normalize(profile.job_title):
            return False
        if not search_tokens:
            return True
        return all(re.search(rf"\b{re.escape(token)}\b", haystack) or token in haystack for token in search_tokens)

    filtered: list[tuple[int, EmployeeDirectoryProfile]] = []
    for profile in profiles:
        employee = employees_by_id[profile.employee_id]
        if not matches(profile, employee.role):
            continue
        haystack = _searchable_text(profile, employee.role)
        exact_name = int(_normalize(profile.display_name) == normalized_search)
        exact_email = int(_normalize(profile.work_email) == normalized_search)
        phrase_match = int(bool(normalized_search and normalized_search in haystack))
        filtered.append((exact_email * 4 + exact_name * 3 + phrase_match * 2 + len(search_tokens), profile))

    filtered.sort(
        key=lambda item: (
            -item[0],
            _normalize(item[1].display_name),
            _normalize(item[1].job_title),
        )
    )
    return [profile for _, profile in filtered[: max(1, min(limit, 10))]]


def _missing(status: EmployeeManagerStatus, warning: str) -> EmployeeManagerView:
    return EmployeeManagerView(status, None, None, None, None, None, datetime.now(timezone.utc), warning)


def _projection(db: Session, manager: Employee, source: str) -> EmployeeManagerView:
    designation = (
        db.query(Designation).filter(Designation.id == manager.designation_id).first()
        if manager.designation_id else None
    )
    department = (
        db.query(Department).filter(Department.id == manager.department_id).first()
        if manager.department_id else None
    )
    return EmployeeManagerView(
        status=EmployeeManagerStatus.AVAILABLE,
        display_name=_name(manager),
        job_title=(designation.name if designation and designation.is_active else manager.designation),
        department=(department.name if department and department.is_active else (manager.department or None)),
        work_email=manager.work_email,
        source=source,
        as_of=datetime.now(timezone.utc),
    )


def get_my_reporting_manager(db: Session, actor_employee: Employee) -> EmployeeManagerView:
    """Resolve the actor's reporting manager without accepting a target identity."""

    if actor_employee.manager_id:
        if actor_employee.manager_id == actor_employee.id:
            return _missing(EmployeeManagerStatus.SELF_REFERENCE, "MANAGER_SELF_REFERENCE")
        manager = db.query(Employee).filter(Employee.id == actor_employee.manager_id).first()
        if manager is None:
            return _missing(EmployeeManagerStatus.INVALID_REFERENCE, "MANAGER_REFERENCE_INVALID")
        if not manager.is_active or manager.employment_status != "active" or manager.account_locked:
            return _missing(EmployeeManagerStatus.INACTIVE_MANAGER, "MANAGER_NOT_ACTIVE")
        return _projection(db, manager, "manager_id")

    legacy = _normalize(actor_employee.reporting_manager)
    if not legacy:
        return _missing(EmployeeManagerStatus.NOT_ASSIGNED, "MANAGER_NOT_ASSIGNED")
    if legacy in {"self", _normalize(actor_employee.work_email), _normalize(_name(actor_employee))}:
        return _missing(EmployeeManagerStatus.SELF_REFERENCE, "MANAGER_SELF_REFERENCE")
    candidates = db.query(Employee).filter(Employee.id != actor_employee.id).all()
    matches = [row for row in candidates if legacy in {_normalize(_name(row)), _normalize(row.work_email)}]
    if len(matches) > 1:
        return _missing(EmployeeManagerStatus.AMBIGUOUS_LEGACY_REFERENCE, "MANAGER_LEGACY_AMBIGUOUS")
    active = [
        row for row in matches
        if row.is_active and row.employment_status == "active" and not row.account_locked
    ]
    if len(active) == 1:
        return _projection(db, active[0], "legacy_reporting_manager")
    if matches:
        return _missing(EmployeeManagerStatus.INACTIVE_MANAGER, "MANAGER_NOT_ACTIVE")
    return _missing(EmployeeManagerStatus.INVALID_REFERENCE, "MANAGER_LEGACY_NOT_FOUND")

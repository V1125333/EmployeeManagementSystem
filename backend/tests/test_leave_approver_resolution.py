from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.employee import Employee
from app.models.leave_attendance import LeaveType
from app.models.organization import Department, Designation
from app.services.leave_approver_service import resolve_leave_approver_with_reason


@pytest.fixture()
def approver_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Department.__table__,
            Designation.__table__,
            Employee.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    yield db
    db.close()
    engine.dispose()


def employee(employee_id: str, *, role: str = "employee", **overrides) -> Employee:
    values = {
        "id": employee_id,
        "first_name": employee_id.title(),
        "last_name": "Person",
        "work_email": f"{employee_id}@example.com",
        "phone": "1000000000",
        "workforce_type": "full_time",
        "role": role,
        "employment_status": "active",
        "is_active": True,
        "joining_date": date(2025, 1, 1),
        "reporting_manager": "",
    }
    values.update(overrides)
    return Employee(**values)


def test_normalized_manager_id_resolves_active_employee_regardless_of_role(approver_db):
    manager = employee(
        "normalized-manager",
        role="employee",
        first_name="Avery",
        last_name="Lead",
    )
    report = employee("normalized-report", manager_id=manager.id)
    approver_db.add_all([manager, report])
    approver_db.commit()

    resolution = resolve_leave_approver_with_reason(approver_db, report)

    assert resolution.is_resolved
    assert resolution.approver.employee_id == manager.id
    assert resolution.approver.display_name == "Avery Lead"
    assert resolution.approver.source == "manager_id"


def test_supported_legacy_reporting_manager_normalizes_name(approver_db):
    manager = employee(
        "legacy-manager",
        first_name="David",
        last_name="Park",
    )
    report = employee(
        "legacy-report",
        reporting_manager="  DAVID   park  ",
    )
    approver_db.add_all([manager, report])
    approver_db.commit()

    resolution = resolve_leave_approver_with_reason(approver_db, report)

    assert resolution.is_resolved
    assert resolution.approver.employee_id == manager.id
    assert resolution.approver.source == "legacy_reporting_manager"


def test_missing_manager_is_reported_without_fallback(approver_db):
    report = employee("missing-manager")
    approver_db.add(report)
    approver_db.commit()

    resolution = resolve_leave_approver_with_reason(approver_db, report)

    assert not resolution.is_resolved
    assert resolution.failure_code == "APPROVER_MANAGER_NOT_ASSIGNED"


def test_inactive_normalized_manager_is_rejected(approver_db):
    manager = employee(
        "inactive-manager",
        is_active=False,
        employment_status="inactive",
    )
    report = employee("inactive-report", manager_id=manager.id)
    approver_db.add_all([manager, report])
    approver_db.commit()

    resolution = resolve_leave_approver_with_reason(approver_db, report)

    assert not resolution.is_resolved
    assert resolution.failure_code == "APPROVER_MANAGER_INACTIVE"


def test_invalid_normalized_manager_reference_is_reported(approver_db):
    report = employee(
        "invalid-report",
        manager_id="employee-that-does-not-exist",
        reporting_manager="Some Legacy Manager",
    )
    approver_db.add(report)
    approver_db.commit()

    resolution = resolve_leave_approver_with_reason(approver_db, report)

    assert not resolution.is_resolved
    assert resolution.failure_code == "APPROVER_MANAGER_REFERENCE_INVALID"


@pytest.mark.parametrize(
    ("manager_id", "legacy"),
    [
        ("self-report", ""),
        (None, "Self"),
        (None, "self-report@example.com"),
        (None, "Self-Report Person"),
    ],
)
def test_self_manager_relationship_is_rejected(
    approver_db, manager_id, legacy
):
    report = employee(
        "self-report",
        manager_id=manager_id,
        reporting_manager=legacy,
    )
    approver_db.add(report)
    approver_db.commit()

    resolution = resolve_leave_approver_with_reason(approver_db, report)

    assert not resolution.is_resolved
    assert resolution.failure_code == "APPROVER_SELF_REFERENCE"


def test_top_level_super_admin_has_no_implicit_approver(approver_db):
    unrelated_admin = employee("unrelated-admin", role="hr_admin")
    top_level = employee(
        "top-level",
        role="super_admin",
        first_name="Super",
        last_name="Admin",
        reporting_manager="Self",
    )
    approver_db.add_all([unrelated_admin, top_level])
    approver_db.commit()

    resolution = resolve_leave_approver_with_reason(approver_db, top_level)

    assert not resolution.is_resolved
    assert resolution.failure_code == "APPROVER_SELF_REFERENCE"
    assert resolution.approver is None


def test_policy_defined_alternate_approver_is_not_in_current_policy_model(
    approver_db,
):
    """The current policy schema cannot route to an alternate approver."""
    unrelated_hr = employee("policy-hr", role="hr_admin")
    report = employee("policy-report")
    approver_db.add_all([unrelated_hr, report])
    approver_db.commit()

    assert {
        "approver_id",
        "alternate_approver_id",
        "approval_route",
    }.isdisjoint(LeaveType.__table__.columns.keys())
    resolution = resolve_leave_approver_with_reason(approver_db, report)

    assert not resolution.is_resolved
    assert resolution.failure_code == "APPROVER_MANAGER_NOT_ASSIGNED"
    assert resolution.approver is None

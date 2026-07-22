from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.attendance import router
from app.core.database import Base, get_db
from app.models.employee import Employee
from app.models.leave_attendance import Attendance
from app.models.organization import Department, Designation


def _employee(joining_date: date) -> Employee:
    return Employee(
        id="attendance-employee",
        first_name="Asha",
        last_name="Rao",
        work_email="asha@example.com",
        phone="1000000000",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        reporting_manager="Manager",
        joining_date=joining_date,
        date_of_joining=joining_date,
        work_location="US",
    )


def test_attendance_range_is_bounded_by_joining_date_and_today():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Department.__table__, Designation.__table__, Employee.__table__, Attendance.__table__])
    Session = sessionmaker(bind=engine)
    joining_date = date.today() - timedelta(days=10)
    with Session() as db:
        db.add(_employee(joining_date))
        db.add_all([
            Attendance(employee_id="attendance-employee", date=joining_date, check_in=datetime.utcnow(), status="present"),
            Attendance(employee_id="attendance-employee", date=date.today(), check_in=datetime.utcnow(), status="present"),
        ])
        db.commit()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    headers = {"x-user-id": "attendance-employee", "x-user-email": "ASHA@EXAMPLE.COM"}
    with TestClient(app) as client:
        context = client.get("/api/v1/attendance/me/context", headers=headers)
        assert context.status_code == 200
        assert context.json()["joining_date"] == joining_date.isoformat()

        invalid = client.get(
            "/api/v1/attendance/me/history",
            params={"date_from": (joining_date - timedelta(days=1)).isoformat(), "date_to": date.today().isoformat()},
            headers=headers,
        )
        assert invalid.status_code == 400

        valid = client.get(
            "/api/v1/attendance/me/history",
            params={"date_from": joining_date.isoformat(), "date_to": date.today().isoformat()},
            headers=headers,
        )
        assert valid.status_code == 200
        assert [row["date"] for row in valid.json()] == [date.today().isoformat(), joining_date.isoformat()]

"""Seed safe, repeatable showcase data without changing existing logins.

Run from the backend root with:
    python scripts/seed_showcase_data.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import func


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.models.allocation import Allocation  # noqa: E402
from app.models.employee import Employee  # noqa: E402
from app.models.leave_attendance import Attendance, LeaveRequest, LeaveType  # noqa: E402
from app.models.operations import Announcement, Project  # noqa: E402


EMPLOYEES = (
    ("Priya", "Sharma", "priya.sharma@demo.reknew.ai", "Engineering", "Engineering Lead", "manager", "Onshore"),
    ("David", "Park", "david.park@demo.reknew.ai", "Product", "Product Manager", "manager", "Remote"),
    ("Sarah", "Chen", "sarah.chen@demo.reknew.ai", "People", "People Operations Partner", "hr_admin", "Hybrid"),
    ("Marcus", "Johnson", "marcus.johnson@demo.reknew.ai", "Engineering", "Senior Engineer", "employee", "Remote"),
    ("Maya", "Patel", "maya.patel@demo.reknew.ai", "Engineering", "Data Analyst", "employee", "Onshore"),
    ("Tom", "Keller", "tom.keller@demo.reknew.ai", "Design", "Senior Product Designer", "employee", "Hybrid"),
    ("Aaliyah", "Brooks", "aaliyah.brooks@demo.reknew.ai", "Marketing", "Marketing Specialist", "employee", "Remote"),
    ("James", "Rivera", "james.rivera@demo.reknew.ai", "Sales", "Account Executive", "employee", "Onshore"),
    ("Sofia", "Reyes", "sofia.reyes@demo.reknew.ai", "Design", "UX Designer", "employee", "Hybrid"),
    ("Amir", "Hassan", "amir.hassan@demo.reknew.ai", "Engineering", "DevOps Engineer", "employee", "Remote"),
)


def find_employee(db, email: str) -> Employee | None:
    return db.query(Employee).filter(func.lower(Employee.work_email) == email.lower()).first()


def seed_employees(db) -> tuple[dict[str, Employee], int]:
    people: dict[str, Employee] = {}
    created = 0
    manager_name = "Priya Sharma"
    for index, (first, last, email, department, designation, role, location) in enumerate(EMPLOYEES):
        employee = find_employee(db, email)
        if employee is None:
            joined = date.today() - timedelta(days=150 + index * 73)
            employee = Employee(
                first_name=first,
                last_name=last,
                work_email=email,
                phone=f"555010{index:04d}",
                date_of_birth=date(1988 + index, (index % 12) + 1, min(10 + index, 28)),
                gender="female" if index in {0, 2, 4, 6, 8} else "male",
                workforce_type="full_time",
                employment_type="full_time",
                role=role,
                employment_status="active",
                location=location,
                joining_date=joined,
                date_of_joining=joined,
                work_location=location,
                department=department,
                designation=designation,
                reporting_manager="" if role == "manager" else manager_name,
                emergency_contact_name="Demo Contact",
                emergency_contact_phone="5550199999",
                is_active=True,
                is_first_login=True,
            )
            db.add(employee)
            db.flush()
            created += 1
        people[email] = employee

    priya = people["priya.sharma@demo.reknew.ai"]
    for employee in people.values():
        if employee.id != priya.id and not employee.manager_id:
            employee.manager_id = priya.id
    return people, created


def seed_projects(db, admin: Employee, people: dict[str, Employee]) -> tuple[dict[str, Project], int]:
    definitions = (
        ("DEMO-ORB", "Orbit Workforce Platform", "Reknew", "priya.sharma@demo.reknew.ai"),
        ("DEMO-INS", "People Analytics Insights", "Northstar Group", "david.park@demo.reknew.ai"),
    )
    projects: dict[str, Project] = {}
    created = 0
    for code, name, client, manager_email in definitions:
        project = db.query(Project).filter(Project.code == code).first()
        if project is None:
            project = Project(
                code=code,
                name=name,
                description="Showcase project generated for the Reknew Orbit demo.",
                client_name=client,
                start_date=date.today() - timedelta(days=120),
                end_date=date.today() + timedelta(days=240),
                status="active",
                project_manager_id=people[manager_email].id,
                created_by=admin.id,
            )
            db.add(project)
            db.flush()
            created += 1
        projects[code] = project
    return projects, created


def seed_allocations(db, admin: Employee, people: dict[str, Employee], projects: dict[str, Project]) -> int:
    assignments = (
        ("priya.sharma@demo.reknew.ai", "DEMO-ORB", 100, "Engineering Lead"),
        ("marcus.johnson@demo.reknew.ai", "DEMO-ORB", 100, "Backend Engineer"),
        ("tom.keller@demo.reknew.ai", "DEMO-ORB", 75, "Product Designer"),
        ("amir.hassan@demo.reknew.ai", "DEMO-ORB", 100, "DevOps Engineer"),
        ("david.park@demo.reknew.ai", "DEMO-INS", 100, "Project Manager"),
        ("maya.patel@demo.reknew.ai", "DEMO-INS", 80, "Data Analyst"),
        ("sofia.reyes@demo.reknew.ai", "DEMO-INS", 60, "UX Researcher"),
    )
    created = 0
    for email, code, percentage, role in assignments:
        employee = people[email]
        project = projects[code]
        exists = db.query(Allocation).filter(
            Allocation.employee_id == employee.id,
            Allocation.project_id == project.id,
            Allocation.status == "active",
        ).first()
        if exists:
            continue
        db.add(Allocation(
            employee_id=employee.id,
            project_id=project.id,
            project_name=project.name,
            manager_id=project.project_manager_id or admin.id,
            allocation_percentage=percentage,
            allocation_role=role,
            billing_type="billable",
            status="active",
            start_date=date.today() - timedelta(days=90),
            end_date=date.today() + timedelta(days=180),
            notes="Showcase allocation",
            created_by=admin.id,
        ))
        created += 1
    return created


def seed_attendance(db, people: dict[str, Employee]) -> int:
    created = 0
    current = date.today()
    workdays: list[date] = []
    while len(workdays) < 10:
        if current.weekday() < 5:
            workdays.append(current)
        current -= timedelta(days=1)

    for day_index, workday in enumerate(workdays):
        for employee_index, employee in enumerate(people.values()):
            if db.query(Attendance).filter(Attendance.employee_id == employee.id, Attendance.date == workday).first():
                continue
            if (day_index + employee_index) % 9 == 0:
                continue
            check_in = datetime.combine(workday, time(9, 0)) + timedelta(minutes=(employee_index % 4) * 7)
            db.add(Attendance(
                employee_id=employee.id,
                date=workday,
                check_in=check_in,
                check_out=check_in + timedelta(hours=8, minutes=30),
                total_hours=8.5,
                status="wfh" if employee_index % 4 == 1 else "present",
                source="system",
                remarks="Showcase attendance",
            ))
            created += 1
    return created


def seed_leave_requests(db, admin: Employee, people: dict[str, Employee]) -> int:
    leave_type = db.query(LeaveType).filter(LeaveType.code == "CL").first()
    if leave_type is None:
        return 0
    created = 0
    for email, offset, duration in (
        ("aaliyah.brooks@demo.reknew.ai", 7, 2),
        ("james.rivera@demo.reknew.ai", 14, 3),
    ):
        employee = people[email]
        marker = "Showcase leave request"
        if db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee.id, LeaveRequest.reason == marker).first():
            continue
        start = date.today() + timedelta(days=offset)
        db.add(LeaveRequest(
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            start_date=start,
            end_date=start + timedelta(days=duration - 1),
            total_days=duration,
            reason=marker,
            status="pending",
        ))
        created += 1
    return created


def seed_announcement(db, admin: Employee) -> int:
    title = "Welcome to the Reknew Orbit showcase"
    if db.query(Announcement).filter(Announcement.title == title).first():
        return 0
    now = datetime.now()
    db.add(Announcement(
        title=title,
        description="Explore workforce insights, allocations, attendance, and employee workflows.",
        message="Explore workforce insights, allocations, attendance, and employee workflows.",
        type="general",
        announcement_type="general",
        priority="normal",
        audience_type="everyone",
        status="published",
        publish_at=now,
        expires_at=now + timedelta(days=90),
        created_by=admin.id,
        published_by=admin.id,
        is_pinned=True,
        is_active=True,
        publish_date=date.today(),
        expiry_date=date.today() + timedelta(days=90),
    ))
    return 1


def main() -> None:
    db = SessionLocal()
    try:
        admin = find_employee(db, "superadmin@reknew.ai")
        if admin is None:
            raise RuntimeError("Create superadmin@reknew.ai before seeding showcase data.")
        people, employee_count = seed_employees(db)
        projects, project_count = seed_projects(db, admin, people)
        allocation_count = seed_allocations(db, admin, people, projects)
        attendance_count = seed_attendance(db, people)
        leave_count = seed_leave_requests(db, admin, people)
        announcement_count = seed_announcement(db, admin)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Showcase data ready")
    print(f"Employees created: {employee_count}")
    print(f"Projects created: {project_count}")
    print(f"Allocations created: {allocation_count}")
    print(f"Attendance records created: {attendance_count}")
    print(f"Leave requests created: {leave_count}")
    print(f"Announcements created: {announcement_count}")


if __name__ == "__main__":
    main()

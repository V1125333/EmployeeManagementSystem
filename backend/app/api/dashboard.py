"""
Dashboard API — pulls real KPI data from database.
"""

from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import and_, exists, func, or_
from app.core.database import get_db
from app.models.employee import Employee
from app.models.allocation import Allocation
from app.models.leave_attendance import LeaveRequest, Attendance, AttendanceCorrection
from app.models.operations import Announcement
from app.models.training import TrainingEnrollment
from app.services.settings_service import get_current_employee

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def active_announcement_status(announcement: Announcement, now: datetime) -> bool:
    if announcement.status != "published":
        return False
    if announcement.publish_at and announcement.publish_at > now:
        return False
    if announcement.expires_at and announcement.expires_at <= now:
        return False
    return True


def employee_name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip()


@router.get("/employee-context")
async def get_employee_dashboard_context(
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    """Return the signed-in employee's reporting context and direct-report status."""
    actor = get_current_employee(db, current_user_id, current_user_email)
    manager = db.query(Employee).filter(Employee.id == actor.manager_id).first() if actor.manager_id else None
    if not manager and actor.reporting_manager:
        manager_reference = actor.reporting_manager.strip().lower()
        manager = next((
            employee for employee in db.query(Employee).filter(Employee.is_active.is_(True)).all()
            if employee.id != actor.id and manager_reference in {
                employee_name(employee).lower(),
                employee.work_email.lower(),
            }
        ), None)

    actor_references = {employee_name(actor).lower(), actor.work_email.lower()}
    direct_reports = [
        employee for employee in db.query(Employee).filter(Employee.is_active.is_(True)).all()
        if employee.id != actor.id and (
            employee.manager_id == actor.id
            or (employee.reporting_manager or "").strip().lower() in actor_references
        )
    ]
    direct_reports.sort(key=lambda employee: employee_name(employee).lower())
    report_ids = [employee.id for employee in direct_reports]
    attendance_by_employee = {
        attendance.employee_id: attendance
        for attendance in db.query(Attendance).filter(
            Attendance.employee_id.in_(report_ids),
            Attendance.date == date.today(),
        ).all()
    } if report_ids else {}
    employees_on_leave = {
        employee_id for (employee_id,) in db.query(LeaveRequest.employee_id).filter(
            LeaveRequest.employee_id.in_(report_ids),
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= date.today(),
            LeaveRequest.end_date >= date.today(),
        ).all()
    } if report_ids else set()

    def person_payload(employee: Employee | None) -> dict | None:
        if not employee:
            return None
        return {
            "id": employee.id,
            "name": employee_name(employee),
            "email": employee.work_email,
            "designation": employee.designation or employee.role.replace("_", " ").title(),
            "department": employee.department or "Not assigned",
            "profile_image_url": employee.profile_image_url,
        }

    team = []
    for employee in direct_reports:
        attendance = attendance_by_employee.get(employee.id)
        status = "on_leave" if employee.id in employees_on_leave else (
            "working" if attendance and attendance.check_in and not attendance.check_out else "not_checked_in"
        )
        team.append({**person_payload(employee), "today_status": status})

    return {
        "employee": person_payload(actor),
        "manager": person_payload(manager),
        "direct_reports": team,
    }


@router.get("/kpis")
async def get_kpis(db: Session = Depends(get_db)):
    """Get all dashboard KPI metrics from real data."""

    today = date.today()
    now = datetime.utcnow()

    # Employee counts (exclude super admin)
    base = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai")
    total = base.count()
    active = base.filter(Employee.employment_status == "active").count()
    inactive = base.filter(Employee.employment_status != "active").count()

    # New starters in the current calendar month.
    month_start = today.replace(day=1)
    new_this_month_employees = base.filter(
        Employee.joining_date >= month_start,
        Employee.joining_date <= today,
    ).order_by(Employee.joining_date.asc()).all()
    new_this_month = [
        {
            "employee_id": employee.id,
            "name": employee_name(employee),
            "date": employee.joining_date.isoformat(),
            "subtitle": employee.designation or employee.department,
        }
        for employee in new_this_month_employees
    ]

    # Bench capacity: active non-trainees without a current active project allocation.
    active_allocation_exists = exists().where(and_(
        Allocation.employee_id == Employee.id,
        Allocation.project_id.isnot(None),
        Allocation.status == "active",
        Allocation.start_date <= today,
        or_(Allocation.end_date.is_(None), Allocation.end_date >= today),
    ))
    trainee_expression = or_(
        func.lower(func.replace(func.replace(Employee.role, " ", "_"), "-", "_")) == "trainee",
        func.lower(Employee.workforce_type).like("%trainee%"),
    )
    bench_employees = base.filter(
        Employee.employment_status == "active",
        ~trainee_expression,
        ~active_allocation_exists,
    ).order_by(Employee.first_name.asc(), Employee.last_name.asc()).all()

    # Pending leave requests
    pending_leave = db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count()

    # Today's attendance rate
    today_present = db.query(Attendance).filter(
        Attendance.date == today,
        Attendance.status.in_(["present", "wfh", "late"])
    ).count()
    rate = round((today_present / active * 100)) if active > 0 else 0
    attendance_rate = rate

    # Upcoming birthdays (next 7 days)
    upcoming_birthdays = []
    employees = base.filter(Employee.date_of_birth.isnot(None), Employee.employment_status == "active").all()
    for emp in employees:
        bday_this_year = emp.date_of_birth.replace(year=today.year)
        if bday_this_year < today:
            bday_this_year = emp.date_of_birth.replace(year=today.year + 1)
        days_until = (bday_this_year - today).days
        if 0 <= days_until <= 7:
            upcoming_birthdays.append({
                "employee_id": emp.id,
                "name": employee_name(emp),
                "date": bday_this_year.isoformat(),
                "subtitle": f"{days_until} day{'s' if days_until != 1 else ''} away" if days_until else "Today",
            })
    upcoming_birthdays.sort(key=lambda item: item["date"])

    # Work anniversaries this month
    anniversaries = []
    for emp in base.filter(Employee.employment_status == "active").all():
        if emp.joining_date and emp.joining_date.month == today.month and emp.joining_date.year < today.year:
            years = today.year - emp.joining_date.year
            anniversary_date = emp.joining_date.replace(year=today.year)
            anniversaries.append({
                "employee_id": emp.id,
                "name": employee_name(emp),
                "date": anniversary_date.isoformat(),
                "subtitle": f"{years} year{'s' if years != 1 else ''}",
            })
    anniversaries.sort(key=lambda item: item["date"])

    return {
        "kpis": [
            {"label": "Total Employees", "value": str(total), "icon": "Users", "color": "#66785F"},
            {"label": "Active Employees", "value": str(active), "icon": "UserCheck", "color": "#7BAE7F"},
            {"label": "Inactive", "value": str(inactive), "icon": "UserX", "color": "#9CA3AF"},
            {"label": "Pending Leave", "value": str(pending_leave), "icon": "Calendar", "color": "#D6A85F"},
            {"label": "Today's Attendance", "value": attendance_rate, "icon": "CheckCircle", "color": "#7E9BB7"},
            {"label": "New This Month", "value": str(len(new_this_month)), "trend": "this month", "icon": "UserPlus", "color": "#D97A34", "details": new_this_month},
            {"label": "Upcoming Birthdays", "value": str(len(upcoming_birthdays)), "trend": "this week", "icon": "Cake", "color": "#D97C7C", "details": upcoming_birthdays},
            {"label": "Work Anniversaries", "value": str(len(anniversaries)), "trend": "this month", "icon": "Award", "color": "#A3B18A", "details": anniversaries},
            {
                "label": "Bench Capacity",
                "value": str(len(bench_employees)),
                "trend": "available now",
                "icon": "BriefcaseBusiness",
                "color": "#D97A34",
            },
        ]
    }


@router.get("/pending-tasks")
async def get_pending_tasks(db: Session = Depends(get_db)):
    """Get pending task counts for dashboard widgets."""

    pending_leave = db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count()
    pending_corrections = db.query(AttendanceCorrection).filter(AttendanceCorrection.status == "pending").count()

    # Onboarding = employees who haven't completed first-time setup
    pending_onboarding = db.query(Employee).filter(
        Employee.is_first_login == True,
        Employee.work_email != "superadmin@reknew.ai",
    ).count()

    # Profile updates = employees missing key fields (DOB, gender, emergency contact)
    missing_profiles = db.query(Employee).filter(
        Employee.work_email != "superadmin@reknew.ai",
        Employee.employment_status == "active",
    ).filter(
        (Employee.date_of_birth.is_(None)) |
        (Employee.gender.is_(None)) |
        (Employee.emergency_contact_name.is_(None))
    ).count()

    return {
        "tasks": [
            {"label": "Leave Approvals", "count": pending_leave, "urgent": min(pending_leave, 2), "color": "#D6A85F"},
            {"label": "Attendance Corrections", "count": pending_corrections, "urgent": 0, "color": "#7E9BB7"},
            {"label": "Onboarding Tasks", "count": pending_onboarding, "urgent": min(pending_onboarding, 1), "color": "#7BAE7F"},
            {"label": "Profile Updates", "count": missing_profiles, "urgent": 0, "color": "#A3B18A"},
        ]
    }


@router.get("/announcements")
async def get_dashboard_announcements(db: Session = Depends(get_db)):
    """Get active announcements for the compact dashboard widget."""

    now = datetime.utcnow()
    records = db.query(Announcement).filter(
        Announcement.status == "published",
    ).order_by(
        Announcement.is_pinned.desc(),
        Announcement.publish_at.desc().nullslast(),
        Announcement.created_at.desc(),
    ).limit(20).all()

    announcements = []
    for item in records:
        if not active_announcement_status(item, now):
            continue
        item_type = item.announcement_type or item.type or "general"
        if item.priority == "critical" or item_type == "emergency":
            item_type = "urgent"
        announcements.append({
            "id": item.id,
            "title": item.title,
            "description": item.message or item.description,
            "type": item_type,
            "publish_date": item.publish_at.isoformat() if item.publish_at else item.created_at.isoformat() if item.created_at else None,
            "is_pinned": bool(item.is_pinned),
        })

    return {"announcements": announcements}


@router.get("/department-chart")
async def get_department_chart(db: Session = Depends(get_db)):
    """Get employee count per department."""

    results = db.query(
        Employee.department, func.count(Employee.id)
    ).filter(
        Employee.work_email != "superadmin@reknew.ai",
        Employee.employment_status == "active",
    ).group_by(Employee.department).all()

    return {
        "departments": [{"dept": dept, "count": count} for dept, count in results if dept]
    }


@router.get("/attendance-trend")
async def get_attendance_trend(db: Session = Depends(get_db)):
    """Get daily attendance rate for last 10 working days."""

    today = date.today()
    active_count = db.query(Employee).filter(
        Employee.work_email != "superadmin@reknew.ai",
        Employee.employment_status == "active",
    ).count()

    if active_count == 0:
        return {"trend": []}

    trend = []
    check_date = today
    days_collected = 0

    while days_collected < 10:
        if check_date.weekday() < 5:  # weekdays only
            present = db.query(Attendance).filter(
                Attendance.date == check_date,
                Attendance.status.in_(["present", "wfh", "late"])
            ).count()
            rate = round((present / active_count) * 100, 1)
            trend.append({
                "day": check_date.strftime("%d %b"),
                "rate": rate,
            })
            days_collected += 1
        check_date -= timedelta(days=1)

    trend.reverse()  # oldest first
    return {"trend": trend}


@router.get("/on-leave-today")
async def get_on_leave_today(db: Session = Depends(get_db)):
    """Get employees on approved leave today."""

    today = date.today()
    on_leave = db.query(LeaveRequest).filter(
        LeaveRequest.status == "approved",
        LeaveRequest.start_date <= today,
        LeaveRequest.end_date >= today,
    ).all()

    result = []
    for lr in on_leave:
        emp = db.query(Employee).filter(Employee.id == lr.employee_id).first()
        if emp:
            result.append({
                "name": f"{emp.first_name} {emp.last_name}",
                "avatar": f"{emp.first_name[0]}{emp.last_name[0]}".upper(),
                "type": "Leave",
                "duration": f"{lr.start_date.strftime('%b %d')}–{lr.end_date.strftime('%b %d')}",
            })

    return {"on_leave": result}


@router.get("/leave-calendar")
async def get_leave_calendar(db: Session = Depends(get_db)):
    """Get leave count per day for current month."""

    today = date.today()
    first_day = today.replace(day=1)
    if today.month == 12:
        last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    calendar = []
    for day_num in range(1, last_day.day + 1):
        d = date(today.year, today.month, day_num)
        count = db.query(LeaveRequest).filter(
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= d,
            LeaveRequest.end_date >= d,
        ).count()
        calendar.append({"day": day_num, "count": count})

    return {"calendar": calendar, "month": today.strftime("%B %Y")}

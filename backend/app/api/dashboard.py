"""
Dashboard API — pulls real KPI data from database.
"""

from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, Attendance, AttendanceCorrection
from app.models.training import TrainingEnrollment

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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

    # Pending leave requests
    pending_leave = db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count()

    # Today's attendance rate
    today_present = db.query(Attendance).filter(
        Attendance.date == today,
        Attendance.status.in_(["present", "wfh", "late"])
    ).count()
    rate = round((today_present / active * 100)) if active > 0 else 0
    attendance_rate = f"{rate}%" if rate == int(rate) else f"{rate}%"

    # Upcoming birthdays (next 7 days)
    upcoming_bdays = 0
    employees = base.filter(Employee.date_of_birth.isnot(None), Employee.employment_status == "active").all()
    for emp in employees:
        bday_this_year = emp.date_of_birth.replace(year=today.year)
        days_until = (bday_this_year - today).days
        if 0 <= days_until <= 7:
            upcoming_bdays += 1

    # Work anniversaries this month
    anniversaries = 0
    for emp in base.filter(Employee.employment_status == "active").all():
        if emp.joining_date and emp.joining_date.month == today.month and emp.joining_date.year < today.year:
            anniversaries += 1

    return {
        "kpis": [
            {"label": "Total Employees", "value": str(total), "icon": "Users", "color": "#66785F"},
            {"label": "Active Employees", "value": str(active), "icon": "UserCheck", "color": "#7BAE7F"},
            {"label": "Inactive", "value": str(inactive), "icon": "UserX", "color": "#9CA3AF"},
            {"label": "Pending Leave", "value": str(pending_leave), "icon": "Calendar", "color": "#D6A85F"},
            {"label": "Today's Attendance", "value": f"{attendance_rate}%", "icon": "CheckCircle", "color": "#7E9BB7"},
            {"label": "Upcoming Birthdays", "value": str(upcoming_bdays), "trend": "this week", "icon": "Cake", "color": "#D97C7C"},
            {"label": "Work Anniversaries", "value": str(anniversaries), "trend": "this month", "icon": "Award", "color": "#A3B18A"},
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

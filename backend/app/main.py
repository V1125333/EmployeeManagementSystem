"""
Reknew Orbit — Backend API
Creates all 19 database tables on startup and seeds initial data.
"""

import logging
from datetime import date
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import (
    create_tables,
    ensure_audit_log_table,
    ensure_employee_audit_columns,
    ensure_employee_sensitive_columns,
    ensure_announcement_columns,
    ensure_notification_columns,
    ensure_timesheet_columns,
    ensure_time_off_columns,
    ensure_leave_type_policy_columns,
    ensure_allocation_columns,
    SessionLocal,
)

# Import all models so SQLAlchemy registers them
from app.models import (
    Employee, EmployeeAuditLog, EmployeePerformanceSnapshot, Department, Designation,
    LeaveType, LeaveBalance, LeaveRequest, Attendance, AttendanceCorrection,
    OnboardingTask, Training, TrainingEnrollment,
    Channel, ChannelMember, Message, MessageReaction,
    Project, Allocation, Announcement, AnnouncementAudience, AnnouncementAcknowledgment,
    AnnouncementRead, Notification, ActionInboxItem, ActivityLog,
    UserSettings, SupportTicket,
    Client, ClientOnboarding, ClientChecklistItem, ClientTask, ClientTeamMember,
    ClientDocument, ClientMilestone, ClientActivityLog,
    Certificate, CertificateAuditLog,
    SensitiveAccessAuditLog,
    AuditLog,
)
from app.services.auth_service import hash_password
from app.api.dashboard import router as dashboard_router
from app.api.employees import router as employees_router
from app.api.auth import router as auth_router
from app.api.announcements import router as announcements_router
from app.api.inbox_notifications import router as inbox_notifications_router
from app.api.certificates import router as certificates_router
from app.api.hr_documents import router as hr_documents_router
from app.api.settings import router as settings_router
from app.api.support_tickets import router as support_tickets_router
from app.api.attendance import router as attendance_router
from app.api.timesheets import router as timesheets_router
from app.api.leaves import router as leaves_router
from app.api.admin_time_off import router as admin_time_off_router
from app.api.client_onboarding import router as client_onboarding_router
from app.api.audit_logs import router as audit_logs_router
from app.api.allocations import router as allocations_router
from app.api.forecasting import router as forecasting_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def seed_departments(db):
    """Seed default departments if table is empty."""
    if db.query(Department).count() > 0:
        return
    departments = [
        ("Engineering", "ENG", 1),
        ("Product", "PRD", 2),
        ("Design", "DES", 3),
        ("Marketing", "MKT", 4),
        ("Sales", "SLS", 5),
        ("Operations", "OPS", 6),
        ("People", "PPL", 7),
        ("Finance", "FIN", 8),
    ]
    for name, code, order in departments:
        db.add(Department(name=name, code=code, sort_order=order))
    db.commit()
    logger.info(f"Seeded {len(departments)} departments")


def seed_designations(db):
    """Seed default designations if table is empty."""
    if db.query(Designation).count() > 0:
        return
    designations = [
        ("Intern", 1),
        ("Junior Engineer", 1),
        ("Engineer", 2),
        ("Senior Engineer", 3),
        ("Lead Engineer", 4),
        ("Engineering Manager", 5),
        ("Product Manager", 3),
        ("Senior Product Manager", 4),
        ("Designer", 2),
        ("Senior Designer", 3),
        ("Director", 5),
        ("VP", 6),
        ("C-Level Executive", 7),
    ]
    for name, level in designations:
        db.add(Designation(name=name, level=level))
    db.commit()
    logger.info(f"Seeded {len(designations)} designations")


def seed_leave_types(db):
    """Seed default leave types if table is empty."""
    if db.query(LeaveType).count() > 0:
        return
    leave_types = [
        ("Casual Leave", "CL", 12, True, True, 5, 1, True, None, None),
        ("Sick Leave", "SL", 10, True, False, 0, 2, False, 30, None),
        ("Earned Leave", "EL", 15, True, True, 10, 3, True, None, None),
        ("Maternity Leave", "ML", 180, True, False, 0, 4, True, None, None),
        ("Paternity Leave", "PL", 15, True, False, 0, 5, True, None, None),
        ("Compensatory Off", "CO", 0, True, False, 0, 6, True, None, None),
        ("Loss of Pay", "LOP", 0, False, False, 0, 7, True, None, None),
        ("Bereavement Leave", "BL", 5, True, False, 0, 8, True, 30, "Future bereavement leave is unusual. Please confirm the dates before submitting."),
    ]
    for name, code, days, paid, carry, max_carry, order, allow_future, past_limit, future_warning in leave_types:
        db.add(LeaveType(
            name=name, code=code, default_days_per_year=days,
            is_paid=paid, is_carry_forward=carry,
            max_carry_forward_days=max_carry, sort_order=order,
            allow_future_dates=allow_future,
            past_date_limit_days=past_limit,
            future_date_warning=future_warning,
        ))
    db.commit()
    logger.info(f"Seeded {len(leave_types)} leave types")


def seed_default_channels(db):
    """Seed default chat channels if table is empty."""
    if db.query(Channel).count() > 0:
        return
    channels = [
        ("general", "public", "Company-wide general discussion"),
        ("announcements", "public", "Official announcements from HR and leadership"),
        ("engineering", "public", "Engineering team discussions"),
        ("product", "public", "Product team discussions"),
        ("design", "public", "Design team discussions"),
        ("random", "public", "Casual conversations and fun stuff"),
    ]
    for name, ch_type, desc in channels:
        db.add(Channel(name=name, type=ch_type, description=desc))
    db.commit()
    logger.info(f"Seeded {len(channels)} chat channels")


def seed_admin(db):
    """Create the super admin account if it doesn't exist."""
    admin = db.query(Employee).filter(Employee.work_email == "superadmin@reknew.ai").first()
    if admin:
        return

    admin = Employee(
        first_name="Super",
        last_name="Admin",
        work_email="superadmin@reknew.ai",
        phone="0000000000",
        workforce_type="Full-Time Employee",
        role="super_admin",
        department="People",
        designation="Administrator",
        reporting_manager="Self",
        employment_status="active",
        work_location="Onshore",
        joining_date=date(2024, 1, 1),
        password_hash=hash_password("test"),
        totp_secret=None,
        is_first_login=False,
        is_active=True,
        setup_code=None,
    )
    db.add(admin)
    db.commit()
    logger.info("Super admin account seeded: superadmin@reknew.ai / test")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create all tables and seed data."""
    create_tables()
    ensure_audit_log_table()
    ensure_employee_audit_columns()
    ensure_employee_sensitive_columns()
    ensure_announcement_columns()
    ensure_notification_columns()
    ensure_timesheet_columns()
    ensure_time_off_columns()
    ensure_leave_type_policy_columns()
    ensure_allocation_columns()
    logger.info("All database tables created")

    db = SessionLocal()
    try:
        seed_departments(db)
        seed_designations(db)
        seed_leave_types(db)
        seed_default_channels(db)
        seed_admin(db)
        logger.info("Database seeding complete")
    finally:
        db.close()

    yield


app = FastAPI(
    title="Reknew Orbit API",
    description="Employee Management System — 19 tables, TOTP auth",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employees_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(announcements_router, prefix="/api/v1")
app.include_router(inbox_notifications_router, prefix="/api/v1")
app.include_router(certificates_router, prefix="/api/v1")
app.include_router(hr_documents_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(support_tickets_router, prefix="/api/v1")
app.include_router(attendance_router, prefix="/api/v1")
app.include_router(timesheets_router, prefix="/api/v1")
app.include_router(leaves_router, prefix="/api/v1")
app.include_router(admin_time_off_router, prefix="/api/v1")
app.include_router(client_onboarding_router, prefix="/api/v1")
app.include_router(audit_logs_router, prefix="/api/v1")
app.include_router(allocations_router, prefix="/api/v1")
app.include_router(forecasting_router, prefix="/api/v1")



@app.get("/")
async def root():
    return {"app": "Reknew Orbit API", "version": "3.0.0", "tables": 19}


@app.get("/health")
async def health():
    return {"status": "healthy", "auth": "TOTP", "tables": 19}

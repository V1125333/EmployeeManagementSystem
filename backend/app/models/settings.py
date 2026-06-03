"""
User settings and support ticket models.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint("theme IN ('light', 'dark', 'system')", name="ck_user_settings_theme"),
        CheckConstraint("sidebar_mode IN ('expanded', 'collapsed')", name="ck_user_settings_sidebar_mode"),
        CheckConstraint("dashboard_density IN ('comfortable', 'compact')", name="ck_user_settings_dashboard_density"),
        CheckConstraint("date_format IN ('MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD')", name="ck_user_settings_date_format"),
        CheckConstraint(
            "profile_visibility IN ('Everyone', 'Managers Only', 'HR Only', 'Private')",
            name="ck_user_settings_profile_visibility",
        ),
        CheckConstraint(
            "phone_visibility IN ('Everyone', 'Managers Only', 'HR Only', 'Private')",
            name="ck_user_settings_phone_visibility",
        ),
        CheckConstraint(
            "birthday_visibility IN ('Everyone', 'Managers Only', 'HR Only', 'Private')",
            name="ck_user_settings_birthday_visibility",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False)

    time_zone: Mapped[str] = mapped_column(String(100), nullable=False, default="America/New_York")
    date_format: Mapped[str] = mapped_column(String(20), nullable=False, default="MM/DD/YYYY")
    default_landing_page: Mapped[str] = mapped_column(String(100), nullable=False, default="Dashboard")

    theme: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    sidebar_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="expanded")
    dashboard_density: Mapped[str] = mapped_column(String(20), nullable=False, default="comfortable")

    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    notification_company_announcements: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notification_leave_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notification_attendance_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notification_task_assignments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notification_training_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notification_project_allocation_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    profile_visibility: Mapped[str] = mapped_column(String(30), nullable=False, default="Everyone")
    phone_visibility: Mapped[str] = mapped_column(String(30), nullable=False, default="Managers Only")
    birthday_visibility: Mapped[str] = mapped_column(String(30), nullable=False, default="Everyone")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint("status IN ('Open', 'In Progress', 'Resolved', 'Closed')", name="ck_support_tickets_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)

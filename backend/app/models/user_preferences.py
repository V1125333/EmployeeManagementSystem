"""
Per-user preference storage for theme, layout, and notifications.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False)

    theme_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="light")
    accent_color: Mapped[str] = mapped_column(String(30), nullable=False, default="olive")
    sidebar_collapsed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    compact_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    timezone: Mapped[str] = mapped_column(String(60), nullable=False, default="Asia/Kolkata")
    date_format: Mapped[str] = mapped_column(String(20), nullable=False, default="DD/MM/YYYY")
    default_landing_page: Mapped[str] = mapped_column(String(50), nullable=False, default="Dashboard")
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="en-US")

    email_notif_leave_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_notif_leave_rejected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_notif_timesheet_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_notif_timesheet_rejected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_notif_allocation_changes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    inapp_notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

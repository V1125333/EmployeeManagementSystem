"""
Table 1: employees — Central employee records.
The most important table. Nearly every other table references this.
"""

import uuid
from datetime import datetime, date
from sqlalchemy import String, Boolean, Date, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ─── Basic Info ───
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    work_email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    personal_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_code: Mapped[str] = mapped_column(String(10), default="+91")
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)  # male, female, non_binary, prefer_not_to_say
    profile_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Organization ───
    department_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("departments.id"), nullable=True)
    designation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("designations.id"), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)

    # ─── Workforce Info ───
    workforce_type: Mapped[str] = mapped_column(String(50), nullable=False)  # full_time, part_time, contract, intern, trainee
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # super_admin, hr_admin, manager, employee, trainee
    employment_status: Mapped[str] = mapped_column(String(30), default="active")  # active, inactive, onboarding, offboarding
    inactive_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str] = mapped_column(String(200), default="Onshore")
    date_of_joining: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_of_exit: Mapped[date | None] = mapped_column(Date, nullable=True)
    onboarding_type: Mapped[str] = mapped_column(String(50), default="Standard Employee")

    # ─── Authentication ───
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_first_login: Mapped[bool] = mapped_column(Boolean, default=True)
    setup_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ─── Emergency Contact ───
    emergency_contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_contact_relation: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ─── Address ───
    current_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    permanent_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Notes ───
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Timestamps ───
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ─── Legacy fields (kept for backward compatibility with existing services) ───
    department: Mapped[str] = mapped_column(String(100), default="")  # will migrate to department_id
    designation: Mapped[str | None] = mapped_column(String(100), nullable=True)  # will migrate to designation_id
    reporting_manager: Mapped[str] = mapped_column(String(100), default="")  # will migrate to manager_id
    joining_date: Mapped[date] = mapped_column(Date, nullable=False)
    work_location: Mapped[str] = mapped_column(String(50), default="Onshore")

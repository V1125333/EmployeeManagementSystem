"""
Table 4: leave_types — Leave category definitions (Casual, Sick, Earned, etc.)
Table 5: leave_balances — Per employee per year balance tracking
Table 6: leave_requests — Leave applications and approval workflow
Table 7: attendance — Daily attendance records per employee
Table 8: attendance_corrections — Requests to fix attendance records
"""

import uuid
from datetime import datetime, date
from sqlalchemy import String, Boolean, Date, DateTime, Text, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class LeaveType(Base):
    __tablename__ = "leave_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_days_per_year: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True)
    is_carry_forward: Mapped[bool] = mapped_column(Boolean, default=False)
    max_carry_forward_days: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    leave_type_id: Mapped[str] = mapped_column(String(36), ForeignKey("leave_types.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_days: Mapped[float] = mapped_column(Numeric(5, 1), default=0)
    used_days: Mapped[float] = mapped_column(Numeric(5, 1), default=0)
    carry_forward_days: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    leave_type_id: Mapped[str] = mapped_column(String(36), ForeignKey("leave_types.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_days: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    is_half_day: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, approved, rejected, cancelled
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    check_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_hours: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="present")  # present, absent, half_day, late, on_leave, wfh, holiday
    source: Mapped[str] = mapped_column(String(20), default="system")  # manual, biometric, system, mobile_app
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AttendanceCorrection(Base):
    __tablename__ = "attendance_corrections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    attendance_id: Mapped[str] = mapped_column(String(36), ForeignKey("attendance.id"), nullable=False)
    original_check_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    original_check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_check_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, approved, rejected
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

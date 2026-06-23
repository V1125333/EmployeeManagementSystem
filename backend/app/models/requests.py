"""Employee request workflow models."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmployeeRequest(Base):
    __tablename__ = "employee_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    ticket_number: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True, index=True)
    request_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    current_owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True, index=True)
    submitted_to_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    pending_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    wfh_from_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    wfh_to_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    wfh_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    wfh_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    sp_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sp_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    sp_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    sp_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sp_duration_minutes: Mapped[int | None] = mapped_column(nullable=True)

    ot_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ot_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    ot_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    ot_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ot_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ot_duration_minutes: Mapped[int | None] = mapped_column(nullable=True)

    exp_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exp_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    exp_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    exp_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    exp_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    exp_paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exp_paid_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)

    reviewed_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RequestTicketCounter(Base):
    __tablename__ = "request_ticket_counters"

    prefix: Mapped[str] = mapped_column(String(10), primary_key=True)
    year: Mapped[int] = mapped_column(primary_key=True)
    last_value: Mapped[int] = mapped_column(default=0)


class RequestStatusHistory(Base):
    __tablename__ = "request_status_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_requests.id"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RequestComment(Base):
    __tablename__ = "request_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_requests.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RequestAttachment(Base):
    __tablename__ = "request_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_requests.id"), nullable=False, index=True)
    uploaded_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False, index=True)

    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    storage_provider: Mapped[str] = mapped_column(String(30), nullable=False, default="local")
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, default="OTHER", index=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

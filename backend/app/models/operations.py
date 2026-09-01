"""
Table 16: projects — Project registry for team allocation
Table 17: allocations — Employee-to-project mapping
Table 18: announcements — Company-wide posts
Table 19: notifications — User notification inbox
Bonus: activity_log — System-wide audit trail
"""

import uuid
from datetime import datetime, date, time, timezone
from sqlalchemy import (
    String, Boolean, CheckConstraint, Date, DateTime, Time, Text, Numeric,
    ForeignKey, Index, Integer, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.domain.timesheet import TimesheetIdempotencyStatus, TimesheetWeekState
from app.models.allocation import Allocation


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clients.id"), nullable=True, index=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planning")  # planning, active, on_hold, completed, cancelled
    project_manager_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectDocument(Base):
    __tablename__ = "project_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    uploaded_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_provider: Mapped[str] = mapped_column(String(30), nullable=False, default="local")
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, default="OTHER")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompanyHoliday(Base):
    __tablename__ = "company_holidays"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    holiday_type: Mapped[str] = mapped_column(String(30), default="public")
    regions: Mapped[str] = mapped_column(Text, default="all")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimesheetWeek(Base):
    """Additive aggregate boundary; legacy routes do not use this model yet."""

    __tablename__ = "timesheet_weeks"
    __table_args__ = (
        UniqueConstraint("employee_id", "week_start", name="uq_timesheet_weeks_employee_week"),
        CheckConstraint(
            "state IN ('draft', 'submitted', 'approved', 'rejected', 'mixed_legacy')",
            name="ck_timesheet_weeks_state",
        ),
        CheckConstraint("version >= 1", name="ck_timesheet_weeks_version_positive"),
        CheckConstraint(
            "review_decision IS NULL OR review_decision IN ('approve', 'reject')",
            name="ck_timesheet_weeks_review_decision",
        ),
        Index("ix_timesheet_weeks_employee_week", "employee_id", "week_start"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default=TimesheetWeekState.DRAFT.value)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC", server_default="UTC")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    review_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    entries: Mapped[list["TimesheetEntry"]] = relationship(back_populates="timesheet_week")


class TimesheetIdempotencyRecord(Base):
    """Future write replay record. It stores hashes/references, never request bodies."""

    __tablename__ = "timesheet_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "actor_employee_id", "operation", "idempotency_key",
            name="uq_timesheet_idempotency_actor_operation_key",
        ),
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'failed', 'abandoned')",
            name="ck_timesheet_idempotency_status",
        ),
        Index("ix_timesheet_idempotency_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_timesheet_idempotency_expires_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False, default="timesheet_week")
    aggregate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TimesheetIdempotencyStatus.IN_PROGRESS.value,
    )
    result_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TimesheetMigrationAnomaly(Base):
    """Bounded, content-free record of legacy state anomalies found by backfill."""

    __tablename__ = "timesheet_migration_anomalies"
    __table_args__ = (
        UniqueConstraint("timesheet_week_id", "anomaly_type", name="uq_timesheet_anomaly_week_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timesheet_week_id: Mapped[str] = mapped_column(String(36), ForeignKey("timesheet_weeks.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class TimesheetEntry(Base):
    __tablename__ = "timesheet_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    timesheet_week_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("timesheet_weeks.id"), nullable=True, index=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    entry_code: Mapped[str] = mapped_column(String(10), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    hours: Mapped[float] = mapped_column(Numeric(4, 2), default=0)
    overtime_hours: Mapped[float] = mapped_column(Numeric(4, 2), default=0)
    overtime_requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    overtime_status: Mapped[str] = mapped_column(String(20), default="none")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_zone: Mapped[str] = mapped_column(String(80), default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    timesheet_week: Mapped[TimesheetWeek | None] = relationship(back_populates="entries")


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="general")  # general, hr, policy, event, urgent
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    announcement_type: Mapped[str] = mapped_column(String(30), default="general")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    audience_type: Mapped[str] = mapped_column(String(30), default="everyone")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    requires_acknowledgment: Mapped[bool] = mapped_column(Boolean, default=False)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    publish_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AnnouncementAudience(Base):
    __tablename__ = "announcement_audiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    announcement_id: Mapped[str] = mapped_column(String(36), ForeignKey("announcements.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_value: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnnouncementAcknowledgment(Base):
    __tablename__ = "announcement_acknowledgments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    announcement_id: Mapped[str] = mapped_column(String(36), ForeignKey("announcements.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    announcement_id: Mapped[str] = mapped_column(String(36), ForeignKey("announcements.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    actor_employee_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(30), default="system")  # leave, attendance, training, announcement, chat, system
    notification_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    origin_domain: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deduplication_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "deduplication_key", name="uq_notifications_recipient_deduplication"),
        Index("ix_notifications_origin_event", "origin_domain", "event_type"),
    )


class ActionInboxItem(Base):
    __tablename__ = "action_inbox_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assigned_to_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # employee_added, leave_approved, etc.
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # employee, leave_request, policy, etc.
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string for extra data
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

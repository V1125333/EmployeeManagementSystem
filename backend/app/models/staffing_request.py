"""
Staffing requests and candidate snapshots.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StaffingRequest(Base):
    __tablename__ = "staffing_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    hiring_manager_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role_needed: Mapped[str] = mapped_column(String(100), nullable=False)
    designation_needed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    skills_required: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    allocation_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    headcount_needed: Mapped[int] = mapped_column(Integer, nullable=False)
    headcount_fulfilled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    fulfilled_allocation_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fulfilled_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StaffingRequestCandidate(Base):
    __tablename__ = "staffing_request_candidates"
    __table_args__ = (
        UniqueConstraint("staffing_request_id", "employee_id", name="uq_staffing_request_candidate"),
        UniqueConstraint("staffing_request_id", "allocation_id", name="uq_staffing_candidate_request_allocation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    staffing_request_id: Mapped[str] = mapped_column(String(36), ForeignKey("staffing_requests.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    allocation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("allocations.id"), nullable=True)
    match_status: Mapped[str] = mapped_column(String(20), nullable=False, default="suggested")
    available_capacity_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    current_allocation_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    next_available_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    suggested_by: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

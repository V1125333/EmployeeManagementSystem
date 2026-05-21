"""
Table 9: onboarding_tasks — Checklist tasks for new employees
Table 10: trainings — Training program definitions
Table 11: training_enrollments — Employee training assignments and progress
"""

import uuid
from datetime import datetime, date
from sqlalchemy import String, Boolean, Date, DateTime, Text, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, in_progress, completed
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Training(Base):
    __tablename__ = "trainings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(30), default="optional")  # mandatory, optional, skill_based, compliance
    department_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("departments.id"), nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_hours: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    material_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrainingEnrollment(Base):
    __tablename__ = "training_enrollments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    training_id: Mapped[str] = mapped_column(String(36), ForeignKey("trainings.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, in_progress, completed, failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    certificate_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

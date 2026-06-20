"""
Client onboarding tables for admin-side client implementation tracking.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contract_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="prospect")
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClientOnboarding(Base):
    __tablename__ = "client_onboarding"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(80), default="Contract Signed")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    target_go_live_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_go_live_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClientChecklistItem(Base):
    __tablename__ = "client_checklist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClientTask(Base):
    __tablename__ = "client_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(40), default="not_started")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClientTeamMember(Base):
    __tablename__ = "client_team_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(60), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClientDocument(Base):
    __tablename__ = "client_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClientMilestone(Base):
    __tablename__ = "client_milestones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False)
    milestone_name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="not_started")
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClientActivityLog(Base):
    __tablename__ = "client_activity_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

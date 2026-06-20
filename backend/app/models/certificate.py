"""
Certificate verification records.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    certificate_code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    learner_name: Mapped[str] = mapped_column(String(180), nullable=False)
    course_name: Mapped[str] = mapped_column(String(180), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="valid")
    verification_url: Mapped[str] = mapped_column(String(500), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    issued_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CertificateAuditLog(Base):
    __tablename__ = "certificate_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    certificate_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

"""
Security and sensitive-data audit models.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SensitiveAccessAuditLog(Base):
    __tablename__ = "sensitive_access_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employees.id"), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sensitivity_level: Mapped[str] = mapped_column(String(30), default="restricted")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

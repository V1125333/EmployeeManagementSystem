"""
Read-only centralized audit trail API.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import cast, or_, String
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditLog
from app.services.audit_service import log_authorization_failure
from app.services.settings_service import get_current_employee, normalize_role

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def can_view_audit(role: str | None) -> bool:
    return normalize_role(role) in {"super_admin", "hr_admin", "global_access"}


def serialize_audit(row: AuditLog) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "actor_user_id": row.actor_user_id,
        "actor_name": row.actor_name,
        "actor_role": row.actor_role,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "old_values": row.old_values,
        "new_values": row.new_values,
        "changed_fields": row.changed_fields,
        "reason": row.reason,
        "metadata_json": row.metadata_json,
        "source": row.source,
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
    }


@router.get("")
async def list_audit_logs(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    actor: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    source: str | None = Query(default=None),
    sensitive_only: bool = Query(default=False),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    requester = get_current_employee(db, x_user_id, x_user_email)
    if not can_view_audit(requester.role):
        log_authorization_failure(
            db,
            requester,
            action="audit_logs.view",
            entity_type="audit_log",
            reason="Global audit trail is restricted to Super Admin and HR Admin.",
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Only Super Admin and HR Admin can view audit logs.")

    query = db.query(AuditLog)
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLog.created_at <= date_to)
    if actor:
        actor_term = f"%{actor.strip()}%"
        query = query.filter(or_(AuditLog.actor_name.ilike(actor_term), AuditLog.actor_user_id.ilike(actor_term)))
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id.ilike(f"%{entity_id.strip()}%"))
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
    if source:
        query = query.filter(AuditLog.source == source)
    if sensitive_only:
        query = query.filter(cast(AuditLog.metadata_json, String).ilike("%sensitive%"))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            AuditLog.actor_name.ilike(term),
            AuditLog.action.ilike(term),
            AuditLog.entity_type.ilike(term),
            AuditLog.entity_id.ilike(term),
            AuditLog.reason.ilike(term),
            cast(AuditLog.changed_fields, String).ilike(term),
        ))

    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [serialize_audit(row) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }

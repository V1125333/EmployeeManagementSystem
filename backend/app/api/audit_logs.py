"""
Read-only centralized audit trail API.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import cast, or_, String
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditLog
from app.services.audit_service import log_audit, log_authorization_failure
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


def filtered_audit_query(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    actor: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    source: str | None = None,
    sensitive_only: bool = False,
    search: str | None = None,
):
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
    return query


def ensure_audit_viewer(db: Session, x_user_id: str | None, x_user_email: str | None):
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
    return requester


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
    ensure_audit_viewer(db, x_user_id, x_user_email)
    query = filtered_audit_query(
        db,
        date_from=date_from,
        date_to=date_to,
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        source=source,
        sensitive_only=sensitive_only,
        search=search,
    )

    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [serialize_audit(row) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/export")
async def export_audit_logs(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    actor: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    source: str | None = Query(default=None),
    sensitive_only: bool = Query(default=False),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    requester = get_current_employee(db, x_user_id, x_user_email)
    if normalize_role(requester.role) != "super_admin":
        log_authorization_failure(
            db,
            requester,
            action="audit_logs.export",
            entity_type="audit_log",
            reason="Audit export is restricted to Super Admin.",
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Only Super Admin can export audit logs.")

    filters = {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "actor": actor,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "source": source,
        "sensitive_only": sensitive_only,
        "search": search,
    }
    query = filtered_audit_query(
        db,
        date_from=date_from,
        date_to=date_to,
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        source=source,
        sensitive_only=sensitive_only,
        search=search,
    )
    rows = query.order_by(AuditLog.created_at.desc()).limit(10000).all()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date/Time", "Actor", "Role", "Action", "Entity Type", "Entity ID", "Changed Fields", "Reason", "Source", "IP Address"])
    for row in rows:
        writer.writerow([
            row.created_at.isoformat() if row.created_at else "",
            row.actor_name or "System",
            row.actor_role or "",
            row.action,
            row.entity_type,
            row.entity_id or "",
            ", ".join((row.changed_fields or {}).keys()),
            row.reason or "",
            row.source,
            row.ip_address or "",
        ])
    log_audit(
        db,
        requester,
        "audit_logs_exported",
        "audit_log",
        metadata={"exported_by": requester.work_email, "filters_applied": filters, "row_count": len(rows)},
        source="admin",
    )
    db.commit()
    buffer.seek(0)
    filename = f'audit-export-{date.today().strftime("%Y%m%d")}.csv'
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/entity/{entity_type}/{entity_id}")
async def list_entity_audit_logs(
    entity_type: str,
    entity_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    ensure_audit_viewer(db, x_user_id, x_user_email)
    query = db.query(AuditLog).filter(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [serialize_audit(row) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/{log_id}")
async def get_audit_log(
    log_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    ensure_audit_viewer(db, x_user_id, x_user_email)
    row = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Audit log not found.")
    return serialize_audit(row)

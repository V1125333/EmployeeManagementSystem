"""Authenticated, read-only boundary for the legacy Orbit briefing surface."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.authentication import AuthenticatedActor, get_authenticated_actor
from app.core.database import get_db
from app.services.audit_service import log_audit
from app.services.orbit_briefing_service import get_action_items, get_upcoming

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/me", tags=["Orbit AI"])

_DISABLED_MESSAGE = "This Orbit action is temporarily disabled. Please use the relevant application page."


def _correlation_id(request: Request) -> str:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    return str(correlation_id)[:120]


def _legacy_category(item_id: str | None) -> str:
    if item_id and item_id.startswith("timesheet:"):
        return "timesheet"
    if item_id and item_id.startswith("leave:"):
        return "leave"
    return "unknown"


def _audit_disabled_attempt(
    db: Session,
    request: Request,
    actor: AuthenticatedActor,
    *,
    operation: str,
    category: str,
) -> str:
    correlation_id = _correlation_id(request)
    try:
        log_audit(
            db,
            actor.employee,
            action=f"orbit.legacy_{operation}.disabled",
            entity_type="orbit_legacy_action",
            reason="Legacy Orbit mutation boundary is disabled.",
            metadata={
                "correlation_id": correlation_id,
                "operation": operation,
                "category": category,
                "outcome": "blocked",
            },
            source="security",
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist disabled Orbit action audit.")
    return correlation_id


def _disabled_response(code: str, correlation_id: str) -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": code,
            "message": _DISABLED_MESSAGE,
            "correlation_id": correlation_id,
        },
    )


@router.get("/action-items")
async def action_items(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    return get_action_items(db, actor.employee)


@router.get("/upcoming")
async def upcoming(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    return get_upcoming(db, actor.employee)


@router.post("/action-items/{item_id}/execute")
async def execute_action_disabled(
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    correlation_id = _audit_disabled_attempt(
        db,
        request,
        actor,
        operation="execute",
        category=_legacy_category(item_id),
    )
    _disabled_response("ORBIT_ACTION_TEMPORARILY_DISABLED", correlation_id)


@router.post("/undo")
async def undo_disabled(
    request: Request,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    correlation_id = _audit_disabled_attempt(
        db, request, actor, operation="undo", category="unknown"
    )
    _disabled_response("ORBIT_UNDO_TEMPORARILY_DISABLED", correlation_id)


@router.post("/action-items/{item_id}/undo")
async def historical_undo_disabled(
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    # Retain the historical URL as a fail-closed compatibility boundary. The
    # item identifier and request body are deliberately neither parsed nor logged.
    correlation_id = _audit_disabled_attempt(
        db, request, actor, operation="undo", category=_legacy_category(item_id)
    )
    _disabled_response("ORBIT_UNDO_TEMPORARILY_DISABLED", correlation_id)

"""Development-only authenticated browser preview for the isolated AI Platform."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai_platform.execution import ExecutionPrincipal
from app.ai_platform.preview import (
    PlatformPreviewRequest, PlatformPreviewResponse, run_platform_preview,
)
from app.core.authentication import AuthenticatedActor, get_authenticated_actor
from app.core.config import settings
from app.core.database import get_db
from app.services.leave_eligibility_service import resolve_employee_timezone

router = APIRouter(prefix="/ai", tags=["AI Platform Preview"])


def require_platform_preview_enabled() -> None:
    environment = settings.APP_ENV.strip().lower()
    if not settings.AI_PLATFORM_PREVIEW_ENABLED or environment not in {"development", "dev", "test"}:
        raise HTTPException(status_code=404, detail="Not found.")


@router.post(
    "/platform-preview",
    response_model=PlatformPreviewResponse,
    include_in_schema=False,
)
def platform_preview(
    payload: PlatformPreviewRequest,
    _preview_enabled: None = Depends(require_platform_preview_enabled),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
    db: Session = Depends(get_db),
) -> PlatformPreviewResponse:
    principal = ExecutionPrincipal.from_authenticated(actor.principal)
    timezone_name = resolve_employee_timezone(db, actor.employee)
    try:
        return run_platform_preview(
            message=payload.message,
            principal=principal,
            db=db,
            timezone_name=timezone_name,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "PREVIEW_FAILED", "message": "The Platform preview could not complete safely."},
        ) from exc

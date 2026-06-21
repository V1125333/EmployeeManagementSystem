from io import StringIO
import csv

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.employee import Employee
from app.schemas.forecasting import ForecastResponse
from app.services.audit_service import log_audit, log_authorization_failure
from app.services.forecasting_service import SUPPORTED_FORECAST_WINDOWS, get_workforce_forecast
from app.services.settings_service import get_current_employee, normalize_role


router = APIRouter(prefix="/forecasting", tags=["Workforce Forecasting"])


def _allowed_scope(actor: Employee) -> str:
    role = normalize_role(actor.role)
    if role in {"super_admin", "hr_admin", "admin", "global_access"}:
        return "all"
    if role == "manager":
        return "direct_reports"
    return "none"


def _load_forecast(db: Session, actor: Employee, window_days: int) -> ForecastResponse:
    if window_days not in SUPPORTED_FORECAST_WINDOWS:
        raise HTTPException(status_code=400, detail="window_days must be 30, 60, or 90.")
    scope = _allowed_scope(actor)
    if scope == "none":
        log_authorization_failure(
            db,
            actor,
            action="forecast.view",
            entity_type="workforce_forecast",
            entity_id=str(window_days),
            reason="User attempted to view workforce forecasting without permission.",
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Not authorized to view workforce forecasting.")
    return get_workforce_forecast(
        db,
        window_days,
        manager_employee_id=actor.id if scope == "direct_reports" else None,
    )


@router.get("", response_model=ForecastResponse)
async def workforce_forecast(
    window_days: int = Query(30),
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    report = _load_forecast(db, actor, window_days)
    log_audit(
        db,
        actor,
        action="forecast_viewed",
        entity_type="workforce_forecast",
        entity_id=str(window_days),
        metadata={
            "role": actor.role,
            "scope": _allowed_scope(actor),
            "filters": {"window_days": window_days},
            "forecast_window_days": window_days,
        },
    )
    db.commit()
    return report


@router.get("/export")
async def export_workforce_forecast(
    window_days: int = Query(30),
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    report = _load_forecast(db, actor, window_days)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Employee",
        "Department",
        "Manager",
        "Current Allocation",
        "Forecast Allocation",
        "Availability Date",
        "Forecast Status",
    ])
    for row in report.employees:
        writer.writerow([
            row.employee_name,
            row.department or "",
            row.manager_name or "",
            row.current_allocation_percentage,
            row.forecast_allocation_percentage,
            row.next_allocation_end_date.isoformat() if row.next_allocation_end_date else "",
            row.forecast_status,
        ])

    log_audit(
        db,
        actor,
        action="forecast_exported",
        entity_type="workforce_forecast",
        entity_id=str(window_days),
        metadata={
            "role": actor.role,
            "scope": _allowed_scope(actor),
            "filters": {"window_days": window_days},
            "forecast_window_days": window_days,
            "row_count": len(report.employees),
        },
    )
    db.commit()

    output.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="workforce-forecast-{window_days}-days.csv"'}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)

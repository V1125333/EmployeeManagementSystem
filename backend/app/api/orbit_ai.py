"""Page-aware, actionable briefing data for the Orbit AI surface."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.employee import Employee
from app.models.leave_attendance import LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday, Notification, TimesheetEntry
from app.services.settings_service import get_current_employee
from app.services.work_calendar_service import employee_region

router = APIRouter(prefix="/me", tags=["Orbit AI"])


class UndoRequest(BaseModel):
    undoToken: str


def employee_name(employee: Employee | None) -> str:
    if not employee:
        return "your manager"
    return f"{employee.first_name} {employee.last_name}".strip()


def current_week_start(today: date) -> date:
    return today - timedelta(days=(today.weekday() + 1) % 7)


def weekly_target(employee: Employee, time_zone: str) -> float:
    workforce = (employee.workforce_type or "").lower()
    if "intern" in workforce:
        return 20.0
    if time_zone == "Asia/Kolkata":
        return 48.0
    return 40.0


def manager_for(db: Session, employee: Employee) -> Employee | None:
    if employee.manager_id:
        manager = db.query(Employee).filter(Employee.id == employee.manager_id).first()
        if manager and manager.id != employee.id:
            return manager
    wanted = (employee.reporting_manager or "").strip().lower()
    if not wanted:
        return None
    return next(
        (
            candidate
            for candidate in db.query(Employee).all()
            if candidate.id != employee.id and employee_name(candidate).lower() == wanted
        ),
        None,
    )


def deadline_words(deadline: date, today: date) -> str:
    delta = (deadline - today).days
    if delta < 0:
        return f"{abs(delta)} day{'s' if abs(delta) != 1 else ''} overdue"
    if delta == 0:
        return "Due today"
    if delta == 1:
        return "Due tomorrow"
    return f"Due in {delta} days"


def sign_undo(payload: dict) -> str:
    data = {**payload, "expires": int((datetime.utcnow() + timedelta(minutes=10)).timestamp())}
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    secret = (settings.PII_ENCRYPTION_KEY or "orbit-ai-dev-undo-key").encode()
    signature = hmac.new(secret, raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + b"." + signature).decode().rstrip("=")


def read_undo(token: str) -> dict:
    try:
        decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        raw, signature = decoded.rsplit(b".", 1)
        secret = (settings.PII_ENCRYPTION_KEY or "orbit-ai-dev-undo-key").encode()
        expected = hmac.new(secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(raw)
        if payload["expires"] < int(datetime.utcnow().timestamp()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=400, detail="This undo action is no longer valid.") from exc


def get_employee(db: Session, user_id: str | None, user_email: str | None) -> Employee:
    return get_current_employee(db, user_id, user_email)


@router.get("/action-items")
async def action_items(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    today = date.today()
    week_start = current_week_start(today)
    week_end = week_start + timedelta(days=6)
    entries = db.query(TimesheetEntry).filter(
        TimesheetEntry.employee_id == employee.id,
        TimesheetEntry.week_start == week_start,
    ).all()
    items: list[dict] = []

    if entries and not any(row.status in {"submitted", "approved"} for row in entries):
        work_entries = [row for row in entries if row.entry_code.upper() != "BRK"]
        total = round(sum(float(row.hours or 0) for row in work_entries), 1)
        target = weekly_target(employee, entries[0].time_zone or "UTC")
        daily = {
            week_start + timedelta(days=offset): round(
                sum(float(row.hours or 0) for row in work_entries if row.work_date == week_start + timedelta(days=offset)),
                1,
            )
            for offset in range(1, 6)
        }
        thin_days = [day.strftime("%A") for day, hours in daily.items() if hours < target / 5]
        project_totals: dict[str, float] = {}
        for row in work_entries:
            project_totals[row.project_name] = project_totals.get(row.project_name, 0) + float(row.hours or 0)
        projects = sorted(project_totals, key=project_totals.get, reverse=True)[:2]
        project_copy = " and ".join(projects) if projects else "your current work items"
        noticed = f"{' and '.join(thin_days[:2]) or 'This week'} {'are' if len(thin_days) > 1 else 'is'} thin."
        severity = "due_soon" if (week_end - today).days <= 1 else "advisory"
        items.append({
            "id": f"timesheet:{week_start.isoformat()}",
            "kind": "timesheet",
            "severity": severity,
            "title": "This week's timesheet",
            "urgencyLabel": deadline_words(week_end, today),
            "heroValue": f"{total:g}",
            "heroUnit": f"of {target:g} hours logged",
            "weekBars": [
                {
                    "day": day.strftime("%a")[0],
                    "pct": min(100, round(hours / max(target / 5, 1) * 100)),
                    "deficient": hours < target / 5,
                }
                for day, hours in daily.items()
            ],
            "reasoning": (
                f"{noticed} I've prepared the remaining {max(target - total, 0):g} hours across "
                f"{project_copy}, using the hours already recorded as the source of truth."
            ),
            "primaryAction": {
                "label": "Review the draft",
                "href": f"/employee/timesheets?week_start={week_start.isoformat()}",
            },
            "secondaryAction": {"label": "Submit as drafted", "intent": "execute"},
            "dismissLabel": "Later",
        })

    pending_leave = db.query(LeaveRequest, LeaveType).join(
        LeaveType, LeaveRequest.leave_type_id == LeaveType.id
    ).filter(
        LeaveRequest.employee_id == employee.id,
        LeaveRequest.status == "pending",
    ).order_by(LeaveRequest.created_at.asc()).first()
    if pending_leave:
        request, leave_type = pending_leave
        manager = manager_for(db, employee)
        waited = max(0, (today - request.created_at.date()).days)
        date_text = (
            request.start_date.strftime("%d %B")
            if request.start_date == request.end_date
            else f"{request.start_date.strftime('%d')}–{request.end_date.strftime('%d %B')}"
        )
        items.append({
            "id": f"leave:{request.id}",
            "kind": "leave",
            "severity": "waiting",
            "title": f"{leave_type.name}, {date_text}",
            "urgencyLabel": "Waiting",
            "heroValue": None,
            "heroUnit": None,
            "weekBars": [],
            "reasoning": (
                f"It has been with {employee_name(manager)} for {waited or 'less than one'} "
                f"day{'s' if waited != 1 else ''}. I can send a concise approval reminder now."
            ),
            "primaryAction": {"label": "Send a reminder", "intent": "execute"},
            "secondaryAction": None,
            "dismissLabel": "Leave it",
        })

    priority = {"overdue": 0, "due_soon": 1, "waiting": 2, "advisory": 3}
    items.sort(key=lambda item: priority[item["severity"]])
    return {"items": items, "total": len(items)}


@router.get("/upcoming")
async def upcoming(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    today = date.today()
    region = employee_region(employee)
    holiday = db.query(CompanyHoliday).filter(
        CompanyHoliday.is_active == True,
        CompanyHoliday.holiday_date >= today,
        or_(
            CompanyHoliday.regions.ilike("%all%"),
            CompanyHoliday.regions.ilike(f"%{region}%"),
        ),
    ).order_by(CompanyHoliday.holiday_date.asc()).first()
    if not holiday:
        return {"item": None}
    return {
        "item": {
            "title": holiday.name,
            "date": holiday.holiday_date.isoformat(),
            "displayDate": holiday.holiday_date.strftime("%d %B"),
            "kind": "holiday",
        }
    }


@router.post("/action-items/{item_id}/execute")
async def execute_action(
    item_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    now = datetime.utcnow()
    if item_id.startswith("timesheet:"):
        week_start = date.fromisoformat(item_id.split(":", 1)[1])
        entries = db.query(TimesheetEntry).filter(
            TimesheetEntry.employee_id == employee.id,
            TimesheetEntry.week_start == week_start,
            TimesheetEntry.status == "draft",
        ).all()
        if not entries:
            raise HTTPException(status_code=409, detail="This timesheet is no longer a draft.")
        total = round(sum(float(row.hours or 0) for row in entries if row.entry_code.upper() != "BRK"), 1)
        for row in entries:
            row.status = "submitted"
            row.submitted_at = now
            row.updated_at = now
        manager = manager_for(db, employee)
        if manager:
            db.add(Notification(
                user_id=manager.id,
                title="Timesheet submitted",
                message=f"{employee_name(employee)} submitted {total:g} hours.",
                type="timesheet",
                notification_type="timesheet",
                related_entity_type="timesheet",
                related_entity_id=entries[0].id,
                link_url="/employee/timesheets",
            ))
        db.commit()
        return {
            "confirmation": f"Timesheet submitted — {total:g} hours.",
            "next": f"{employee_name(manager)} will see it next. I'll tell you when it is reviewed.",
            "viewLabel": "View timesheet",
            "viewHref": "/employee/timesheets",
            "undoToken": sign_undo({"kind": "timesheet", "employee_id": employee.id, "week_start": week_start.isoformat()}),
        }

    if item_id.startswith("leave:"):
        request_id = item_id.split(":", 1)[1]
        request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id,
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.status == "pending",
        ).first()
        if not request:
            raise HTTPException(status_code=409, detail="This leave request is no longer pending.")
        manager = manager_for(db, employee)
        if not manager:
            raise HTTPException(status_code=409, detail="No reporting manager is assigned.")
        notification = Notification(
            user_id=manager.id,
            title="Leave approval reminder",
            message=f"{employee_name(employee)} is waiting for a leave request decision.",
            type="leave",
            notification_type="leave_reminder",
            related_entity_type="leave_request",
            related_entity_id=request.id,
            link_url="/employee/approvals",
        )
        db.add(notification)
        db.commit()
        return {
            "confirmation": f"Reminder sent to {employee_name(manager)}.",
            "next": "I'll keep watching the request and tell you when a decision arrives.",
            "viewLabel": "View request",
            "viewHref": "/employee/apply-leave",
            "undoToken": sign_undo({"kind": "notification", "employee_id": employee.id, "notification_id": notification.id}),
        }
    raise HTTPException(status_code=404, detail="Action item not found.")


@router.post("/action-items/{item_id}/undo")
async def undo_action(
    item_id: str,
    payload: UndoRequest,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_employee(db, x_user_id, x_user_email)
    undo = read_undo(payload.undoToken)
    if undo.get("employee_id") != employee.id:
        raise HTTPException(status_code=403, detail="This undo action belongs to another user.")
    if undo["kind"] == "timesheet":
        rows = db.query(TimesheetEntry).filter(
            TimesheetEntry.employee_id == employee.id,
            TimesheetEntry.week_start == date.fromisoformat(undo["week_start"]),
            TimesheetEntry.status == "submitted",
            TimesheetEntry.reviewed_at.is_(None),
        ).all()
        for row in rows:
            row.status = "draft"
            row.submitted_at = None
            row.updated_at = datetime.utcnow()
        db.commit()
        return {"message": "Timesheet returned to draft."}
    if undo["kind"] == "notification":
        notification = db.query(Notification).filter(
            Notification.id == undo["notification_id"],
            Notification.is_read == False,
        ).first()
        if notification:
            db.delete(notification)
            db.commit()
        return {"message": "Reminder withdrawn."}
    raise HTTPException(status_code=400, detail="Unsupported undo action.")

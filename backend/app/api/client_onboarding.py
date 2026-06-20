"""
Admin Client Onboarding API.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.client_onboarding import (
    Client,
    ClientActivityLog,
    ClientChecklistItem,
    ClientDocument,
    ClientMilestone,
    ClientOnboarding,
    ClientTask,
    ClientTeamMember,
)
from app.models.employee import Employee
from app.services.audit_service import log_audit
from app.services.settings_service import get_current_employee, is_admin_role

router = APIRouter(prefix="/admin/client-onboarding", tags=["Client Onboarding"])

CLIENT_STATUSES = {"prospect", "contract_signed", "onboarding", "active", "paused", "completed", "at_risk"}
STAGES = [
    "Contract Signed",
    "Requirements Gathering",
    "Environment Setup",
    "Team Allocation",
    "Training",
    "Go Live",
    "Hypercare",
    "Completed",
]
CHECKLIST_DEFAULTS = [
    "NDA Signed",
    "Contract Uploaded",
    "Kickoff Meeting Completed",
    "Client Requirements Collected",
    "Project Team Assigned",
    "Access Requirements Confirmed",
    "Environment Setup Started",
    "Training Completed",
    "Go-Live Approved",
]
MILESTONE_DEFAULTS = ["Kickoff", "Requirements Finalized", "UAT", "Go Live", "Hypercare Complete"]


def require_admin(db: Session, user_id: str | None, user_email: str | None) -> Employee:
    user = get_current_employee(db, user_id, user_email)
    if not is_admin_role(user.role):
        raise HTTPException(status_code=403, detail="Only Super Admin and HR/Admin roles can access Client Onboarding.")
    return user


def employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unassigned"
    return f"{employee.first_name} {employee.last_name}".strip()


def normalize_status(value: str | None, default: str = "prospect") -> str:
    normalized = (value or default).strip().lower().replace(" ", "_").replace("-", "_")
    if normalized not in CLIENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid client status.")
    return normalized


def serialize_employee(employee: Employee) -> dict:
    return {
        "id": employee.id,
        "name": employee_name(employee),
        "email": employee.work_email,
        "department": employee.department,
        "role": employee.role,
    }


def serialize_client_list(db: Session, client: Client) -> dict:
    onboarding = db.query(ClientOnboarding).filter(ClientOnboarding.client_id == client.id).first()
    owner_id = client.owner_id or (onboarding.owner_id if onboarding else None)
    owner = db.query(Employee).filter(Employee.id == owner_id).first() if owner_id else None
    return {
        "id": client.id,
        "client_name": client.client_name,
        "industry": client.industry,
        "website": client.website,
        "status": client.status,
        "primary_contact_name": client.primary_contact_name,
        "contact_email": client.contact_email,
        "onboarding_stage": onboarding.stage if onboarding else "Contract Signed",
        "progress_percent": onboarding.progress_percent if onboarding else 0,
        "target_go_live_date": onboarding.target_go_live_date.isoformat() if onboarding and onboarding.target_go_live_date else None,
        "owner_id": client.owner_id,
        "owner_name": employee_name(owner),
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }


def serialize_detail(db: Session, client: Client) -> dict:
    onboarding = db.query(ClientOnboarding).filter(ClientOnboarding.client_id == client.id).first()
    owner = db.query(Employee).filter(Employee.id == client.owner_id).first() if client.owner_id else None
    return {
        "client": {
            "id": client.id,
            "client_name": client.client_name,
            "industry": client.industry,
            "website": client.website,
            "primary_contact_name": client.primary_contact_name,
            "contact_email": client.contact_email,
            "contact_phone": client.contact_phone,
            "contract_start_date": client.contract_start_date.isoformat() if client.contract_start_date else None,
            "contract_end_date": client.contract_end_date.isoformat() if client.contract_end_date else None,
            "status": client.status,
            "owner_id": client.owner_id,
            "owner_name": employee_name(owner),
            "notes": client.notes,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "updated_at": client.updated_at.isoformat() if client.updated_at else None,
        },
        "onboarding": serialize_onboarding(onboarding),
        "checklist": [serialize_checklist(db, row) for row in db.query(ClientChecklistItem).filter(ClientChecklistItem.client_id == client.id).order_by(ClientChecklistItem.sort_order.asc(), ClientChecklistItem.created_at.asc()).all()],
        "tasks": [serialize_task(db, row) for row in db.query(ClientTask).filter(ClientTask.client_id == client.id).order_by(ClientTask.created_at.desc()).all()],
        "team": [serialize_team(db, row) for row in db.query(ClientTeamMember).filter(ClientTeamMember.client_id == client.id).order_by(ClientTeamMember.created_at.asc()).all()],
        "documents": [serialize_document(db, row) for row in db.query(ClientDocument).filter(ClientDocument.client_id == client.id).order_by(ClientDocument.created_at.desc()).all()],
        "milestones": [serialize_milestone(db, row) for row in db.query(ClientMilestone).filter(ClientMilestone.client_id == client.id).order_by(ClientMilestone.created_at.asc()).all()],
        "activity": [serialize_activity(db, row) for row in db.query(ClientActivityLog).filter(ClientActivityLog.client_id == client.id).order_by(ClientActivityLog.created_at.desc()).limit(80).all()],
    }


def serialize_onboarding(row: ClientOnboarding | None) -> dict:
    if not row:
        return {"stage": "Contract Signed", "progress_percent": 0, "target_go_live_date": None, "actual_go_live_date": None, "owner_id": None}
    return {
        "id": row.id,
        "stage": row.stage,
        "progress_percent": row.progress_percent,
        "target_go_live_date": row.target_go_live_date.isoformat() if row.target_go_live_date else None,
        "actual_go_live_date": row.actual_go_live_date.isoformat() if row.actual_go_live_date else None,
        "owner_id": row.owner_id,
    }


def serialize_checklist(db: Session, row: ClientChecklistItem) -> dict:
    owner = db.query(Employee).filter(Employee.id == row.owner_id).first() if row.owner_id else None
    return {
        "id": row.id,
        "title": row.title,
        "is_complete": row.is_complete,
        "owner_id": row.owner_id,
        "owner_name": employee_name(owner) if owner else None,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "notes": row.notes,
    }


def serialize_task(db: Session, row: ClientTask) -> dict:
    assigned = db.query(Employee).filter(Employee.id == row.assigned_to_id).first() if row.assigned_to_id else None
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "assigned_to_id": row.assigned_to_id,
        "assigned_to_name": employee_name(assigned) if assigned else None,
        "priority": row.priority,
        "status": row.status,
        "due_date": row.due_date.isoformat() if row.due_date else None,
    }


def serialize_team(db: Session, row: ClientTeamMember) -> dict:
    employee = db.query(Employee).filter(Employee.id == row.employee_id).first()
    return {
        "id": row.id,
        "employee_id": row.employee_id,
        "employee_name": employee_name(employee),
        "role": row.role,
        "notes": row.notes,
    }


def serialize_document(db: Session, row: ClientDocument) -> dict:
    uploader = db.query(Employee).filter(Employee.id == row.uploaded_by).first() if row.uploaded_by else None
    return {
        "id": row.id,
        "document_type": row.document_type,
        "file_name": row.file_name,
        "file_url": row.file_url,
        "notes": row.notes,
        "uploaded_by_name": employee_name(uploader) if uploader else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_milestone(db: Session, row: ClientMilestone) -> dict:
    return {
        "id": row.id,
        "milestone_name": row.milestone_name,
        "target_date": row.target_date.isoformat() if row.target_date else None,
        "actual_date": row.actual_date.isoformat() if row.actual_date else None,
        "status": row.status,
    }


def serialize_activity(db: Session, row: ClientActivityLog) -> dict:
    actor = db.query(Employee).filter(Employee.id == row.performed_by).first() if row.performed_by else None
    return {
        "id": row.id,
        "action": row.action,
        "details": row.details,
        "performed_by_name": employee_name(actor),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def log_activity(db: Session, client_id: str, actor: Employee, action: str, details: str | None = None) -> None:
    db.add(ClientActivityLog(
        client_id=client_id,
        action=action,
        details=details,
        performed_by=actor.id,
        created_by=actor.id,
        updated_by=actor.id,
    ))
    log_audit(
        db,
        actor,
        action=f"client_onboarding.{action.strip().lower().replace(' ', '_')}",
        entity_type="client",
        entity_id=client_id,
        reason=details,
        metadata={"legacy_client_activity_log": True},
        source="admin",
    )


def validate_client_payload(payload: ClientPayload) -> None:
    if payload.onboarding_stage not in STAGES:
        raise HTTPException(status_code=400, detail="Invalid onboarding stage.")
    if payload.contract_start_date and payload.contract_end_date and payload.contract_end_date < payload.contract_start_date:
        raise HTTPException(status_code=400, detail="Contract end date cannot be before contract start date.")
    if payload.contract_start_date and payload.target_go_live_date and payload.target_go_live_date < payload.contract_start_date:
        raise HTTPException(status_code=400, detail="Target go-live date cannot be before contract start date.")


def refresh_progress(db: Session, client_id: str) -> None:
    onboarding = db.query(ClientOnboarding).filter(ClientOnboarding.client_id == client_id).first()
    if not onboarding:
        return
    checklist = db.query(ClientChecklistItem).filter(ClientChecklistItem.client_id == client_id).all()
    progress = round((sum(1 for item in checklist if item.is_complete) / len(checklist)) * 100) if checklist else 0
    onboarding.progress_percent = progress
    if progress == 100:
        onboarding.stage = "Completed"


def ensure_defaults(db: Session, client_id: str, actor: Employee) -> None:
    if db.query(ClientChecklistItem).filter(ClientChecklistItem.client_id == client_id).count() == 0:
        for index, title in enumerate(CHECKLIST_DEFAULTS):
            db.add(ClientChecklistItem(client_id=client_id, title=title, sort_order=index + 1, owner_id=actor.id, created_by=actor.id, updated_by=actor.id))
    if db.query(ClientMilestone).filter(ClientMilestone.client_id == client_id).count() == 0:
        for title in MILESTONE_DEFAULTS:
            db.add(ClientMilestone(client_id=client_id, milestone_name=title, created_by=actor.id, updated_by=actor.id))


class ClientPayload(BaseModel):
    client_name: str = Field(..., min_length=2, max_length=200)
    industry: str = Field(..., min_length=2, max_length=120)
    website: str | None = Field(default=None, max_length=255)
    primary_contact_name: str = Field(..., min_length=2, max_length=160)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=50)
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    status: str = "prospect"
    owner_id: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    onboarding_stage: str = "Contract Signed"
    target_go_live_date: date | None = None


class ChecklistPayload(BaseModel):
    is_complete: bool | None = None
    owner_id: str | None = None
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class TaskPayload(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    assigned_to_id: str | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    status: str = Field(default="not_started", pattern="^(not_started|in_progress|blocked|completed)$")
    due_date: date | None = None


class TeamPayload(BaseModel):
    employee_id: str
    role: str = Field(..., pattern="^(client_manager|project_manager|technical_lead|developer|qa|support)$")
    notes: str | None = Field(default=None, max_length=1000)


class DocumentPayload(BaseModel):
    document_type: str = Field(..., pattern="^(nda|msa|sow|requirements|architecture|training_material|other)$")
    file_name: str = Field(..., min_length=2, max_length=255)
    file_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class MilestonePayload(BaseModel):
    milestone_name: str = Field(..., min_length=2, max_length=200)
    target_date: date | None = None
    actual_date: date | None = None
    status: str = Field(default="not_started", pattern="^(not_started|in_progress|blocked|completed|approved)$")


@router.get("")
async def list_clients(
    search: str | None = Query(None),
    status: str | None = Query(None),
    stage: str | None = Query(None),
    owner: str | None = Query(None),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    require_admin(db, x_user_id, x_user_email)
    total_count = db.query(Client).count()
    query = db.query(Client)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Client.client_name.ilike(term), Client.primary_contact_name.ilike(term), Client.contact_email.ilike(term), Client.industry.ilike(term), Client.website.ilike(term)))
    if status and status != "All":
        query = query.filter(Client.status == normalize_status(status))
    if owner and owner != "All":
        query = query.filter(Client.owner_id == owner)
    clients = query.order_by(Client.updated_at.desc()).all()
    rows = [serialize_client_list(db, client) for client in clients]
    if stage and stage != "All":
        rows = [row for row in rows if row["onboarding_stage"] == stage]
    employees = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai").order_by(Employee.first_name.asc()).all()
    return {"clients": rows, "total_count": total_count, "employees": [serialize_employee(employee) for employee in employees], "stages": STAGES}


@router.post("")
async def create_client(
    payload: ClientPayload,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = require_admin(db, x_user_id, x_user_email)
    validate_client_payload(payload)
    status = normalize_status(payload.status)
    client = Client(
        client_name=payload.client_name.strip(),
        industry=payload.industry,
        website=payload.website,
        primary_contact_name=payload.primary_contact_name,
        contact_email=str(payload.contact_email) if payload.contact_email else None,
        contact_phone=payload.contact_phone,
        contract_start_date=payload.contract_start_date,
        contract_end_date=payload.contract_end_date,
        status=status,
        owner_id=payload.owner_id or actor.id,
        notes=payload.notes,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(client)
    db.flush()
    db.add(ClientOnboarding(
        client_id=client.id,
        stage=payload.onboarding_stage or "Contract Signed",
        target_go_live_date=payload.target_go_live_date,
        owner_id=payload.owner_id or actor.id,
        created_by=actor.id,
        updated_by=actor.id,
    ))
    ensure_defaults(db, client.id, actor)
    log_activity(db, client.id, actor, "Created client", f"Created {client.client_name}.")
    db.commit()
    db.refresh(client)
    return serialize_detail(db, client)


@router.get("/{client_id}")
async def get_client(
    client_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = require_admin(db, x_user_id, x_user_email)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    ensure_defaults(db, client.id, actor)
    db.commit()
    return serialize_detail(db, client)


@router.put("/{client_id}")
async def update_client(client_id: str, payload: ClientPayload, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    validate_client_payload(payload)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.client_name = payload.client_name.strip()
    client.industry = payload.industry
    client.website = payload.website
    client.primary_contact_name = payload.primary_contact_name
    client.contact_email = str(payload.contact_email) if payload.contact_email else None
    client.contact_phone = payload.contact_phone
    client.contract_start_date = payload.contract_start_date
    client.contract_end_date = payload.contract_end_date
    old_status = client.status
    client.status = normalize_status(payload.status)
    client.owner_id = payload.owner_id
    client.notes = payload.notes
    client.updated_by = actor.id
    onboarding = db.query(ClientOnboarding).filter(ClientOnboarding.client_id == client.id).first()
    if onboarding:
        old_stage = onboarding.stage
        onboarding.stage = payload.onboarding_stage or onboarding.stage
        onboarding.target_go_live_date = payload.target_go_live_date
        onboarding.owner_id = payload.owner_id
        onboarding.updated_by = actor.id
        if old_stage != onboarding.stage:
            log_activity(db, client.id, actor, "Changed stage", f"{old_stage} to {onboarding.stage}.")
    if old_status != client.status:
        log_activity(db, client.id, actor, "Changed status", f"{old_status} to {client.status}.")
    log_activity(db, client.id, actor, "Updated client", f"Updated {client.client_name}.")
    db.commit()
    return serialize_detail(db, client)


@router.delete("/{client_id}")
async def delete_client(client_id: str, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    require_admin(db, x_user_id, x_user_email)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for model in [ClientActivityLog, ClientChecklistItem, ClientTask, ClientTeamMember, ClientDocument, ClientMilestone, ClientOnboarding]:
        db.query(model).filter(model.client_id == client_id).delete()
    db.delete(client)
    db.commit()
    return {"success": True}


@router.put("/{client_id}/checklist/{item_id}")
async def update_checklist(client_id: str, item_id: str, payload: ChecklistPayload, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = db.query(ClientChecklistItem).filter(ClientChecklistItem.id == item_id, ClientChecklistItem.client_id == client_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    for field in ["is_complete", "owner_id", "due_date", "notes"]:
        value = getattr(payload, field)
        if value is not None or field in payload.model_fields_set:
            setattr(row, field, value)
    row.updated_by = actor.id
    refresh_progress(db, client_id)
    if payload.is_complete is not None:
        log_activity(db, client_id, actor, "Completed checklist item" if payload.is_complete else "Reopened checklist item", row.title)
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.post("/{client_id}/tasks")
async def create_task(client_id: str, payload: TaskPayload, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = ClientTask(client_id=client_id, title=payload.title, description=payload.description, assigned_to_id=payload.assigned_to_id, priority=payload.priority, status=payload.status, due_date=payload.due_date, created_by=actor.id, updated_by=actor.id)
    db.add(row)
    log_activity(db, client_id, actor, "Added task", payload.title)
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.put("/{client_id}/tasks/{task_id}")
async def update_task(client_id: str, task_id: str, payload: TaskPayload, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = db.query(ClientTask).filter(ClientTask.id == task_id, ClientTask.client_id == client_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    row.updated_by = actor.id
    log_activity(db, client_id, actor, "Completed task" if row.status == "completed" else "Updated task", row.title)
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.delete("/{client_id}/tasks/{task_id}")
async def delete_task(client_id: str, task_id: str, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = db.query(ClientTask).filter(ClientTask.id == task_id, ClientTask.client_id == client_id).first()
    if row:
        log_activity(db, client_id, actor, "Deleted task", row.title)
    db.query(ClientTask).filter(ClientTask.id == task_id, ClientTask.client_id == client_id).delete()
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.post("/{client_id}/team")
async def create_team_member(client_id: str, payload: TeamPayload, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = ClientTeamMember(client_id=client_id, employee_id=payload.employee_id, role=payload.role, notes=payload.notes, created_by=actor.id, updated_by=actor.id)
    db.add(row)
    log_activity(db, client_id, actor, "Added team member", payload.role)
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.delete("/{client_id}/team/{member_id}")
async def delete_team_member(client_id: str, member_id: str, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = db.query(ClientTeamMember).filter(ClientTeamMember.id == member_id, ClientTeamMember.client_id == client_id).first()
    if row:
        log_activity(db, client_id, actor, "Removed team member", row.role)
    db.query(ClientTeamMember).filter(ClientTeamMember.id == member_id, ClientTeamMember.client_id == client_id).delete()
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.post("/{client_id}/documents")
async def create_document(client_id: str, payload: DocumentPayload, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = ClientDocument(client_id=client_id, document_type=payload.document_type, file_name=payload.file_name, file_url=payload.file_url, notes=payload.notes, uploaded_by=actor.id, created_by=actor.id, updated_by=actor.id)
    db.add(row)
    log_activity(db, client_id, actor, "Uploaded document", payload.file_name)
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.delete("/{client_id}/documents/{document_id}")
async def delete_document(client_id: str, document_id: str, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = db.query(ClientDocument).filter(ClientDocument.id == document_id, ClientDocument.client_id == client_id).first()
    if row:
        log_activity(db, client_id, actor, "Removed document", row.file_name)
    db.query(ClientDocument).filter(ClientDocument.id == document_id, ClientDocument.client_id == client_id).delete()
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.post("/{client_id}/milestones")
async def create_milestone(client_id: str, payload: MilestonePayload, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = ClientMilestone(client_id=client_id, milestone_name=payload.milestone_name, target_date=payload.target_date, actual_date=payload.actual_date, status=payload.status, created_by=actor.id, updated_by=actor.id)
    db.add(row)
    log_activity(db, client_id, actor, "Added milestone", payload.milestone_name)
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.put("/{client_id}/milestones/{milestone_id}")
async def update_milestone(client_id: str, milestone_id: str, payload: MilestonePayload, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = db.query(ClientMilestone).filter(ClientMilestone.id == milestone_id, ClientMilestone.client_id == client_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Milestone not found")
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    row.updated_by = actor.id
    log_activity(db, client_id, actor, "Updated milestone", row.milestone_name)
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())


@router.delete("/{client_id}/milestones/{milestone_id}")
async def delete_milestone(client_id: str, milestone_id: str, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_admin(db, x_user_id, x_user_email)
    row = db.query(ClientMilestone).filter(ClientMilestone.id == milestone_id, ClientMilestone.client_id == client_id).first()
    if row:
        log_activity(db, client_id, actor, "Deleted milestone", row.milestone_name)
    db.query(ClientMilestone).filter(ClientMilestone.id == milestone_id, ClientMilestone.client_id == client_id).delete()
    db.commit()
    return serialize_detail(db, db.query(Client).filter(Client.id == client_id).first())

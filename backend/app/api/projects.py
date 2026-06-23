from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Response, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.allocation import Allocation
from app.models.employee import Employee
from app.schemas.allocation import AllocationOut
from app.schemas.operations import ProjectCreate, ProjectManagerSchema, ProjectOut, ProjectUpdate
from app.services.allocation_service import serialize_allocation
from app.services.audit_service import log_authorization_failure
from app.services.project_service import (
    assign_project_manager,
    create_project,
    delete_project_document,
    download_project_document,
    get_project,
    list_project_documents,
    list_projects,
    serialize_project_document,
    update_project,
    upload_project_document,
)
from app.services.settings_service import get_current_employee, normalize_role

router = APIRouter(prefix="/projects", tags=["Projects"])


def _is_project_admin(actor: Employee) -> bool:
    return normalize_role(actor.role) in {"super_admin", "hr_admin", "admin", "global_access"}


def _require_project_admin(db: Session, actor: Employee, action: str) -> None:
    if _is_project_admin(actor):
        return
    log_authorization_failure(
        db,
        actor,
        action=action,
        entity_type="project",
        entity_id=actor.id,
        reason="User attempted to manage projects without permission.",
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Not authorized to manage projects.")


def _employee_name(employee: Employee) -> str:
    middle_name = getattr(employee, "middle_name", None)
    parts = [employee.first_name, middle_name, employee.last_name]
    return " ".join(part.strip() for part in parts if part and part.strip()) or employee.work_email


def _employee_payload(employee: Employee) -> dict:
    return {
        "id": employee.id,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "work_email": employee.work_email,
        "role": employee.role,
        "department": employee.department,
        "designation": employee.designation,
        "profile_image_url": employee.profile_image_url,
        "reporting_manager": employee.reporting_manager,
        "manager_id": employee.manager_id,
        "name": _employee_name(employee),
    }


@router.get("/", response_model=dict)
async def projects_index(
    search: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=250),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    get_current_employee(db, current_user_id, current_user_email)
    projects, total = list_projects(db, search=search, status=status, limit=limit, offset=offset)
    return {"projects": projects, "total": total, "limit": limit, "offset": offset}


@router.post("/", response_model=ProjectOut)
async def create_project_endpoint(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_project_admin(db, actor, "project.create")
    return get_project(db, create_project(db, data, actor).id)


@router.get("/assignable-employees", response_model=dict)
async def assignable_employees(
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=250),
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    if not (_is_project_admin(actor) or normalize_role(actor.role) == "manager"):
        raise HTTPException(status_code=403, detail="Not authorized to view assignable employees.")

    query = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai")
    if normalize_role(actor.role) == "manager" and not _is_project_admin(actor):
        actor_name = _employee_name(actor)
        query = query.filter(or_(Employee.manager_id == actor.id, Employee.reporting_manager == actor_name))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Employee.first_name.ilike(term), Employee.last_name.ilike(term), Employee.work_email.ilike(term)))

    employees = query.order_by(Employee.first_name.asc(), Employee.last_name.asc()).limit(limit).all()
    managers = (
        db.query(Employee)
        .filter(Employee.role.in_(["manager", "hr_admin", "super_admin", "admin"]), Employee.work_email != "superadmin@reknew.ai")
        .order_by(Employee.first_name.asc(), Employee.last_name.asc())
        .all()
        if _is_project_admin(actor)
        else [actor]
    )
    return {
        "employees": [_employee_payload(employee) for employee in employees],
        "managers": [_employee_payload(manager) for manager in managers],
    }


@router.get("/{project_id}", response_model=ProjectOut)
async def project_detail(
    project_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    get_current_employee(db, current_user_id, current_user_email)
    return get_project(db, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project_endpoint(
    project_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_project_admin(db, actor, "project.update")
    return get_project(db, update_project(db, project_id, data, actor).id)


@router.patch("/{project_id}/manager", response_model=ProjectOut)
async def update_project_manager(
    project_id: str,
    data: ProjectManagerSchema,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    _require_project_admin(db, actor, "project.manager.assign")
    return get_project(db, assign_project_manager(db, project_id, data.manager_employee_id, actor).id)


@router.get("/{project_id}/allocations", response_model=list[AllocationOut])
async def project_allocations(
    project_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    get_current_employee(db, current_user_id, current_user_email)
    get_project(db, project_id)
    allocations = (
        db.query(Allocation)
        .filter(Allocation.project_id == project_id)
        .order_by(Allocation.status.asc(), Allocation.start_date.desc(), Allocation.updated_at.desc())
        .all()
    )
    return [serialize_allocation(db, allocation) for allocation in allocations]


@router.get("/{project_id}/documents", response_model=list[dict])
async def project_documents(
    project_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    documents = list_project_documents(db, actor, project_id)
    return [serialize_project_document(db, document) for document in documents]


@router.post("/{project_id}/documents", response_model=dict)
async def upload_document(
    project_id: str,
    document_type: str = Form("OTHER"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    file_bytes = await file.read()
    document = upload_project_document(
        db,
        actor,
        project_id=project_id,
        file_name=file.filename or "project-document",
        content_type=file.content_type,
        file_bytes=file_bytes,
        document_type=document_type,
    )
    return serialize_project_document(db, document)


@router.get("/{project_id}/documents/{document_id}/download")
async def download_document(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    file_bytes, mime_type, file_name = download_project_document(db, actor, project_id, document_id)
    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.delete("/{project_id}/documents/{document_id}", response_model=dict)
async def delete_document(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user_id: str | None = Header(None, alias="x-user-id"),
    current_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, current_user_id, current_user_email)
    delete_project_document(db, actor, project_id, document_id)
    return {"ok": True}

from __future__ import annotations

from datetime import datetime
import hashlib
import os
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.allocation import Allocation
from app.models.employee import Employee
from app.models.operations import Project, ProjectDocument
from app.schemas.operations import ProjectCreate, ProjectUpdate
from app.services.attachment_service import validate_attachment
from app.services.audit_service import changed_fields, log_audit
from app.services.settings_service import normalize_role
from app.services.storage.base import StorageProvider
from app.services.storage.storage_factory import get_storage

PROJECT_DOCUMENT_TYPES = {"CONTRACT", "SOW", "NDA", "INVOICE", "REPORT", "OTHER"}


def _is_project_admin(actor: Employee) -> bool:
    return normalize_role(actor.role) in {"super_admin", "hr_admin", "global_access"}


def _employee_name_from_row(employee: Employee | None) -> str | None:
    if not employee:
        return None
    middle_name = getattr(employee, "middle_name", None)
    parts = [employee.first_name, middle_name, employee.last_name]
    return " ".join(part.strip() for part in parts if part and part.strip()) or employee.work_email


def _employee_name(db: Session, employee_id: str | None) -> str | None:
    if not employee_id:
        return None
    return _employee_name_from_row(db.query(Employee).filter(Employee.id == employee_id).first())


def get_project_record(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def serialize_project(db: Session, project: Project) -> dict[str, Any]:
    active_statuses = {"active", "upcoming"}
    allocation_count = db.query(func.count(Allocation.id)).filter(Allocation.project_id == project.id).scalar() or 0
    active_allocation_count = (
        db.query(func.count(Allocation.id))
        .filter(Allocation.project_id == project.id, Allocation.status.in_(active_statuses))
        .scalar()
        or 0
    )
    return {
        "id": project.id,
        "name": project.name,
        "code": project.code,
        "description": project.description,
        "client_name": project.client_name,
        "start_date": project.start_date,
        "end_date": project.end_date,
        "status": project.status,
        "project_manager_id": project.project_manager_id,
        "project_manager_name": _employee_name(db, project.project_manager_id),
        "created_by": project.created_by,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "allocation_count": int(allocation_count),
        "active_allocation_count": int(active_allocation_count),
        "active_employee_count": int(active_allocation_count),
    }


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def _validate_dates(start_date, end_date) -> None:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date cannot be before start_date.")


def list_projects(
    db: Session,
    search: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    query = db.query(Project)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Project.name.ilike(term),
                Project.code.ilike(term),
                Project.client_name.ilike(term),
                Project.description.ilike(term),
            )
        )
    if status and status != "all":
        query = query.filter(Project.status == status)

    total = query.count()
    projects = query.order_by(Project.updated_at.desc(), Project.name.asc()).offset(offset).limit(limit).all()
    return [serialize_project(db, project) for project in projects], total


def get_project(db: Session, project_id: str) -> dict[str, Any]:
    return serialize_project(db, get_project_record(db, project_id))


def create_project(db: Session, data: ProjectCreate, actor: Employee) -> Project:
    payload = data.model_dump()
    payload["name"] = payload["name"].strip()
    payload["code"] = _normalize_code(payload["code"])
    _validate_dates(payload.get("start_date"), payload.get("end_date"))

    existing = db.query(Project).filter(func.lower(Project.code) == payload["code"].lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Project code already exists.")

    project = Project(
        **payload,
        created_by=actor.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(project)
    db.flush()
    log_audit(
        db,
        actor,
        action="project_created",
        entity_type="project",
        entity_id=project.id,
        new_values=serialize_project(db, project),
        metadata={"project_id": project.id, "changed_by": actor.id, "changed_at": datetime.utcnow().isoformat()},
    )
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project_id: str, data: ProjectUpdate, actor: Employee) -> Project:
    project = get_project_record(db, project_id)
    old_values = serialize_project(db, project)
    patch = data.model_dump(exclude_unset=True)
    if "name" in patch and patch["name"] is not None:
        patch["name"] = patch["name"].strip()
    if "code" in patch and patch["code"] is not None:
        patch["code"] = _normalize_code(patch["code"])
        duplicate = (
            db.query(Project)
            .filter(func.lower(Project.code) == patch["code"].lower(), Project.id != project.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Project code already exists.")

    next_start = patch.get("start_date", project.start_date)
    next_end = patch.get("end_date", project.end_date)
    _validate_dates(next_start, next_end)

    for field, value in patch.items():
        setattr(project, field, value)
    project.updated_at = datetime.utcnow()

    db.flush()
    new_values = serialize_project(db, project)
    changes = changed_fields(old_values, new_values)
    if changes:
        log_audit(
            db,
            actor,
            action="project_updated",
            entity_type="project",
            entity_id=project.id,
            old_values=old_values,
            new_values=new_values,
            changed_fields_payload=changes,
            metadata={"project_id": project.id, "changed_by": actor.id, "changed_at": datetime.utcnow().isoformat()},
        )
    db.commit()
    db.refresh(project)
    return project


def assign_project_manager(db: Session, project_id: str, manager_employee_id: str | None, actor: Employee) -> Project:
    project = get_project_record(db, project_id)
    if manager_employee_id:
        employee = db.query(Employee).filter(Employee.id == manager_employee_id, Employee.is_active.is_(True)).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found or inactive.")

    old_manager_id = project.project_manager_id
    project.project_manager_id = manager_employee_id
    project.updated_at = datetime.utcnow()
    log_audit(
        db,
        actor,
        action="project_manager_assigned",
        entity_type="project",
        entity_id=project.id,
        metadata={
            "project_name": project.name,
            "old_manager_id": old_manager_id,
            "new_manager_id": manager_employee_id,
        },
    )
    db.commit()
    db.refresh(project)
    return project


def _project_document_query(db: Session, project_id: str, document_id: str):
    return db.query(ProjectDocument).filter(
        ProjectDocument.id == document_id,
        ProjectDocument.project_id == project_id,
        ProjectDocument.is_deleted.is_(False),
    )


def _validate_project_document(file_name: str, content_type: str | None, file_bytes: bytes, document_type: str) -> None:
    if document_type not in PROJECT_DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid document_type '{document_type}'.")
    validate_attachment(file_name, content_type, file_bytes, "OTHER")


def upload_project_document(
    db: Session,
    actor: Employee,
    project_id: str,
    file_name: str,
    content_type: str | None,
    file_bytes: bytes,
    document_type: str,
) -> ProjectDocument:
    project = get_project_record(db, project_id)
    if not _is_project_admin(actor):
        raise HTTPException(status_code=403, detail="Only HR Admin or Super Admin can upload project documents.")

    document_type = (document_type or "OTHER").upper()
    _validate_project_document(file_name, content_type, file_bytes, document_type)
    prefix = str(uuid.uuid4()).replace("-", "")[:8]
    stored_file_name = StorageProvider.generate_safe_filename(file_name, prefix)
    folder_path = f"projects/{project_id}/documents"
    upload_result = get_storage().upload_file(file_bytes, folder_path, stored_file_name)
    checksum = hashlib.sha256(file_bytes).hexdigest()
    doc = ProjectDocument(
        project_id=project.id,
        uploaded_by_id=actor.id,
        original_file_name=file_name,
        stored_file_name=upload_result.stored_file_name,
        file_extension=os.path.splitext(file_name)[1].lower(),
        mime_type=content_type,
        file_size_bytes=len(file_bytes),
        checksum_sha256=checksum,
        storage_provider=settings.STORAGE_PROVIDER,
        storage_path=upload_result.storage_path,
        document_type=document_type,
    )
    db.add(doc)
    log_audit(
        db,
        actor,
        action="project_document_uploaded",
        entity_type="project",
        entity_id=project.id,
        metadata={
            "original_file_name": file_name,
            "document_type": document_type,
            "file_size_bytes": len(file_bytes),
        },
    )
    db.commit()
    db.refresh(doc)
    return doc


def list_project_documents(db: Session, actor: Employee, project_id: str) -> list[ProjectDocument]:
    get_project_record(db, project_id)
    return (
        db.query(ProjectDocument)
        .filter(ProjectDocument.project_id == project_id, ProjectDocument.is_deleted.is_(False))
        .order_by(ProjectDocument.created_at.desc())
        .all()
    )


def download_project_document(db: Session, actor: Employee, project_id: str, document_id: str) -> tuple[bytes, str, str]:
    project = get_project_record(db, project_id)
    doc = _project_document_query(db, project_id, document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        file_bytes = get_storage().download_file(doc.storage_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document file not found.")
    log_audit(
        db,
        actor,
        action="project_document_downloaded",
        entity_type="project",
        entity_id=project.id,
        metadata={"document_id": doc.id, "document_type": doc.document_type},
    )
    db.commit()
    return file_bytes, doc.mime_type or "application/octet-stream", doc.original_file_name


def delete_project_document(db: Session, actor: Employee, project_id: str, document_id: str) -> None:
    project = get_project_record(db, project_id)
    doc = _project_document_query(db, project_id, document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.uploaded_by_id != actor.id and not _is_project_admin(actor):
        raise HTTPException(status_code=403, detail="Not authorized to delete this project document.")
    doc.is_deleted = True
    doc.deleted_at = datetime.utcnow()
    doc.deleted_by_id = actor.id
    doc.updated_at = datetime.utcnow()
    log_audit(
        db,
        actor,
        action="project_document_deleted",
        entity_type="project",
        entity_id=project.id,
        metadata={"document_id": doc.id, "original_file_name": doc.original_file_name},
    )
    db.commit()


def serialize_project_document(db: Session, doc: ProjectDocument) -> dict[str, Any]:
    uploader = db.query(Employee).filter(Employee.id == doc.uploaded_by_id).first()
    return {
        "id": doc.id,
        "project_id": doc.project_id,
        "original_file_name": doc.original_file_name,
        "file_extension": doc.file_extension,
        "mime_type": doc.mime_type,
        "file_size_bytes": doc.file_size_bytes,
        "document_type": doc.document_type,
        "storage_provider": doc.storage_provider,
        "uploaded_by_id": doc.uploaded_by_id,
        "uploaded_by_name": _employee_name_from_row(uploader),
        "created_at": doc.created_at,
    }

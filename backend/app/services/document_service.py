"""Secure storage and authorization for employee-facing documents."""

from __future__ import annotations

from datetime import datetime
import hashlib
import os
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.core.config import settings
from app.models.documents import EmployeeDocument
from app.models.employee import Employee
from app.services.attachment_service import validate_attachment
from app.services.audit_service import log_audit
from app.services.settings_service import is_admin_role
from app.services.storage.base import StorageProvider
from app.services.storage.storage_factory import get_storage


CATEGORIES = {"payroll", "policy", "personal", "certificate"}
EMPLOYEE_UPLOAD_CATEGORIES = {"personal", "certificate"}
FOLDER_NAMES = {
    "payroll": "Payroll",
    "policy": "Policy & Company",
    "personal": "Personal",
    "certificate": "Certificates",
}


def infer_category(file_name: str) -> str:
    value = (file_name or "").lower().replace("_", " ").replace("-", " ")
    keyword_groups = (
        ("payroll", ("payslip", "pay slip", "form 16", "salary", "bonus letter")),
        ("policy", ("policy", "handbook", "code of conduct", "company guideline")),
        ("personal", ("passport", "aadhaar", "aadhar", "pan card", "offer letter", "address proof", "id proof")),
        ("certificate", ("certificate", "certification", "degree", "college", "diploma", "training completion")),
    )
    for category, keywords in keyword_groups:
        if any(keyword in value for keyword in keywords):
            return category
    return "personal"


def normalize_category(category: str | None, file_name: str) -> str:
    normalized = (category or "").strip().lower()
    if not normalized:
        return infer_category(file_name)
    if normalized not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Category must be payroll, policy, personal, or certificate.")
    return normalized


def _visible_query(db: Session, actor: Employee) -> Query:
    return db.query(EmployeeDocument).filter(
        EmployeeDocument.is_deleted.is_(False),
        or_(EmployeeDocument.category == "policy", EmployeeDocument.employee_id == actor.id),
    )


def list_documents(db: Session, actor: Employee) -> list[EmployeeDocument]:
    return _visible_query(db, actor).order_by(EmployeeDocument.updated_at.desc()).all()


def get_visible_document(db: Session, actor: Employee, document_id: str) -> EmployeeDocument:
    row = _visible_query(db, actor).filter(EmployeeDocument.id == document_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    return row


def _ensure_upload_allowed(actor: Employee, category: str) -> None:
    if is_admin_role(actor.role):
        return
    if category not in EMPLOYEE_UPLOAD_CATEGORIES:
        raise HTTPException(status_code=403, detail="Employees can upload only Personal or Certificate documents.")


def _store(file_name: str, content_type: str | None, file_bytes: bytes, employee_id: str, category: str):
    validate_attachment(file_name, content_type, file_bytes, "OTHER")
    prefix = uuid.uuid4().hex[:8]
    stored_file_name = StorageProvider.generate_safe_filename(file_name, prefix)
    folder_path = f"employee-documents/{employee_id}/{category}"
    result = get_storage().upload_file(file_bytes, folder_path, stored_file_name)
    return result, hashlib.sha256(file_bytes).hexdigest()


def upload_document(
    db: Session,
    actor: Employee,
    file_name: str,
    content_type: str | None,
    file_bytes: bytes,
    category: str | None,
) -> EmployeeDocument:
    normalized = normalize_category(category, file_name)
    _ensure_upload_allowed(actor, normalized)
    result, checksum = _store(file_name, content_type, file_bytes, actor.id, normalized)
    row = EmployeeDocument(
        employee_id=None if normalized == "policy" else actor.id,
        uploaded_by_id=actor.id,
        name=os.path.basename(file_name),
        stored_file_name=result.stored_file_name,
        mime_type=content_type,
        file_size_bytes=len(file_bytes),
        checksum_sha256=checksum,
        storage_provider=settings.STORAGE_PROVIDER,
        storage_path=result.storage_path,
        category=normalized,
        folder=FOLDER_NAMES[normalized],
        status="none",
    )
    db.add(row)
    db.flush()
    log_audit(
        db,
        actor,
        action="employee_document_uploaded",
        entity_type="employee_document",
        entity_id=row.id,
        metadata={"name": row.name, "category": normalized, "file_size_bytes": len(file_bytes)},
    )
    db.commit()
    db.refresh(row)
    return row


def replace_document(
    db: Session,
    actor: Employee,
    document_id: str,
    file_name: str,
    content_type: str | None,
    file_bytes: bytes,
    category: str | None,
) -> EmployeeDocument:
    row = get_visible_document(db, actor, document_id)
    if not is_admin_role(actor.role) and (row.employee_id != actor.id or row.category not in EMPLOYEE_UPLOAD_CATEGORIES):
        raise HTTPException(status_code=403, detail="This document is download-only for employees.")
    normalized = normalize_category(category or row.category, file_name)
    _ensure_upload_allowed(actor, normalized)
    result, checksum = _store(file_name, content_type, file_bytes, actor.id, normalized)
    old_storage_path = row.storage_path
    row.name = os.path.basename(file_name)
    row.stored_file_name = result.stored_file_name
    row.mime_type = content_type
    row.file_size_bytes = len(file_bytes)
    row.checksum_sha256 = checksum
    row.storage_provider = settings.STORAGE_PROVIDER
    row.storage_path = result.storage_path
    row.category = normalized
    row.folder = FOLDER_NAMES[normalized]
    row.status = "none"
    row.tag = None
    row.employee_id = None if normalized == "policy" else actor.id
    row.updated_at = datetime.utcnow()
    log_audit(
        db,
        actor,
        action="employee_document_replaced",
        entity_type="employee_document",
        entity_id=row.id,
        metadata={"name": row.name, "category": normalized, "file_size_bytes": len(file_bytes)},
    )
    db.commit()
    try:
        get_storage().delete_file(old_storage_path)
    except (FileNotFoundError, ValueError):
        pass
    db.refresh(row)
    return row


def download_document(db: Session, actor: Employee, document_id: str) -> tuple[bytes, str, str]:
    row = get_visible_document(db, actor, document_id)
    try:
        file_bytes = get_storage().download_file(row.storage_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document file not found.")
    log_audit(
        db,
        actor,
        action="employee_document_downloaded",
        entity_type="employee_document",
        entity_id=row.id,
        metadata={"category": row.category},
    )
    db.commit()
    return file_bytes, row.mime_type or "application/octet-stream", row.name


def format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{round(size / 1024)} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def serialize_document(row: EmployeeDocument) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "category": row.category,
        "folder": row.folder,
        "size": format_file_size(row.file_size_bytes),
        "sizeBytes": row.file_size_bytes,
        "uploadedAt": row.updated_at,
        "status": row.status,
        "tag": row.tag,
    }

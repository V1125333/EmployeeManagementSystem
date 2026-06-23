"""Secured request attachment storage and access."""

from __future__ import annotations

from datetime import date
import hashlib
import os
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.requests import RequestAttachment
from app.services.audit_service import log_audit
from app.services.requests_service import (
    _can_pay_expenses,
    _is_admin,
    employee_name,
    ensure_read_access,
    find_employee,
    get_request,
    utc_now,
)
from app.services.settings_service import normalize_role
from app.services.storage.base import StorageProvider
from app.services.storage.storage_factory import get_storage

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".doc", ".docx"}

DOCUMENT_TYPES = {
    "EXPENSE_RECEIPT",
    "MEDICAL_BILL",
    "FOOD_BILL",
    "REQUEST_LETTER",
    "OVERTIME_PROOF",
    "WFH_SUPPORT",
    "OTHER",
}


def validate_attachment(file_name: str, content_type: str | None, file_bytes: bytes, document_type: str) -> None:
    ext = os.path.splitext(file_name or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"File type '{ext or 'unknown'}' is not allowed.")
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=422, detail=f"MIME type '{content_type or 'unknown'}' is not allowed.")
    if len(file_bytes) > settings.ATTACHMENT_MAX_FILE_SIZE_BYTES:
        mb = settings.ATTACHMENT_MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(status_code=422, detail=f"File size exceeds the {mb}MB limit.")
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid document_type '{document_type}'.")


def _attachment_query(db: Session, request_id: str, attachment_id: str):
    return db.query(RequestAttachment).filter(
        RequestAttachment.id == attachment_id,
        RequestAttachment.request_id == request_id,
        RequestAttachment.is_deleted.is_(False),
    )


def upload_attachment(
    db: Session,
    actor: Employee,
    request_id: str,
    file_name: str,
    content_type: str | None,
    file_bytes: bytes,
    document_type: str = "OTHER",
) -> RequestAttachment:
    request = get_request(db, request_id)
    ensure_read_access(db, actor, request)
    if request.status not in {"draft", "pending"}:
        raise HTTPException(status_code=400, detail="Attachments can only be added to draft or pending requests.")
    if actor.id != request.employee_id and not _can_pay_expenses(actor):
        raise HTTPException(status_code=403, detail="Not authorized to upload attachments for this request.")

    validate_attachment(file_name, content_type, file_bytes, document_type)
    attachment_count = db.query(RequestAttachment).filter(
        RequestAttachment.request_id == request.id,
        RequestAttachment.is_deleted.is_(False),
    ).count()
    if attachment_count >= settings.ATTACHMENT_MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Maximum of {settings.ATTACHMENT_MAX_FILES_PER_REQUEST} attachments per request.")

    today = date.today()
    prefix = str(uuid.uuid4()).replace("-", "")[:8]
    stored_file_name = StorageProvider.generate_safe_filename(file_name, prefix)
    folder_path = f"requests/{today.year}/{today.month:02d}/user_{request.employee_id}/request_{request.id}"
    upload_result = get_storage().upload_file(file_bytes, folder_path, stored_file_name)
    checksum = hashlib.sha256(file_bytes).hexdigest()
    attachment = RequestAttachment(
        request_id=request.id,
        uploaded_by_id=actor.id,
        original_file_name=file_name,
        stored_file_name=upload_result.stored_file_name,
        file_extension=os.path.splitext(file_name)[1].lower(),
        mime_type=content_type,
        file_size_bytes=len(file_bytes),
        checksum_sha256=checksum,
        storage_provider=settings.STORAGE_PROVIDER,
        storage_path=upload_result.storage_path,
        file_url=upload_result.file_url,
        document_type=document_type,
    )
    db.add(attachment)
    log_audit(
        db,
        actor,
        "request_attachment_uploaded",
        "employee_request",
        request.id,
        metadata={
            "original_file_name": file_name,
            "document_type": document_type,
            "file_size_bytes": len(file_bytes),
            "storage_provider": settings.STORAGE_PROVIDER,
        },
    )
    db.commit()
    db.refresh(attachment)
    return attachment


def list_attachments(db: Session, actor: Employee, request_id: str) -> list[RequestAttachment]:
    request = get_request(db, request_id)
    ensure_read_access(db, actor, request)
    return db.query(RequestAttachment).filter(
        RequestAttachment.request_id == request_id,
        RequestAttachment.is_deleted.is_(False),
    ).order_by(RequestAttachment.created_at.asc()).all()


def download_attachment(db: Session, actor: Employee, request_id: str, attachment_id: str) -> tuple[bytes, str, str]:
    attachment = _attachment_query(db, request_id, attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    request = get_request(db, request_id)
    try:
        ensure_read_access(db, actor, request)
    except HTTPException:
        log_audit(
            db,
            actor,
            "request_attachment_download_denied",
            "employee_request",
            request_id,
            metadata={"attachment_id": attachment_id, "attempted_by_role": normalize_role(actor.role)},
        )
        db.commit()
        raise
    try:
        file_bytes = get_storage().download_file(attachment.storage_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Attachment file not found.")
    log_audit(
        db,
        actor,
        "request_attachment_downloaded",
        "employee_request",
        request_id,
        metadata={
            "attachment_id": attachment_id,
            "document_type": attachment.document_type,
            "file_size_bytes": attachment.file_size_bytes,
        },
    )
    db.commit()
    return file_bytes, attachment.mime_type or "application/octet-stream", attachment.original_file_name


def delete_attachment(db: Session, actor: Employee, request_id: str, attachment_id: str) -> None:
    attachment = _attachment_query(db, request_id, attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    request = get_request(db, request_id)
    ensure_read_access(db, actor, request)
    if request.status not in {"draft", "pending"}:
        raise HTTPException(status_code=400, detail="Attachments cannot be deleted after a request is approved or rejected.")
    if attachment.uploaded_by_id != actor.id and not _can_pay_expenses(actor):
        raise HTTPException(status_code=403, detail="Not authorized to delete this attachment.")
    attachment.is_deleted = True
    attachment.deleted_at = utc_now()
    attachment.deleted_by_id = actor.id
    log_audit(
        db,
        actor,
        "request_attachment_deleted",
        "employee_request",
        request.id,
        metadata={
            "attachment_id": attachment.id,
            "original_file_name": attachment.original_file_name,
            "document_type": attachment.document_type,
        },
    )
    db.commit()


def serialize_attachment(db: Session, row: RequestAttachment) -> dict[str, Any]:
    uploader = find_employee(db, row.uploaded_by_id)
    return {
        "id": row.id,
        "request_id": row.request_id,
        "original_file_name": row.original_file_name,
        "file_extension": row.file_extension,
        "mime_type": row.mime_type,
        "file_size_bytes": row.file_size_bytes,
        "document_type": row.document_type,
        "storage_provider": row.storage_provider,
        "uploaded_by_name": employee_name(uploader),
        "created_at": row.created_at,
    }

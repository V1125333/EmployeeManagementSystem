"""Employee document browser endpoints."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.document_service import (
    download_document,
    list_documents,
    replace_document,
    serialize_document,
    upload_document,
)
from app.services.settings_service import get_current_employee


router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("")
async def employee_documents(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, x_user_id, x_user_email)
    return [serialize_document(row) for row in list_documents(db, actor)]


@router.post("")
async def create_employee_document(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, x_user_id, x_user_email)
    row = upload_document(db, actor, file.filename or "document", file.content_type, await file.read(), category)
    return serialize_document(row)


@router.put("/{document_id}")
async def update_employee_document(
    document_id: str,
    file: UploadFile = File(...),
    category: str | None = Form(None),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, x_user_id, x_user_email)
    row = replace_document(db, actor, document_id, file.filename or "document", file.content_type, await file.read(), category)
    return serialize_document(row)


@router.get("/{document_id}/download")
async def get_employee_document(
    document_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = get_current_employee(db, x_user_id, x_user_email)
    file_bytes, mime_type, file_name = download_document(db, actor, document_id)
    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}"},
    )


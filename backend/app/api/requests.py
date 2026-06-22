from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.requests import ApproveSchema, CancelSchema, CommentSchema, RejectSchema, RequestCreateSchema, RequestUpdateSchema
from app.services.requests_service import (
    add_comment,
    approve_request,
    cancel_request,
    create_request,
    delete_attachment,
    ensure_read_access,
    get_attachment,
    get_approval_queue,
    get_my_requests,
    get_request,
    get_types,
    mark_expense_paid,
    reject_request,
    serialize_attachment,
    serialize_comment,
    serialize_request,
    submit_request,
    update_request,
    upload_attachment,
)
from app.services.settings_service import get_current_employee

router = APIRouter(prefix="/requests", tags=["Requests"])


def actor_from_headers(db: Session, x_user_id: str | None, x_user_email: str | None):
    return get_current_employee(db, x_user_id, x_user_email)


@router.get("/types")
async def request_types():
    return get_types()


@router.post("")
async def create_employee_request(
    payload: RequestCreateSchema,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = create_request(db, actor, payload)
    return serialize_request(db, row, actor, include_detail=True)


@router.get("/my")
async def my_requests(
    status: str | None = Query(None),
    request_type: str | None = Query(None),
    search: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    return get_my_requests(db, actor, status=status, request_type=request_type, search=search, date_from=date_from, date_to=date_to, page=page, per_page=per_page)


@router.get("/queue")
async def approval_queue(
    status: str | None = Query("pending"),
    request_type: str | None = Query(None),
    search: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    return get_approval_queue(db, actor, status=status, request_type=request_type, search=search, date_from=date_from, date_to=date_to, page=page, per_page=per_page)


@router.get("/{request_id}")
async def request_detail(
    request_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = get_request(db, request_id)
    ensure_read_access(db, actor, row)
    return serialize_request(db, row, actor, include_detail=True)


@router.patch("/{request_id}")
async def update_employee_request(
    request_id: str,
    payload: RequestUpdateSchema,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = update_request(db, actor, request_id, payload)
    return serialize_request(db, row, actor, include_detail=True)


@router.post("/{request_id}/submit")
async def submit_employee_request(
    request_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = submit_request(db, actor, request_id)
    return serialize_request(db, row, actor, include_detail=True)


@router.post("/{request_id}/cancel")
async def cancel_employee_request(
    request_id: str,
    payload: CancelSchema,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = cancel_request(db, actor, request_id, payload.reason)
    return serialize_request(db, row, actor, include_detail=True)


@router.post("/{request_id}/approve")
async def approve_employee_request(
    request_id: str,
    payload: ApproveSchema,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = approve_request(db, actor, request_id, payload.notes)
    return serialize_request(db, row, actor, include_detail=True)


@router.post("/{request_id}/reject")
async def reject_employee_request(
    request_id: str,
    payload: RejectSchema,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = reject_request(db, actor, request_id, payload.reason)
    return serialize_request(db, row, actor, include_detail=True)


@router.post("/{request_id}/comments")
async def add_request_comment(
    request_id: str,
    payload: CommentSchema,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = add_comment(db, actor, request_id, payload)
    return serialize_comment(db, row)


@router.post("/{request_id}/attachments")
async def upload_request_attachment(
    request_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    content = await file.read()
    row = upload_attachment(
        db,
        actor,
        request_id,
        file.filename or "receipt",
        file.content_type,
        content,
    )
    return serialize_attachment(db, row)


@router.get("/{request_id}/attachments/{attachment_id}")
async def get_request_attachment(
    request_id: str,
    attachment_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = get_attachment(db, actor, attachment_id)
    if row.request_id != request_id:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return {
        "id": row.id,
        "file_name": row.file_name,
        "mime_type": row.mime_type,
        "data_uri": row.storage_path,
    }


@router.delete("/{request_id}/attachments/{attachment_id}")
async def delete_request_attachment(
    request_id: str,
    attachment_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = get_attachment(db, actor, attachment_id)
    if row.request_id != request_id:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    delete_attachment(db, actor, attachment_id)
    return {"success": True}


@router.post("/{request_id}/mark-paid")
async def mark_request_paid(
    request_id: str,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(None, alias="x-user-id"),
    x_user_email: str | None = Header(None, alias="x-user-email"),
):
    actor = actor_from_headers(db, x_user_id, x_user_email)
    row = mark_expense_paid(db, actor, request_id)
    return serialize_request(db, row, actor, include_detail=True)

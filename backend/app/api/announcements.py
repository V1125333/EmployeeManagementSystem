"""
Announcement API endpoints.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.employee import Employee
from app.models.operations import (
    Announcement,
    AnnouncementAcknowledgment,
    AnnouncementAudience,
    AnnouncementRead,
    ActionInboxItem,
    Notification,
)

router = APIRouter(prefix="/announcements", tags=["Announcements"])
logger = logging.getLogger(__name__)

CREATE_ROLES = {"super_admin", "admin", "hr_admin", "global_access"}


class AnnouncementPayload(BaseModel):
    title: str
    message: str
    announcement_type: str = "general"
    priority: str = "normal"
    audience_type: str = "everyone"
    target_values: list[str] = []
    status: str = "draft"
    is_pinned: bool = False
    requires_acknowledgment: bool = False
    publish_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


def normalize_role(role: str | None) -> str:
    return (role or "").strip().lower().replace(" ", "_")


def current_actor(
    db: Session,
    user_id: str | None,
    user_email: str | None,
    user_name: str | None,
):
    employee = None
    if user_id:
        employee = db.query(Employee).filter(Employee.id == user_id).first()
    if not employee and user_email:
        employee = db.query(Employee).filter(
            func.lower(Employee.work_email) == user_email.strip().lower()
        ).first()
    if employee and user_email and employee.work_email.lower() != user_email.lower():
        raise HTTPException(status_code=401, detail="Authenticated user headers do not match.")

    actor_id = employee.id if employee else user_id
    actor_role = normalize_role(employee.role if employee else None)
    actor_name = user_email or user_name or (employee.work_email if employee else None) or "unknown"
    return employee, actor_id, actor_role, actor_name


def ensure_can_manage(role: str):
    if role not in CREATE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to manage announcements")


def utc_now() -> datetime:
    """Return naive UTC to match the app's existing DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_datetime(value: datetime | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        if value.tzinfo is not None and value.utcoffset() is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.replace(tzinfo=None)
    except Exception as exc:
        logger.warning("Invalid announcement %s datetime %r: %s", field_name, value, exc)
        raise HTTPException(status_code=422, detail=f"Invalid {field_name} datetime")


def validate_payload(payload: AnnouncementPayload):
    title = payload.title.strip()
    message = payload.message.strip()
    status = payload.status.lower()
    audience_type = payload.audience_type.lower()

    if not title:
        raise HTTPException(status_code=422, detail="Announcement title is required")
    if not message:
        raise HTTPException(status_code=422, detail="Announcement message is required")
    if status not in {"draft", "published"}:
        raise HTTPException(status_code=422, detail="Status must be draft or published")
    if audience_type not in {"everyone", "department", "role", "employee"}:
        raise HTTPException(status_code=422, detail="Invalid audience type")
    if audience_type != "everyone" and not payload.target_values:
        raise HTTPException(status_code=422, detail="Audience target is required")

    publish_at = normalize_datetime(payload.publish_at, "publish_at")
    expires_at = normalize_datetime(payload.expires_at, "expires_at")
    if not publish_at and status == "published":
        publish_at = utc_now()
    if expires_at and publish_at and expires_at <= publish_at:
        raise HTTPException(status_code=422, detail="Expiry date must be after publish date")

    return title, message, status, audience_type, publish_at, expires_at


def announcement_message(announcement: Announcement) -> str:
    return announcement.message or announcement.description


def announcement_type(announcement: Announcement) -> str:
    return announcement.announcement_type or announcement.type or "general"


def is_active_for_employee(announcement: Announcement, now: datetime) -> bool:
    if announcement.status != "published":
        return False
    if announcement.publish_at and announcement.publish_at > now:
        return False
    if announcement.expires_at and announcement.expires_at <= now:
        return False
    return True


def serialize_announcement(
    announcement: Announcement,
    db: Session,
    employee: Employee | None = None,
    include_stats: bool = False,
):
    audiences = db.query(AnnouncementAudience).filter(
        AnnouncementAudience.announcement_id == announcement.id
    ).all()
    acknowledged = False
    read = False
    if employee:
        acknowledged = db.query(AnnouncementAcknowledgment).filter(
            AnnouncementAcknowledgment.announcement_id == announcement.id,
            AnnouncementAcknowledgment.employee_id == employee.id,
        ).first() is not None
        read = db.query(AnnouncementRead).filter(
            AnnouncementRead.announcement_id == announcement.id,
            AnnouncementRead.employee_id == employee.id,
        ).first() is not None

    data = {
        "id": announcement.id,
        "title": announcement.title,
        "message": announcement_message(announcement),
        "announcement_type": announcement_type(announcement),
        "priority": announcement.priority or "normal",
        "audience_type": announcement.audience_type or "everyone",
        "status": effective_status(announcement),
        "is_pinned": bool(announcement.is_pinned),
        "requires_acknowledgment": bool(announcement.requires_acknowledgment),
        "publish_at": announcement.publish_at.isoformat() if announcement.publish_at else None,
        "expires_at": announcement.expires_at.isoformat() if announcement.expires_at else None,
        "created_by": announcement.created_by or announcement.published_by or "unknown",
        "created_at": announcement.created_at.isoformat() if announcement.created_at else None,
        "updated_by": announcement.updated_by,
        "updated_at": announcement.updated_at.isoformat() if announcement.updated_at else None,
        "target_values": [aud.target_value for aud in audiences],
        "acknowledged": acknowledged,
        "read": read,
    }

    if include_stats:
        stats = acknowledgment_stats(announcement, db)
        data.update(stats)

    return data


def effective_status(announcement: Announcement) -> str:
    if announcement.status == "published" and announcement.expires_at and announcement.expires_at <= utc_now():
        return "expired"
    return announcement.status or "draft"


def visible_employee_query(announcement: Announcement, db: Session):
    query = db.query(Employee).filter(
        Employee.employment_status == "active",
        Employee.work_email != "superadmin@reknew.ai",
    )
    audience_type = announcement.audience_type or "everyone"
    audiences = db.query(AnnouncementAudience).filter(
        AnnouncementAudience.announcement_id == announcement.id
    ).all()
    targets = [aud.target_value for aud in audiences]

    if audience_type == "department":
        query = query.filter(Employee.department.in_(targets))
    elif audience_type == "role":
        query = query.filter(Employee.role.in_(targets))
    elif audience_type == "employee":
        query = query.filter(Employee.id.in_(targets))

    return query


def employee_can_see(announcement: Announcement, employee: Employee, db: Session) -> bool:
    if not is_active_for_employee(announcement, utc_now()):
        return False

    audience_type = announcement.audience_type or "everyone"
    if audience_type == "everyone":
        return True

    audiences = db.query(AnnouncementAudience).filter(
        AnnouncementAudience.announcement_id == announcement.id
    ).all()
    targets = {aud.target_value for aud in audiences}
    if audience_type == "department":
        return employee.department in targets
    if audience_type == "role":
        return employee.role in targets
    if audience_type == "employee":
        return employee.id in targets
    return False


def acknowledgment_stats(announcement: Announcement, db: Session):
    eligible_count = visible_employee_query(announcement, db).count()
    acknowledged_count = db.query(AnnouncementAcknowledgment).filter(
        AnnouncementAcknowledgment.announcement_id == announcement.id
    ).count()
    pending_count = max(eligible_count - acknowledged_count, 0)
    percentage = round((acknowledged_count / eligible_count) * 100) if eligible_count else 0
    return {
        "acknowledged_count": acknowledged_count,
        "pending_count": pending_count,
        "acknowledgment_percentage": percentage,
    }


def upsert_audiences(announcement_id: str, audience_type: str, targets: list[str], db: Session):
    db.query(AnnouncementAudience).filter(
        AnnouncementAudience.announcement_id == announcement_id
    ).delete()

    values = ["all"] if audience_type == "everyone" else targets
    target_type = "everyone" if audience_type == "everyone" else audience_type
    for value in values:
        db.add(AnnouncementAudience(
            announcement_id=announcement_id,
            target_type=target_type,
            target_value=value,
        ))


def create_notifications_for_published(announcement: Announcement, db: Session):
    if announcement.status != "published":
        return
    for employee in visible_employee_query(announcement, db).all():
        exists = db.query(Notification).filter(
            Notification.user_id == employee.id,
            Notification.type == "announcement",
            Notification.link_url == f"/announcements/{announcement.id}",
        ).first()
        if exists:
            continue
        db.add(Notification(
            user_id=employee.id,
            title=announcement.title,
            message=announcement_message(announcement)[:240],
            type="announcement",
            notification_type="announcement_published",
            related_entity_type="announcement",
            related_entity_id=announcement.id,
            link_url=f"/announcements/{announcement.id}",
        ))
        if announcement.requires_acknowledgment:
            inbox_exists = db.query(ActionInboxItem).filter(
                ActionInboxItem.assigned_to_user_id == employee.id,
                ActionInboxItem.related_entity_type == "announcement",
                ActionInboxItem.related_entity_id == announcement.id,
                ActionInboxItem.status == "pending",
            ).first()
            if not inbox_exists:
                db.add(ActionInboxItem(
                    assigned_to_user_id=employee.id,
                    item_type="announcement_acknowledgment",
                    title="Announcement acknowledgment required",
                    description=announcement.title,
                    status="pending",
                    priority=announcement.priority or "normal",
                    related_entity_type="announcement",
                    related_entity_id=announcement.id,
                ))


@router.post("")
async def create_announcement(
    payload: AnnouncementPayload,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    current_user_name: str = Header(None, alias="x-user-name"),
    db: Session = Depends(get_db),
):
    _, actor_id, actor_role, actor_name = current_actor(db, current_user_id, current_user_email, current_user_name)
    ensure_can_manage(actor_role)
    title, message, status, audience_type, publish_at, expires_at = validate_payload(payload)

    announcement = Announcement(
        title=title,
        description=message,
        type=payload.announcement_type,
        message=message,
        announcement_type=payload.announcement_type,
        priority=payload.priority,
        audience_type=audience_type,
        status=status,
        is_pinned=payload.is_pinned,
        requires_acknowledgment=payload.requires_acknowledgment,
        publish_at=publish_at,
        expires_at=expires_at,
        publish_date=(publish_at or utc_now()).date(),
        expiry_date=expires_at.date() if expires_at else None,
        created_by=actor_name,
        updated_by=actor_name,
        published_by=actor_id,
        is_active=status == "published",
    )
    db.add(announcement)
    db.flush()
    upsert_audiences(announcement.id, audience_type, payload.target_values, db)
    create_notifications_for_published(announcement, db)
    db.commit()
    db.refresh(announcement)
    return {"success": True, "announcement": serialize_announcement(announcement, db, include_stats=True)}


@router.get("/my")
async def my_announcements(
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    employee, _, _, _ = current_actor(db, current_user_id, current_user_email, None)
    if not employee:
        return {"announcements": []}

    announcements = db.query(Announcement).filter(
        Announcement.status == "published",
        or_(Announcement.expires_at.is_(None), Announcement.expires_at > utc_now()),
    ).order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).all()
    visible = [
        serialize_announcement(item, db, employee=employee)
        for item in announcements
        if employee_can_see(item, employee, db)
    ]
    return {"announcements": visible}


@router.get("")
async def list_announcements(
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    _, _, actor_role, _ = current_actor(db, current_user_id, current_user_email, None)
    ensure_can_manage(actor_role)

    announcements = db.query(Announcement).order_by(
        Announcement.is_pinned.desc(),
        Announcement.created_at.desc(),
    ).all()
    return {"announcements": [serialize_announcement(item, db, include_stats=True) for item in announcements]}


@router.put("/{announcement_id}")
async def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    current_user_name: str = Header(None, alias="x-user-name"),
    db: Session = Depends(get_db),
):
    _, actor_id, actor_role, actor_name = current_actor(db, current_user_id, current_user_email, current_user_name)
    ensure_can_manage(actor_role)

    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    title, message, status, audience_type, publish_at, expires_at = validate_payload(payload)
    announcement.title = title
    announcement.description = message
    announcement.message = message
    announcement.type = payload.announcement_type
    announcement.announcement_type = payload.announcement_type
    announcement.priority = payload.priority
    announcement.audience_type = audience_type
    announcement.status = status
    announcement.is_pinned = payload.is_pinned
    announcement.requires_acknowledgment = payload.requires_acknowledgment
    announcement.publish_at = publish_at
    announcement.expires_at = expires_at
    announcement.publish_date = (publish_at or utc_now()).date()
    announcement.expiry_date = expires_at.date() if expires_at else None
    announcement.updated_by = actor_name
    announcement.updated_at = utc_now()
    announcement.published_by = actor_id
    announcement.is_active = status == "published"
    upsert_audiences(announcement.id, audience_type, payload.target_values, db)
    create_notifications_for_published(announcement, db)
    db.commit()
    db.refresh(announcement)
    return {"success": True, "announcement": serialize_announcement(announcement, db, include_stats=True)}


@router.delete("/{announcement_id}")
async def delete_announcement(
    announcement_id: str,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    _, _, actor_role, _ = current_actor(db, current_user_id, current_user_email, None)
    ensure_can_manage(actor_role)
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    db.query(AnnouncementAudience).filter(AnnouncementAudience.announcement_id == announcement_id).delete()
    db.query(AnnouncementAcknowledgment).filter(AnnouncementAcknowledgment.announcement_id == announcement_id).delete()
    db.query(AnnouncementRead).filter(AnnouncementRead.announcement_id == announcement_id).delete()
    db.delete(announcement)
    db.commit()
    return {"success": True}


@router.post("/{announcement_id}/acknowledge")
async def acknowledge_announcement(
    announcement_id: str,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    employee, _, _, _ = current_actor(db, current_user_id, current_user_email, None)
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not employee or not announcement or not employee_can_see(announcement, employee, db):
        raise HTTPException(status_code=404, detail="Announcement not found")

    existing = db.query(AnnouncementAcknowledgment).filter(
        AnnouncementAcknowledgment.announcement_id == announcement_id,
        AnnouncementAcknowledgment.employee_id == employee.id,
    ).first()
    if not existing:
        db.add(AnnouncementAcknowledgment(
            announcement_id=announcement_id,
            employee_id=employee.id,
        ))
    db.query(ActionInboxItem).filter(
        ActionInboxItem.assigned_to_user_id == employee.id,
        ActionInboxItem.related_entity_type == "announcement",
        ActionInboxItem.related_entity_id == announcement_id,
        ActionInboxItem.status == "pending",
    ).update({"status": "completed", "updated_at": utc_now()})
    db.query(Notification).filter(
        Notification.user_id == employee.id,
        Notification.type == "announcement",
        Notification.link_url == f"/announcements/{announcement_id}",
    ).update({"is_read": True})
    db.commit()
    return {"success": True, "acknowledged_at": utc_now().isoformat()}


@router.post("/{announcement_id}/read")
async def mark_read(
    announcement_id: str,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    employee, _, _, _ = current_actor(db, current_user_id, current_user_email, None)
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not employee or not announcement or not employee_can_see(announcement, employee, db):
        raise HTTPException(status_code=404, detail="Announcement not found")
    existing = db.query(AnnouncementRead).filter(
        AnnouncementRead.announcement_id == announcement_id,
        AnnouncementRead.employee_id == employee.id,
    ).first()
    if not existing:
        db.add(AnnouncementRead(announcement_id=announcement_id, employee_id=employee.id))
    db.query(Notification).filter(
        Notification.user_id == employee.id,
        Notification.type == "announcement",
        Notification.link_url == f"/announcements/{announcement_id}",
    ).update({"is_read": True})
    db.commit()
    return {"success": True}


@router.get("/unread-count")
async def unread_count(
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    employee, _, _, _ = current_actor(db, current_user_id, current_user_email, None)
    if not employee:
        return {"count": 0}
    announcements = db.query(Announcement).filter(
        Announcement.status == "published",
        or_(Announcement.expires_at.is_(None), Announcement.expires_at > utc_now()),
    ).all()
    count = 0
    for announcement in announcements:
        if not employee_can_see(announcement, employee, db):
            continue
        if announcement.requires_acknowledgment:
            seen = db.query(AnnouncementAcknowledgment).filter(
                AnnouncementAcknowledgment.announcement_id == announcement.id,
                AnnouncementAcknowledgment.employee_id == employee.id,
            ).first()
        else:
            seen = db.query(AnnouncementRead).filter(
                AnnouncementRead.announcement_id == announcement.id,
                AnnouncementRead.employee_id == employee.id,
            ).first()
        if not seen:
            count += 1
    return {"count": count}


@router.get("/{announcement_id}/stats")
async def get_announcement_stats(
    announcement_id: str,
    current_user_id: str = Header(None, alias="x-user-id"),
    current_user_email: str = Header(None, alias="x-user-email"),
    db: Session = Depends(get_db),
):
    _, _, actor_role, _ = current_actor(db, current_user_id, current_user_email, None)
    ensure_can_manage(actor_role)
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return acknowledgment_stats(announcement, db)

"""
Support ticket API endpoints.
"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.settings import SupportTicketCreate, SupportTicketResponse
from app.services.settings_service import create_support_ticket, get_current_employee

router = APIRouter(prefix="/support-tickets", tags=["Support Tickets"])


@router.post("", response_model=SupportTicketResponse)
async def submit_support_ticket(
    payload: SupportTicketCreate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
):
    employee = get_current_employee(db, x_user_id, x_user_email)
    return create_support_ticket(db, employee, payload)

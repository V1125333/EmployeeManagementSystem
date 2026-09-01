"""
Support ticket API endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.authentication import AuthenticatedActor, get_authenticated_actor
from app.schemas.settings import SupportTicketCreate, SupportTicketResponse
from app.services.settings_service import create_support_ticket

router = APIRouter(prefix="/support-tickets", tags=["Support Tickets"])


@router.post("", response_model=SupportTicketResponse)
async def submit_support_ticket(
    payload: SupportTicketCreate,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    return create_support_ticket(db, actor.employee, payload)

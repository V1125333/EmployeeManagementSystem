"""
Employee API endpoints.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.employee import AddEmployeeRequest, AddEmployeeResponse
from app.services.employee_service import create_employee

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.post("/", response_model=AddEmployeeResponse)
async def add_employee(data: AddEmployeeRequest, db: Session = Depends(get_db)):
    """Add a new employee with setup code for first-time login."""
    try:
        result = create_employee(db, data)
        return result
    except Exception as e:
        logger.error(f"Error adding employee: {e}")
        raise HTTPException(status_code=500, detail=str(e))

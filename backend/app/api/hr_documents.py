"""
HR document generation API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.authentication import AuthenticatedActor, get_authenticated_actor
from app.schemas.hr_document import InternshipCompletionLetterRequest
from app.services.settings_service import is_admin_role
from app.services.security_service import log_sensitive_access
from app.services.hr_document_service import (
    build_internship_completion_filename,
    generate_internship_completion_docx,
    generate_internship_completion_pdf,
)

router = APIRouter(prefix="/hr-documents", tags=["HR Documents"])


@router.post("/internship-completion")
async def generate_internship_completion_letter(
    request: InternshipCompletionLetterRequest,
    format: str = Query(default="pdf", pattern="^(pdf|docx)$"),
    db: Session = Depends(get_db),
    authenticated_actor: AuthenticatedActor = Depends(get_authenticated_actor),
):
    actor = authenticated_actor.employee
    if not is_admin_role(actor.role):
        raise HTTPException(status_code=403, detail="Admin access is required.")
    if format == "pdf":
        content = generate_internship_completion_pdf(request)
        media_type = "application/pdf"
    elif format == "docx":
        content = generate_internship_completion_docx(request)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        raise HTTPException(status_code=400, detail="Unsupported document format.")

    filename = build_internship_completion_filename(request.intern_name, format)
    log_sensitive_access(
        db,
        actor,
        action="hr_document_generated",
        target_type="hr_document",
        target_id=None,
        sensitivity_level="confidential",
        reason=f"Generated internship completion letter for {request.intern_name}",
        metadata={"format": format, "document": "internship_completion"},
    )
    db.commit()
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

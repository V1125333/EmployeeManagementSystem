"""
HR document generation API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.schemas.hr_document import InternshipCompletionLetterRequest
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
):
    if format == "pdf":
        content = generate_internship_completion_pdf(request)
        media_type = "application/pdf"
    elif format == "docx":
        content = generate_internship_completion_docx(request)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        raise HTTPException(status_code=400, detail="Unsupported document format.")

    filename = build_internship_completion_filename(request.intern_name, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

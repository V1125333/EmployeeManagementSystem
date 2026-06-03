"""
Certificate generation API endpoints.
"""

import io
import zipfile

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.schemas.certificate import (
    BulkCertificateGenerateRequest,
    CERT_TYPES,
    CertificateGenerateRequest,
    CertificateMetaResponse,
    NextSerialResponse,
)
from app.services.certificate_service import (
    build_filename,
    certificate_id,
    consume_next_serial,
    generate_certificate_pdf,
    get_certificate_verification,
    list_counters,
    peek_next_serial,
    record_issued_certificate,
    validate_certificate_type,
)

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.get("/meta", response_model=CertificateMetaResponse)
async def certificate_meta():
    return {
        "certificate_types": CERT_TYPES,
        "counters": list_counters(),
    }


@router.get("/next-serial", response_model=NextSerialResponse)
async def next_serial(
    certificate_type: str = Query(...),
    cohort_code: str = Query("C1"),
    year: int = Query(..., ge=2020, le=2099),
):
    try:
        validate_certificate_type(certificate_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    serial_number = peek_next_serial(certificate_type, cohort_code, year)
    return {
        "next_serial": serial_number,
        "certificate_id": certificate_id(cohort_code, year, serial_number),
    }


@router.post("/generate")
async def generate_certificate(request: CertificateGenerateRequest):
    try:
        validate_certificate_type(request.certificate_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    serial_number = None
    cert_id = ""
    if request.include_certificate_number:
        serial_number = consume_next_serial(
            request.certificate_type,
            request.cohort_code,
            request.year,
        )
        cert_id = certificate_id(request.cohort_code, request.year, serial_number)
    pdf = generate_certificate_pdf(request, serial_number)
    if request.include_certificate_number and serial_number is not None:
        record_issued_certificate(request, serial_number, cert_id)
    filename = build_filename(
        request.first_name,
        request.surname,
        request.certificate_type,
    )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Certificate-Id": cert_id,
            "X-Certificate-Serial": str(serial_number or ""),
        },
    )


@router.post("/bulk-generate")
async def bulk_generate_certificates(request: BulkCertificateGenerateRequest):
    zip_buffer = io.BytesIO()
    issued_ids: list[str] = []

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, record in enumerate(request.records, start=1):
            try:
                validate_certificate_type(record.certificate_type)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Row {index}: {exc}")

            serial_number = None
            cert_id = ""
            if record.include_certificate_number:
                serial_number = consume_next_serial(
                    record.certificate_type,
                    record.cohort_code,
                    record.year,
                )
                cert_id = certificate_id(record.cohort_code, record.year, serial_number)

            pdf = generate_certificate_pdf(record, serial_number)
            if record.include_certificate_number and serial_number is not None:
                record_issued_certificate(record, serial_number, cert_id)
                issued_ids.append(cert_id)

            zf.writestr(
                build_filename(record.first_name, record.surname, record.certificate_type),
                pdf,
            )

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="ReKnew_Certificates.zip"',
            "X-Certificate-Ids": ",".join(issued_ids),
        },
    )


@router.get("/verify/{cert_id}")
async def verify_certificate(cert_id: str):
    record = get_certificate_verification(cert_id)
    if not record:
        return {
            "valid": False,
            "certificate_id": cert_id,
            "status": "not_found",
            "message": "Certificate not found in ReKnew records.",
        }
    return {
        "valid": record.get("status") == "valid",
        **record,
    }

"""
Certificate generation API endpoints.
"""

import io
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.certificate import Certificate, CertificateAuditLog
from app.models.employee import Employee
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
    list_legacy_issued_certificates,
    list_counters,
    peek_next_serial,
    record_issued_certificate,
    validate_certificate_type,
    certificate_verify_url,
)
from app.services.settings_service import get_current_employee, is_admin_role
from app.services.audit_service import log_audit

router = APIRouter(prefix="/certificates", tags=["Certificates"])


def require_certificate_admin(db: Session, user_id: str | None, user_email: str | None):
    user = get_current_employee(db, user_id, user_email)
    if not is_admin_role(user.role):
        raise HTTPException(status_code=403, detail="Only Super Admin/Admin can manage certificates.")
    return user


def safe_certificate(record: Certificate) -> dict:
    return {
        "certificate_code": record.certificate_code,
        "learner_name": record.learner_name,
        "course_name": record.course_name,
        "start_date": record.start_date.isoformat(),
        "end_date": record.end_date.isoformat(),
        "issue_date": record.issue_date.isoformat(),
        "status": record.status,
        "verification_url": record.verification_url,
        "pdf_url": record.pdf_url,
        "issued_by": record.issued_by or "ReKnew",
    }


def save_certificate_record(db: Session, request: CertificateGenerateRequest, cert_id: str, actor: Employee | None, filename: str) -> None:
    existing = db.query(Certificate).filter(Certificate.certificate_code == cert_id).first()
    old_values = safe_certificate(existing) if existing else None
    record = existing or Certificate(certificate_code=cert_id)
    record.learner_name = f"{request.first_name.strip()} {request.surname.strip()}"
    record.course_name = request.certificate_type
    record.start_date = request.start_date
    record.end_date = request.end_date
    record.issue_date = request.issued_date
    record.status = "valid"
    record.verification_url = certificate_verify_url(cert_id)
    record.pdf_url = filename
    record.issued_by = "ReKnew"
    if not existing:
        db.add(record)
    db.add(CertificateAuditLog(certificate_code=cert_id, action="issued", performed_by=actor.id if actor else None))
    log_audit(
        db,
        actor,
        action="certificate.issued" if not existing else "certificate.regenerated",
        entity_type="certificate",
        entity_id=cert_id,
        old_values=old_values,
        new_values=safe_certificate(record),
        metadata={"filename": filename},
        source="admin",
    )
    db.commit()


def sync_legacy_certificates(db: Session) -> None:
    changed = False
    for cert_id, legacy in list_legacy_issued_certificates().items():
        if db.query(Certificate).filter(Certificate.certificate_code == cert_id).first():
            continue
        try:
            record = Certificate(
                certificate_code=cert_id,
                learner_name=legacy.get("recipient_name") or "Unknown Learner",
                course_name=legacy.get("certificate_type") or "Unknown Course",
                start_date=date.fromisoformat(legacy.get("start_date")),
                end_date=date.fromisoformat(legacy.get("end_date")),
                issue_date=date.fromisoformat(legacy.get("issued_date")),
                status=legacy.get("status") or "valid",
                verification_url=certificate_verify_url(cert_id),
                pdf_url=legacy.get("pdf_url"),
                issued_by="ReKnew",
            )
        except (TypeError, ValueError):
            continue
        db.add(record)
        db.add(CertificateAuditLog(certificate_code=cert_id, action="legacy_import", reason="Imported from legacy JSON registry."))
        log_audit(
            db,
            None,
            action="certificate.legacy_imported",
            entity_type="certificate",
            entity_id=cert_id,
            new_values=safe_certificate(record),
            reason="Imported from legacy JSON registry.",
            source="system",
        )
        changed = True
    if changed:
        db.commit()


def request_from_certificate(record: Certificate) -> CertificateGenerateRequest:
    parts = record.learner_name.strip().split()
    first_name = parts[0] if parts else record.learner_name
    surname = " ".join(parts[1:]) if len(parts) > 1 else " "
    code_parts = record.certificate_code.split("-")
    cohort_code = code_parts[1] if len(code_parts) >= 4 else "CL"
    year = int(code_parts[2]) if len(code_parts) >= 4 and code_parts[2].isdigit() else record.issue_date.year
    return CertificateGenerateRequest(
        first_name=first_name,
        surname=surname,
        certificate_type=record.course_name,
        start_date=record.start_date,
        end_date=record.end_date,
        cohort_code=cohort_code,
        year=year,
        issued_date=record.issue_date,
        include_certificate_number=True,
    )


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
async def generate_certificate(request: CertificateGenerateRequest, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_certificate_admin(db, x_user_id, x_user_email)
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
    filename = build_filename(
        request.first_name,
        request.surname,
        request.certificate_type,
    )
    if request.include_certificate_number and serial_number is not None:
        record_issued_certificate(request, serial_number, cert_id)
        save_certificate_record(db, request, cert_id, actor, filename)

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
async def bulk_generate_certificates(request: BulkCertificateGenerateRequest, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_certificate_admin(db, x_user_id, x_user_email)
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
                save_certificate_record(db, record, cert_id, actor, build_filename(record.first_name, record.surname, record.certificate_type))
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


@router.get("")
async def list_certificates(db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    require_certificate_admin(db, x_user_id, x_user_email)
    sync_legacy_certificates(db)
    rows = db.query(Certificate).order_by(Certificate.created_at.desc()).limit(200).all()
    return {"certificates": [safe_certificate(row) for row in rows]}


@router.post("/{cert_id}/revoke")
async def revoke_certificate(cert_id: str, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_certificate_admin(db, x_user_id, x_user_email)
    record = db.query(Certificate).filter(Certificate.certificate_code == cert_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Certificate not found")
    old_values = safe_certificate(record)
    record.status = "revoked"
    db.add(CertificateAuditLog(certificate_code=cert_id, action="revoked", performed_by=actor.id))
    log_audit(
        db,
        actor,
        action="certificate.revoked",
        entity_type="certificate",
        entity_id=cert_id,
        old_values=old_values,
        new_values=safe_certificate(record),
        reason="Certificate revoked by administrator.",
        source="admin",
    )
    db.commit()
    return safe_certificate(record)


@router.get("/{cert_id}/download")
async def download_certificate(cert_id: str, db: Session = Depends(get_db), x_user_id: str | None = Header(None, alias="x-user-id"), x_user_email: str | None = Header(None, alias="x-user-email")):
    actor = require_certificate_admin(db, x_user_id, x_user_email)
    record = db.query(Certificate).filter(Certificate.certificate_code == cert_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Certificate not found")
    serial_number = int(record.certificate_code.split("-")[-1])
    log_audit(
        db,
        actor,
        action="certificate.downloaded",
        entity_type="certificate",
        entity_id=cert_id,
        metadata={"sensitive": False},
        source="admin",
    )
    db.commit()
    pdf = generate_certificate_pdf(request_from_certificate(record), serial_number)
    filename = record.pdf_url or f"{record.certificate_code}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/verify/{cert_id}")
async def verify_certificate(cert_id: str, db: Session = Depends(get_db)):
    db_record = db.query(Certificate).filter(Certificate.certificate_code == cert_id).first()
    if db_record:
        log_audit(
            db,
            None,
            action="certificate.verified",
            entity_type="certificate",
            entity_id=cert_id,
            metadata={"status": db_record.status},
            source="api",
        )
        db.commit()
        return {
            "valid": db_record.status == "valid",
            **safe_certificate(db_record),
        }
    record = get_certificate_verification(cert_id)
    if not record:
        log_audit(
            db,
            None,
            action="certificate.verify_not_found",
            entity_type="certificate",
            entity_id=cert_id,
            metadata={"security_event": False},
            source="api",
        )
        db.commit()
        return {
            "valid": False,
            "certificate_code": cert_id,
            "status": "not_found",
            "message": "Certificate not found in ReKnew records.",
        }
    log_audit(
        db,
        None,
        action="certificate.legacy_verified",
        entity_type="certificate",
        entity_id=cert_id,
        metadata={"status": record.get("status", "valid")},
        source="api",
    )
    db.commit()
    return {
        "valid": record.get("status") == "valid",
        "certificate_code": record.get("certificate_id", cert_id),
        "learner_name": record.get("recipient_name"),
        "course_name": record.get("certificate_type"),
        "start_date": record.get("start_date"),
        "end_date": record.get("end_date"),
        "issue_date": record.get("issued_date"),
        "status": record.get("status", "valid"),
        "verification_url": certificate_verify_url(cert_id),
        "pdf_url": record.get("pdf_url"),
        "issued_by": "ReKnew",
    }

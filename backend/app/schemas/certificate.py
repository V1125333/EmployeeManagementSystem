"""
Certificate generation schemas.
"""

from datetime import date
from pydantic import BaseModel, Field, model_validator


CERT_TYPES = [
    "Agentic Commerce",
    "ReKnew AI Cloud Practitioner",
    "ReKnew AI Cloud Architect",
    "ReKnew AI Foundational Engineer",
    "ReKnew Context Engineer",
    "ReKnew Context Architect",
    "ReKnew Snowflake AI Practitioner",
    "ReKnew DataBricks AI Practitioner",
]


class CertificateGenerateRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=80)
    surname: str = Field(..., min_length=1, max_length=80)
    certificate_type: str
    start_date: date
    end_date: date
    cohort_code: str = Field(default="C1", min_length=1, max_length=12)
    year: int = Field(..., ge=2020, le=2099)
    issued_date: date
    include_certificate_number: bool = True

    @model_validator(mode="after")
    def validate_programme_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End Date must be on or after Start Date")
        return self


class BulkCertificateGenerateRequest(BaseModel):
    records: list[CertificateGenerateRequest] = Field(..., min_length=1, max_length=500)


class CertificateCounter(BaseModel):
    certificate_type: str
    cohort_code: str
    year: int
    last_issued: int


class CertificateMetaResponse(BaseModel):
    certificate_types: list[str]
    counters: list[CertificateCounter]


class NextSerialResponse(BaseModel):
    certificate_id: str
    next_serial: int

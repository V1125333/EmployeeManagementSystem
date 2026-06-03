"""
HR document generation schemas.
"""

from datetime import date

from pydantic import BaseModel, Field, model_validator


class InternshipCompletionLetterRequest(BaseModel):
    intern_name: str = Field(..., min_length=1, max_length=140)
    programme: str = Field(default="Agentic Commerce", min_length=1, max_length=140)
    start_date: date
    end_date: date
    issued_date: date
    responsibility_summary: str = Field(..., min_length=1, max_length=900)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End Date must be on or after Start Date")
        return self

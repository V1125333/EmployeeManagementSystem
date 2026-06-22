from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator


class WFHData(BaseModel):
    from_date: date
    to_date: date
    reason: str = Field(..., min_length=1, max_length=500)
    note: str | None = Field(default=None, max_length=500)


class ShortPermissionData(BaseModel):
    date: date
    start_time: time
    end_time: time
    reason: str = Field(..., min_length=1, max_length=500)


class OvertimeData(BaseModel):
    date: date
    start_time: time
    end_time: time
    project_id: str | None = Field(default=None, max_length=36)
    reason: str = Field(..., min_length=1, max_length=500)


class ExpenseData(BaseModel):
    date: date
    category: str = Field(..., min_length=1, max_length=80)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=10)
    description: str = Field(..., min_length=1, max_length=500)


class RequestCreateSchema(BaseModel):
    request_type: str = Field(..., pattern="^(wfh|short_permission|overtime|expense)$")
    wfh: WFHData | None = None
    short_permission: ShortPermissionData | None = None
    overtime: OvertimeData | None = None
    expense: ExpenseData | None = None
    submit_immediately: bool = True

    @model_validator(mode="after")
    def require_matching_payload(self):
        if self.request_type == "wfh" and self.wfh is None:
            raise ValueError("WFH request data is required.")
        if self.request_type == "short_permission" and self.short_permission is None:
            raise ValueError("Short permission request data is required.")
        if self.request_type == "overtime" and self.overtime is None:
            raise ValueError("Overtime request data is required.")
        if self.request_type == "expense" and self.expense is None:
            raise ValueError("Expense request data is required.")
        return self


class RequestUpdateSchema(BaseModel):
    wfh: WFHData | None = None
    short_permission: ShortPermissionData | None = None
    overtime: OvertimeData | None = None
    expense: ExpenseData | None = None


class ApproveSchema(BaseModel):
    notes: str | None = Field(default=None, max_length=500)


class RejectSchema(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class CancelSchema(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class CommentSchema(BaseModel):
    body: str = Field(..., min_length=1, max_length=1000)
    is_internal: bool = False


class AttachmentOut(BaseModel):
    id: str
    file_name: str
    file_size_bytes: int | None
    mime_type: str | None
    uploaded_by_name: str
    created_at: datetime

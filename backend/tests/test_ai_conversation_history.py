from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import ai as ai_api
from app.api.ai import router
from app.core.authentication import create_access_token
from app.core.database import Base, get_db
from app.models.ai_workflow import (
    AIConversation,
    AIConversationMessage,
    AILeaveRequestDraft,
)
from app.models.employee import Employee
from app.models.leave_attendance import LeaveType
from app.models.organization import Department, Designation
from app.services.ai_conversation_service import append_message


@pytest.fixture()
def history_context(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Department.__table__,
            Designation.__table__,
            Employee.__table__,
            LeaveType.__table__,
            AIConversation.__table__,
            AIConversationMessage.__table__,
            AILeaveRequestDraft.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    first = Employee(
        id="history-owner-1",
        first_name="Asha",
        last_name="Rao",
        work_email="asha.history@example.com",
        phone="1000000000",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        joining_date=date(2024, 1, 1),
    )
    second = Employee(
        id="history-owner-2",
        first_name="Noah",
        last_name="Kim",
        work_email="noah.history@example.com",
        phone="2000000000",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        joining_date=date(2024, 1, 1),
    )
    leave_type = LeaveType(
        id="history-cl",
        name="Casual Leave",
        code="CL",
        default_days_per_year=12,
        is_active=True,
    )
    db.add_all([first, second, leave_type])
    db.commit()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(ai_api, "_audit_lifecycle", lambda *args, **kwargs: None)
    monkeypatch.setattr(ai_api, "_audit", lambda *args, **kwargs: None)
    client = TestClient(app)
    headers = {
        first.id: {"Authorization": f"Bearer {create_access_token(first)}"},
        second.id: {"Authorization": f"Bearer {create_access_token(second)}"},
    }
    yield {
        "client": client,
        "db": db,
        "first": first,
        "second": second,
        "headers": headers,
        "leave_type": leave_type,
    }
    db.close()


def _new(context, employee_id="history-owner-1"):
    response = context["client"].post(
        "/api/v1/ai/conversations",
        headers=context["headers"][employee_id],
        json={},
    )
    assert response.status_code == 200
    return response.json()


def test_back_to_briefing_closes_but_preserves_history(history_context):
    created = _new(history_context)
    row = history_context["db"].get(AIConversation, created["id"])
    append_message(
        history_context["db"], row, role="user", content="Check my leave balance"
    )

    closed = history_context["client"].post(
        f"/api/v1/ai/conversations/{created['id']}/close",
        headers=history_context["headers"]["history-owner-1"],
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    detail = history_context["client"].get(
        f"/api/v1/ai/conversations/{created['id']}",
        headers=history_context["headers"]["history-owner-1"],
    )
    assert detail.status_code == 200
    assert detail.json()["messages"][0]["content"] == "Check my leave balance"
    assert detail.json()["messages"][0]["historical"] is True


def test_new_conversation_ids_are_unique(history_context):
    first = _new(history_context)
    second = _new(history_context)
    assert first["id"] != second["id"]
    assert len(first["id"]) == 36


def test_conversations_are_isolated_by_authenticated_principal(history_context):
    created = _new(history_context)
    hidden = history_context["client"].get(
        f"/api/v1/ai/conversations/{created['id']}",
        headers=history_context["headers"]["history-owner-2"],
    )
    assert hidden.status_code == 404
    history = history_context["client"].get(
        "/api/v1/ai/conversations",
        headers=history_context["headers"]["history-owner-2"],
    )
    assert history.json()["conversations"] == []


def test_owner_fields_are_rejected(history_context):
    response = history_context["client"].post(
        "/api/v1/ai/conversations",
        headers=history_context["headers"]["history-owner-1"],
        json={"owner_employee_id": "history-owner-2"},
    )
    assert response.status_code == 422


def test_archive_is_retrievable_and_restore_reopens(history_context):
    created = _new(history_context)
    archived = history_context["client"].post(
        f"/api/v1/ai/conversations/{created['id']}/archive",
        headers=history_context["headers"]["history-owner-1"],
    )
    assert archived.json()["status"] == "archived"
    detail = history_context["client"].get(
        f"/api/v1/ai/conversations/{created['id']}",
        headers=history_context["headers"]["history-owner-1"],
    )
    assert detail.status_code == 200
    restored = history_context["client"].post(
        f"/api/v1/ai/conversations/{created['id']}/restore",
        headers=history_context["headers"]["history-owner-1"],
    )
    assert restored.status_code == 200
    assert restored.json()["conversation"]["status"] == "active"


def test_deleted_conversation_is_not_retrievable(history_context):
    created = _new(history_context)
    deleted = history_context["client"].delete(
        f"/api/v1/ai/conversations/{created['id']}",
        headers=history_context["headers"]["history-owner-1"],
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    detail = history_context["client"].get(
        f"/api/v1/ai/conversations/{created['id']}",
        headers=history_context["headers"]["history-owner-1"],
    )
    assert detail.status_code == 404


def _draft(context, conversation_id: str, status: str, expires_at: datetime):
    row = AILeaveRequestDraft(
        id=f"draft-{status}",
        owner_employee_id="history-owner-1",
        leave_type_id=context["leave_type"].id,
        leave_type_code="CL",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 1),
        reason="Family event",
        eligibility_snapshot="{}",
        working_day_count=1,
        balance_source="stored_balance",
        blocking_reasons="[]",
        warnings="[]",
        status=status,
        version=1,
        payload_hash="a" * 64,
        correlation_id="history-test",
        conversation_id=conversation_id,
        expires_at=expires_at,
    )
    context["db"].add(row)
    conversation = context["db"].get(AIConversation, conversation_id)
    conversation.workflow_kind = "leave_request_draft"
    conversation.workflow_reference_id = row.id
    conversation.workflow_status = status
    context["db"].commit()


def test_restored_expired_draft_is_marked_expired(history_context):
    created = _new(history_context)
    _draft(
        history_context,
        created["id"],
        "ready_for_confirmation",
        datetime.utcnow() - timedelta(minutes=1),
    )
    detail = history_context["client"].get(
        f"/api/v1/ai/conversations/{created['id']}",
        headers=history_context["headers"]["history-owner-1"],
    )
    assert detail.status_code == 200
    assert detail.json()["workflow"]["display_status"] == "expired"
    assert history_context["db"].get(
        AILeaveRequestDraft, "draft-ready_for_confirmation"
    ).status == "expired"


def test_restored_submitted_draft_is_shown_completed(history_context):
    created = _new(history_context)
    _draft(
        history_context,
        created["id"],
        "submitted",
        datetime.utcnow() + timedelta(hours=1),
    )
    detail = history_context["client"].get(
        f"/api/v1/ai/conversations/{created['id']}",
        headers=history_context["headers"]["history-owner-1"],
    )
    assert detail.status_code == 200
    assert detail.json()["workflow"]["display_status"] == "completed"
    assert detail.json()["facts_require_refresh"] is True

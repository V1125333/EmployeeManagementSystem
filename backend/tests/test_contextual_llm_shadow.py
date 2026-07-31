from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.context_builder import build_context_package
from app.ai.contextual_schemas import (
    ContextualInterpretation,
    LLMProviderRequest,
    LLMProviderResponse,
    TokenUsage,
)
from app.ai.prompt_templates import (
    MAX_FEW_SHOT_ESTIMATED_TOKENS,
    build_contextual_system_prompt,
    estimated_tokens,
    load_prompt_template,
    render_few_shot_examples,
)
from app.ai.providers.base import (
    ProviderBadRequestError,
    ProviderInvalidOutputError,
    parse_structured_interpretation,
)
from app.ai.providers.openai_provider import OpenAILLMProvider
from app.ai.providers import openai_provider as openai_provider_module
from app.ai.providers.openai_provider import _status_error
from app.api import ai as ai_api
from app.api.ai import router
from app.core.authentication import (
    AuthenticatedPrincipal,
    create_access_token,
)
from app.core.config import (
    contextual_provider_configuration_errors,
    settings,
)
from app.core.database import Base, get_db
from app.models.ai_workflow import (
    AIContextualShadowEvaluation,
    AIConversation,
    AIConversationMessage,
    AILeaveIntakeState,
    AILeaveRequestDraft,
)
from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday
from app.models.organization import Department, Designation
from app.schemas.ai import AIChatResponse, AIMessage
from app.services.contextual_shadow_service import (
    contextual_provider_status,
    run_shadow_evaluation,
    shadow_diagnostics,
)


def interpretation(
    *,
    goal="prepare_leave_request",
    workflow_action="continue",
    fields=None,
    capabilities=None,
    ambiguous=False,
):
    return ContextualInterpretation.model_validate(
        {
            "schema_version": "1.0",
            "domain": "leave",
            "goal": goal,
            "workflow_action": workflow_action,
            "extracted_fields": fields or {},
            "field_confidence": [],
            "ambiguity": {
                "is_ambiguous": ambiguous,
                "fields": ["workflow_action"] if ambiguous else [],
                "safe_options": [],
                "explanation": "The requested change is unclear." if ambiguous else None,
            },
            "clarification_requirement": {
                "required": ambiguous,
                "field": "workflow_action" if ambiguous else None,
                "question": "What would you like to change?" if ambiguous else None,
            },
            "proposed_capabilities": capabilities or [],
            "confirmation_requirement": {"required": False, "reason": "none"},
            "response_intent": (
                "ask_clarification" if ambiguous else "show_review"
            ),
        }
    )


class MockProvider:
    name = "mock"
    model = "mock-context-v1"

    def __init__(self, result):
        self.result = result
        self.calls = []

    async def interpret(self, request):
        self.calls.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return LLMProviderResponse(
            interpretation=self.result,
            provider=self.name,
            model=self.model,
            latency_ms=7,
            token_usage=TokenUsage(input_tokens=120, output_tokens=80),
        )


class SlowProvider(MockProvider):
    async def interpret(self, request):
        self.calls.append(request)
        await asyncio.sleep(0.35)
        return await super().interpret(request)


@pytest.fixture()
def shadow_context(monkeypatch):
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
            LeaveBalance.__table__,
            LeaveRequest.__table__,
            CompanyHoliday.__table__,
            AILeaveRequestDraft.__table__,
            AILeaveIntakeState.__table__,
            AIConversation.__table__,
            AIConversationMessage.__table__,
            AIContextualShadowEvaluation.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    manager = Employee(
        id="shadow-manager",
        first_name="David",
        last_name="Park",
        work_email="shadow.manager@example.com",
        phone="2000000000",
        workforce_type="full_time",
        role="manager",
        employment_status="active",
        is_active=True,
        joining_date=date(2024, 1, 1),
    )
    employee = Employee(
        id="shadow-employee",
        first_name="Asha",
        last_name="Rao",
        work_email="shadow.employee@example.com",
        phone="1000000000",
        workforce_type="full_time",
        role="super_admin",
        employment_status="active",
        is_active=True,
        joining_date=date(2025, 1, 1),
        manager_id=manager.id,
        work_country="USA",
    )
    other = Employee(
        id="shadow-other",
        first_name="Other",
        last_name="Employee",
        work_email="shadow.other@example.com",
        phone="3000000000",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        is_active=True,
        joining_date=date(2025, 1, 1),
        manager_id=manager.id,
        work_country="USA",
    )
    casual = LeaveType(
        id="shadow-cl",
        name="Casual Leave",
        code="CL",
        default_days_per_year=12,
        is_paid=True,
        is_active=True,
        sort_order=1,
    )
    db.add_all([manager, employee, other, casual])
    db.flush()
    db.add(
        LeaveBalance(
            id="shadow-balance",
            employee_id=employee.id,
            leave_type_id=casual.id,
            year=date.today().year,
            total_days=12,
            used_days=0,
            carry_forward_days=0,
        )
    )
    conversation = AIConversation(
        id="shadow-conversation",
        owner_employee_id=employee.id,
        title="New",
        domain="leave",
        status="active",
        retention_expires_at=datetime.utcnow() + timedelta(days=30),
    )
    db.add(conversation)
    db.commit()
    principal = AuthenticatedPrincipal(
        employee_id=employee.id,
        email=employee.work_email,
        role="super_admin",
        status="active",
        permissions=frozenset(
            {
                "leave.balance.read.self",
                "leave.request.read.self",
                "leave.assess.self",
                "leave.request.prepare.self",
            }
        ),
        token_id="shadow-token-id",
    )
    old = {
        "enabled": settings.CONTEXTUAL_LLM_ENABLED,
        "shadow": settings.CONTEXTUAL_LLM_SHADOW_MODE,
        "timeout": settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS,
        "retry": settings.CONTEXTUAL_LLM_RETRY_COUNT,
        "provider": settings.CONTEXTUAL_LLM_PROVIDER,
        "model": settings.CONTEXTUAL_LLM_MODEL,
        "provider_key": settings.CONTEXTUAL_LLM_API_KEY,
        "secret": settings.AUTH_JWT_SECRET,
        "env": settings.APP_ENV,
    }
    settings.CONTEXTUAL_LLM_ENABLED = True
    settings.CONTEXTUAL_LLM_SHADOW_MODE = True
    settings.CONTEXTUAL_LLM_PROVIDER = "openai"
    settings.CONTEXTUAL_LLM_MODEL = "test-model"
    settings.CONTEXTUAL_LLM_API_KEY = "server-only-test-key"
    settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS = 0.25
    settings.CONTEXTUAL_LLM_RETRY_COUNT = 0
    settings.AUTH_JWT_SECRET = "shadow-mode-test-secret-that-is-long-enough"
    settings.APP_ENV = "test"
    yield {
        "db": db,
        "engine": engine,
        "Session": Session,
        "employee": employee,
        "other": other,
        "principal": principal,
        "conversation": conversation,
    }
    settings.CONTEXTUAL_LLM_ENABLED = old["enabled"]
    settings.CONTEXTUAL_LLM_SHADOW_MODE = old["shadow"]
    settings.CONTEXTUAL_LLM_TIMEOUT_SECONDS = old["timeout"]
    settings.CONTEXTUAL_LLM_RETRY_COUNT = old["retry"]
    settings.CONTEXTUAL_LLM_PROVIDER = old["provider"]
    settings.CONTEXTUAL_LLM_MODEL = old["model"]
    settings.CONTEXTUAL_LLM_API_KEY = old["provider_key"]
    settings.AUTH_JWT_SECRET = old["secret"]
    settings.APP_ENV = old["env"]
    db.close()
    engine.dispose()


def deterministic_response(conversation_id="shadow-conversation"):
    return AIChatResponse(
        conversation_id=conversation_id,
        status="needs_clarification",
        message=AIMessage(content="Would you like to add a reason?"),
        correlation_id="shadow-correlation",
    )


def add_intake(context, *, owner_id=None):
    row = AILeaveIntakeState(
        id=f"intake-{owner_id or 'owner'}",
        owner_employee_id=owner_id or context["employee"].id,
        conversation_id=context["conversation"].id,
        goal="prepare_leave_request",
        collected_fields=json.dumps({}),
        missing_required_fields=json.dumps(["date_range", "leave_type"]),
        optional_fields=json.dumps(["reason"]),
        source_confidence=json.dumps({}),
        expires_at=datetime.utcnow() + timedelta(minutes=15),
    )
    context["db"].add(row)
    context["db"].commit()
    return row


def test_strict_schema_rejects_unknown_identity_and_unsafe_content():
    payload = interpretation().model_dump(mode="json")
    payload["employee_id"] = "somebody-else"
    with pytest.raises(ValidationError):
        ContextualInterpretation.model_validate(payload)

    arbitrary_capability = interpretation().model_dump(mode="json")
    arbitrary_capability["proposed_capabilities"] = [
        "call_arbitrary_tool"
    ]
    with pytest.raises(ValidationError):
        ContextualInterpretation.model_validate(arbitrary_capability)

    unsafe = interpretation().model_dump(mode="json")
    unsafe["extracted_fields"] = {
        "reason": "SELECT * FROM leave_balances WHERE employee_id=1"
    }
    with pytest.raises(ValidationError):
        ContextualInterpretation.model_validate(unsafe)

    with pytest.raises(ProviderInvalidOutputError):
        parse_structured_interpretation("{not-json")


def test_versioned_few_shot_prompt_is_schema_valid_and_budgeted():
    template = load_prompt_template("contextual_leave_interpreter_v2")
    assert template.version == "contextual_leave_interpreter_v2"
    assert 6 <= len(template.examples) <= 10
    ids = {item.id for item in template.examples}
    assert {
        "start-leave-intake",
        "continue-multiple-fields",
        "modify-date",
        "topic-switch",
        "unsafe-other-employee",
    }.issubset(ids)
    rendered = render_few_shot_examples(template)
    assert estimated_tokens(rendered) <= MAX_FEW_SHOT_ESTIMATED_TOKENS
    prompt = build_contextual_system_prompt(
        version="contextual_leave_interpreter_v2"
    )
    assert "CURRENT_UNTRUSTED_MESSAGE" in prompt
    assert "For next Monday" in prompt
    assert "Actually make it Tuesday" in prompt
    assert estimated_tokens(prompt) < settings.CONTEXTUAL_LLM_MAX_INPUT_TOKENS
    assert (
        settings.CONTEXTUAL_LLM_MAX_INPUT_TOKENS
        - estimated_tokens(prompt)
        >= 3000
    )


def test_enabled_provider_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "CONTEXTUAL_LLM_ENABLED", True)
    monkeypatch.setattr(settings, "CONTEXTUAL_LLM_SHADOW_MODE", True)
    monkeypatch.setattr(settings, "CONTEXTUAL_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "CONTEXTUAL_LLM_MODEL", "test-model")
    monkeypatch.setattr(settings, "CONTEXTUAL_LLM_API_KEY", "")
    monkeypatch.setattr(
        settings,
        "CONTEXTUAL_LLM_PROMPT_VERSION",
        "contextual_leave_interpreter_v2",
    )
    errors = contextual_provider_configuration_errors()
    assert "CONTEXTUAL_LLM_API_KEY is required." in errors

    monkeypatch.setattr(
        settings, "CONTEXTUAL_LLM_API_KEY", "server-only-test-key"
    )
    assert contextual_provider_configuration_errors() == []
    monkeypatch.setattr(settings, "CONTEXTUAL_LLM_SHADOW_MODE", False)
    assert any(
        "must remain true" in item
        for item in contextual_provider_configuration_errors()
    )


def test_official_openai_sdk_adapter_uses_structured_output_without_tools(
    shadow_context,
    monkeypatch,
):
    captured = {}
    expected = interpretation()

    class FakeResponses:
        async def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_parsed=expected,
                usage=SimpleNamespace(input_tokens=90, output_tokens=40),
            )

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.responses = FakeResponses()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(openai_provider_module, "AsyncOpenAI", FakeClient)
    context = build_context_package(
        shadow_context["db"],
        shadow_context["principal"],
        "shadow-conversation",
        current_message="Show my leave balance.",
        correlation_id="official-provider",
    )
    request = LLMProviderRequest(
        system_prompt=build_contextual_system_prompt(),
        current_message="Show my leave balance.",
        context=context,
        max_input_tokens=6000,
        max_output_tokens=700,
        temperature=0,
    )
    response = asyncio.run(
        OpenAILLMProvider(
            model="test-model",
            api_key="server-only-test-key",
            base_url="https://api.openai.com/v1",
            timeout_seconds=4,
        ).interpret(request)
    )
    assert response.interpretation == expected
    assert captured["text_format"] is ContextualInterpretation
    assert captured["store"] is False
    assert "temperature" not in captured
    assert "tools" not in captured
    assert "tool_choice" not in captured
    assert "server-only-test-key" not in captured["input"]
    assert "server-only-test-key" not in captured["instructions"]


def test_context_is_owner_scoped_redacted_and_contains_active_workflow(
    shadow_context,
):
    add_intake(shadow_context)
    db = shadow_context["db"]
    db.add_all(
        [
            AIConversationMessage(
                conversation_id="shadow-conversation",
                owner_employee_id=shadow_context["employee"].id,
                role="user",
                content=(
                    "Email shadow.employee@example.com token Bearer secret.jwt.value "
                    "reference 123e4567-e89b-12d3-a456-426614174000"
                ),
            ),
            AIConversationMessage(
                conversation_id="shadow-conversation",
                owner_employee_id=shadow_context["other"].id,
                role="user",
                content="Another employee private message",
            ),
        ]
    )
    db.commit()
    package = build_context_package(
        db,
        shadow_context["principal"],
        "shadow-conversation",
        current_message="Next Monday",
        correlation_id="correlation",
    )
    encoded = package.model_dump_json()
    assert package.active_workflow.workflow_type == "leave_intake"
    assert package.active_workflow.missing_fields == ["date_range", "leave_type"]
    assert "shadow.employee@example.com" not in encoded
    assert "secret.jwt.value" not in encoded
    assert "123e4567" not in encoded
    assert "Another employee private message" not in encoded
    assert shadow_context["employee"].id not in encoded
    assert shadow_context["principal"].token_id not in encoded
    assert "get_my_leave_balance" not in encoded


def test_known_multi_field_continuation_is_observed_without_business_writes(
    shadow_context,
):
    intake = add_intake(shadow_context)
    provider = MockProvider(
        interpretation(
            fields={
                "leave_type": "Casual Leave",
                "start_date": "2026-07-27",
                "end_date": "2026-07-27",
                "reason": "holiday",
            },
            capabilities=["continue_leave_intake"],
        )
    )
    db = shadow_context["db"]
    before = {
        "requests": db.query(LeaveRequest).count(),
        "drafts": db.query(AILeaveRequestDraft).count(),
        "intakes": db.query(AILeaveIntakeState).count(),
        "messages": db.query(AIConversationMessage).count(),
    }
    row = asyncio.run(
        run_shadow_evaluation(
            db,
            shadow_context["principal"],
            conversation_id="shadow-conversation",
            message=(
                "For next Monday and mention the reason as holiday and "
                "the leave type is casual leave."
            ),
            correlation_id="shadow-correlation",
            deterministic_response=deterministic_response(),
            provider=provider,
        )
    )
    assert row.llm_goal == "prepare_leave_request"
    assert row.llm_workflow_action == "continue"
    assert json.loads(row.extracted_field_categories) == [
        "leave_type",
        "start_date",
        "end_date",
        "reason",
    ]
    assert row.comparison_outcome in {
        "llm_identifies_workflow_continuation",
        "extraction_disagreement",
        "compatible_agreement",
    }
    assert provider.calls[0].context.active_workflow.workflow_type == "leave_intake"
    assert db.get(AILeaveIntakeState, intake.id).collected_fields == "{}"
    assert db.query(LeaveRequest).count() == before["requests"]
    assert db.query(AILeaveRequestDraft).count() == before["drafts"]
    assert db.query(AILeaveIntakeState).count() == before["intakes"]
    assert db.query(AIConversationMessage).count() == before["messages"]


def test_provider_timeout_and_invalid_output_are_metadata_only(
    shadow_context,
):
    slow = SlowProvider(interpretation())
    timeout_row = asyncio.run(
        run_shadow_evaluation(
            shadow_context["db"],
            shadow_context["principal"],
            conversation_id="shadow-conversation",
            message="Show my balance",
            correlation_id="timeout-correlation",
            deterministic_response=deterministic_response(),
            provider=slow,
        )
    )
    assert timeout_row.comparison_outcome == "timeout"
    assert timeout_row.error_category == "provider_timeout"

    invalid = MockProvider(ProviderInvalidOutputError("invalid"))
    invalid_row = asyncio.run(
        run_shadow_evaluation(
            shadow_context["db"],
            shadow_context["principal"],
            conversation_id="shadow-conversation",
            message="Show my balance",
            correlation_id="invalid-correlation",
            deterministic_response=deterministic_response(),
            provider=invalid,
        )
    )
    assert invalid_row.comparison_outcome == "invalid_structured_output"
    assert invalid_row.schema_validation_status == "invalid"
    assert invalid_row.error_category == "provider_invalid_response"


def test_openai_status_errors_map_to_safe_specific_categories():
    def mapped(status, *, error_type=None, code=None, param=None, message=""):
        return _status_error(
            SimpleNamespace(
                status_code=status,
                request_id="req_safe-123",
                code=None,
                param=None,
                body={
                    "type": error_type,
                    "code": code,
                    "param": param,
                    "message": message,
                },
            )
        )

    bad_request = mapped(
        400,
        error_type="invalid_request_error",
        param="temperature",
        message="Unsupported parameter.",
    )
    assert bad_request.category == "provider_bad_request"
    assert bad_request.code == "invalid_request_error"
    assert bad_request.http_status == 400
    assert bad_request.request_id == "req_safe-123"
    assert bad_request.retryable is False
    assert "temperature" in bad_request.safe_message

    structured = mapped(
        400,
        code="invalid_json_schema",
        param="text.format.schema",
    )
    assert structured.category == "provider_structured_output"
    assert mapped(401).category == "provider_authentication"
    assert mapped(403).category == "provider_permission"
    assert mapped(404).category == "provider_model_not_found"
    assert mapped(429, code="rate_limit_exceeded").category == (
        "provider_rate_limit"
    )
    assert mapped(429, code="insufficient_quota").category == "provider_quota"
    assert mapped(500).category == "provider_server_error"


def test_safe_provider_error_metadata_is_persisted(shadow_context):
    failure = ProviderBadRequestError(
        "The contextual provider rejected parameter 'temperature'.",
        code="invalid_request_error",
        http_status=400,
        request_id="req_safe-123",
        retryable=False,
    )
    row = asyncio.run(
        run_shadow_evaluation(
            shadow_context["db"],
            shadow_context["principal"],
            conversation_id="shadow-conversation",
            message="Show my balance",
            correlation_id="safe-error-correlation",
            deterministic_response=deterministic_response(),
            provider=MockProvider(failure),
        )
    )
    assert row.error_category == "provider_bad_request"
    assert row.error_message == (
        "The contextual provider rejected parameter 'temperature'."
    )
    assert row.error_code == "invalid_request_error"
    assert row.error_http_status == 400
    assert row.provider_request_id == "req_safe-123"
    assert row.error_retryable is False


def test_topic_switch_resume_and_owner_scoped_diagnostics(shadow_context):
    add_intake(shadow_context)
    switch = MockProvider(
        interpretation(
            goal="check_leave_balance",
            workflow_action="switch_goal",
            capabilities=["leave.balance.read_self"],
        )
    )
    switch_row = asyncio.run(
        run_shadow_evaluation(
            shadow_context["db"],
            shadow_context["principal"],
            conversation_id="shadow-conversation",
            message="Forget that, show my leave balance.",
            correlation_id="switch-correlation",
            deterministic_response=deterministic_response(),
            provider=switch,
        )
    )
    assert switch_row.segment == "topic_switch"

    resume = MockProvider(
        interpretation(
            workflow_action="resume",
            fields={"request_reference": "active_workflow"},
            capabilities=["continue_leave_intake"],
        )
    )
    resume_row = asyncio.run(
        run_shadow_evaluation(
            shadow_context["db"],
            shadow_context["principal"],
            conversation_id="shadow-conversation",
            message="Go back to the leave request.",
            correlation_id="resume-correlation",
            deterministic_response=deterministic_response(),
            provider=resume,
        )
    )
    assert resume_row.llm_workflow_action == "resume"

    diagnostics = shadow_diagnostics(
        shadow_context["db"], shadow_context["principal"]
    )
    assert len(diagnostics.evaluations) == 2
    assert diagnostics.metrics["total"] == 2
    other_principal = shadow_context["principal"].__class__(
        employee_id=shadow_context["other"].id,
        email=shadow_context["other"].work_email,
        role="employee",
        status="active",
        permissions=frozenset(),
        token_id="other-token",
    )
    assert not shadow_diagnostics(
        shadow_context["db"], other_principal
    ).evaluations


def test_feature_disabled_does_not_schedule_provider_and_enabled_is_observation_only(
    shadow_context, monkeypatch
):
    db = shadow_context["db"]
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(ai_api, "_audit", lambda *args, **kwargs: None)
    calls = []

    async def fake_background(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(ai_api, "run_shadow_evaluation_background", fake_background)
    client = TestClient(app)
    token = create_access_token(shadow_context["employee"])
    headers = {"Authorization": f"Bearer {token}"}

    settings.CONTEXTUAL_LLM_ENABLED = False
    disabled = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "What is my casual leave balance?"},
    )
    assert disabled.status_code == 200
    assert calls == []

    settings.CONTEXTUAL_LLM_ENABLED = True
    enabled = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "What is my casual leave balance?"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["message"] == disabled.json()["message"]
    disabled_result = disabled.json()["result"]
    enabled_result = enabled.json()["result"]
    assert {
        key: value for key, value in enabled_result.items() if key != "as_of"
    } == {
        key: value for key, value in disabled_result.items() if key != "as_of"
    }
    assert enabled.json()["tool_used"] == disabled.json()["tool_used"]
    assert len(calls) == 1
    payload = calls[0][1]["deterministic_response_payload"]
    assert payload["message"] == enabled.json()["message"]


def test_provider_status_is_admin_only_and_never_returns_credential(
    shadow_context, monkeypatch
):
    db = shadow_context["db"]
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(
        settings, "CONTEXTUAL_LLM_API_KEY", "never-return-this-key"
    )
    client = TestClient(app)

    db.add(
        AIContextualShadowEvaluation(
            actor_employee_id=shadow_context["other"].id,
            conversation_id="shadow-conversation",
            correlation_id="other-employee-shadow",
            active_workflow_type="none",
            deterministic_goal="check_leave_balance",
            deterministic_result_category="completed",
            proposed_capabilities="[]",
            extracted_field_categories="[]",
            comparison_outcome="provider_failure",
            segment="standalone",
            schema_validation_status="not_run",
            provider="openai",
            model="test-model",
            latency_ms=100,
            error_category="provider_bad_request",
            error_message="The contextual provider rejected the request.",
            error_code="invalid_request_error",
            error_http_status=400,
            provider_request_id="req_admin-visible",
            error_retryable=False,
            prompt_version="contextual_leave_interpreter_v2",
        )
    )
    db.commit()

    employee_token = create_access_token(shadow_context["other"])
    denied = client.get(
        "/api/v1/ai/shadow-provider-status",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert denied.status_code == 403

    admin_token = create_access_token(shadow_context["employee"])
    allowed = client.get(
        "/api/v1/ai/shadow-provider-status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200
    encoded = allowed.text
    assert "never-return-this-key" not in encoded
    assert allowed.json()["can_affect_production"] is False
    assert allowed.json()["prompt_examples"] == 8
    assert allowed.json()["recent_evaluations"] == 1
    assert allowed.json()["last_error_category"] == "provider_bad_request"
    assert allowed.json()["last_error_http_status"] == 400
    assert allowed.json()["last_provider_request_id"] == "req_admin-visible"

    status = contextual_provider_status(db, shadow_context["principal"])
    assert status.recent_evaluations == 1


def test_evaluation_dataset_is_complete_and_non_production():
    path = (
        __import__("pathlib").Path(__file__).parent
        / "evals"
        / "contextual_leave_phase_a.json"
    )
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert len(rows) >= 38
    assert all(
        {
            "active_workflow",
            "recent_conversation",
            "expected",
            "allowed_capabilities",
            "prohibited_behavior",
        }.issubset(row)
        for row in rows
    )
    assert any(row["id"] == "known-multi-field" for row in rows)
    assert any(row["id"] == "prompt-injection" for row in rows)
    assert any(row["id"] == "contradictory-leave-types" for row in rows)
    assert any(row["id"] == "misspelled-sick-tomorrow" for row in rows)

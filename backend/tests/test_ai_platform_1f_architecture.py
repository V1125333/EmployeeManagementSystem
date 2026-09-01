"""Platform 1F production-isolation and project confidentiality guards."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def test_production_ai_prompts_and_providers_do_not_import_project_capability():
    paths = [
        BACKEND / "app/api/ai.py", BACKEND / "app/ai/orchestrator.py",
        BACKEND / "app/ai/prompts.py", BACKEND / "app/ai/prompt_templates.py",
        *list((BACKEND / "app/ai/providers").glob("*.py")),
    ]
    for path in paths:
        if path.exists():
            source = path.read_text(encoding="utf-8")
            assert "project.assignments.list_self" not in source
            assert "capabilities.projects" not in source


def test_project_assignment_service_is_framework_independent_and_read_only():
    source = (BACKEND / "app/services/project_assignment_service.py").read_text(encoding="utf-8")
    for token in ("fastapi", "APIRouter", "Depends", "db.commit(", "db.flush(", "db.add(", "db.delete("):
        assert token not in source
    assert "app.api" not in source


def test_project_adapter_has_no_dynamic_target_route_or_confidential_fields():
    source = (BACKEND / "app/ai_platform/capabilities/projects.py").read_text(encoding="utf-8")
    assert "app.api" not in source and "importlib" not in source
    for target in ("employee_id:", "project_id:", "client_id:", "manager_id:"):
        assert target not in source
    for confidential in ("budget", "margin", "billing_rate", "client_contact", "document"):
        assert confidential not in source.lower()


def test_generic_executor_has_no_project_special_case_and_cards_require_grounding():
    for name in ("executor.py", "plan_executor.py"):
        source = (BACKEND / "app/ai_platform" / name).read_text(encoding="utf-8")
        assert "project.assignments.list_self" not in source
        assert "CurrentProjectAssignments" not in source
    composer = (BACKEND / "app/ai_platform/response_composer.py").read_text(encoding="utf-8")
    assert "def compose_project_assignments_response(\n    grounding: ValidatedGrounding" in composer


def test_no_frontend_model_migration_prompt_or_provider_wiring_for_project_capability():
    paths = [
        *list((ROOT / "src").rglob("*.ts")), *list((ROOT / "src").rglob("*.tsx")),
        *list((BACKEND / "app/models").glob("*.py")),
        *list((BACKEND / "alembic/versions").glob("*.py")),
        *list((BACKEND / "app/ai/providers").glob("*.py")),
        *list((BACKEND / "app/ai/prompt_templates").glob("*")),
    ]
    for path in paths:
        if path.is_file():
            if path.name in {"AIPlatformPreviewPage.tsx", "AIPlatformPreviewPage.test.tsx", "platformPreviewApi.ts"}:
                continue
            assert "project.assignments.list_self" not in path.read_text(encoding="utf-8"), path

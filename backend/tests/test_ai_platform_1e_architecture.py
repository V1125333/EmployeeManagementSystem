"""Platform 1E production-isolation and manager privacy guards."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def test_production_ai_prompts_and_providers_do_not_import_manager_capability():
    paths = [BACKEND / "app/api/ai.py", BACKEND / "app/ai/orchestrator.py",
             BACKEND / "app/ai/prompts.py", BACKEND / "app/ai/prompt_templates.py",
             *list((BACKEND / "app/ai/providers").glob("*.py"))]
    for path in paths:
        if path.exists():
            source = path.read_text(encoding="utf-8")
            assert "employee.manager.read_self" not in source
            assert "capabilities.manager" not in source


def test_manager_service_is_framework_independent_read_only_and_not_a_route():
    path = BACKEND / "app/services/employee_directory_service.py"
    source = path.read_text(encoding="utf-8")
    for token in ("fastapi", "APIRouter", "Depends", ".commit(", ".flush(", ".add(", ".delete("):
        assert token not in source


def test_manager_capability_has_no_dynamic_target_or_route_dependency():
    source = (BACKEND / "app/ai_platform/capabilities/manager.py").read_text(encoding="utf-8")
    assert "app.api" not in source and "importlib" not in source
    assert "employee_id:" not in source and "manager_id:" not in source


def test_no_frontend_model_or_migration_wiring_for_manager_capability():
    paths = [*list((ROOT / "src").rglob("*.ts")), *list((ROOT / "src").rglob("*.tsx")),
             *list((BACKEND / "app/models").glob("*.py")), *list((BACKEND / "alembic/versions").glob("*.py"))]
    for path in paths:
        if path.name in {"AIPlatformPreviewPage.tsx", "AIPlatformPreviewPage.test.tsx", "platformPreviewApi.ts"}:
            continue
        assert "employee.manager.read_self" not in path.read_text(encoding="utf-8"), path

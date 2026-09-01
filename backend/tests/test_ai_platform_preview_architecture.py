"""Static guards for preview-only isolation and non-expansion."""

from pathlib import Path

from app.ai_platform.platform_registry import PLATFORM_REGISTRY

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_preview_route_is_environment_protected_hidden_and_not_public():
    route = source("backend/app/api/ai_platform_preview.py")
    assert 'environment not in {"development", "dev", "test"}' in route
    assert "include_in_schema=False" in route and "status_code=404" in route
    authentication = source("backend/app/core/authentication.py")
    assert "platform-preview" not in authentication


def test_production_chat_and_frontend_remain_disconnected_from_preview():
    assert "ai_platform" not in source("backend/app/api/ai.py")
    assert "ai_platform" not in source("backend/app/ai/orchestrator.py")
    normal_page = source("src/pages/AskOrbitAIPage.tsx")
    assert "platform-preview" not in normal_page and "AIPlatformPreview" not in normal_page


def test_preview_has_no_provider_prompt_persistence_or_identity_header_path():
    backend = source("backend/app/ai_platform/preview.py") + source("backend/app/api/ai_platform_preview.py")
    frontend = source("src/services/platformPreviewApi.ts")
    for forbidden in ("OpenAI", "provider_factory", "prompt_template", "AIConversation(", "db.add(", "db.commit("):
        assert forbidden not in backend
    for forbidden in ("X-User-Id", "X-User-Email", "employee_id", "capability_id:"):
        assert forbidden not in frontend.split("JSON.stringify({ message })")[0] if forbidden.startswith("X-User") else True
    assert "JSON.stringify({ message })" in frontend


def test_registry_stays_exactly_three_read_capabilities_and_no_new_schema_artifacts():
    assert {(capability_id, version) for capability_id, version, _ in PLATFORM_REGISTRY.list_metadata()} == {
        ("leave.balance.read_self", 1),
        ("employee.manager.read_self", 1),
        ("project.assignments.list_self", 1),
    }
    preview_files = [path.as_posix() for path in ROOT.glob("**/*preview*")]
    assert not any("alembic/versions" in path for path in preview_files)
    assert "model_dump" not in source("backend/app/ai_platform/preview.py")

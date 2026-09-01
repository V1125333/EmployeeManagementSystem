"""Architecture isolation guards for Platform 1D."""

from __future__ import annotations

import ast
from pathlib import Path

from app.ai_platform.contracts import OperationClass
from app.ai_platform.platform_registry import PLATFORM_REGISTRY


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PLATFORM = BACKEND / "app" / "ai_platform"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: found.add(node.module)
    return found


def test_production_gateway_and_orchestrator_do_not_import_platform_1d():
    for relative in ("app/api/ai.py", "app/ai/orchestrator.py"):
        source = (BACKEND / relative).read_text(encoding="utf-8")
        assert "app.ai_platform.orchestrator" not in source
        assert "run_platform_request" not in source


def test_isolated_orchestrator_has_no_llm_provider_prompt_persistence_or_conversation_write():
    path = PLATFORM / "orchestrator.py"
    imported = imports(path)
    forbidden = ("app.ai.providers", "app.ai.prompts", "openai", "app.services.ai_conversation_service")
    assert not any(module.startswith(forbidden) for module in imported)
    source = path.read_text(encoding="utf-8")
    for token in ("append_message", "db.commit", "background_tasks", "provider", "completion.create"):
        assert token not in source


def test_grounding_uses_fixed_application_paths_and_composer_has_no_raw_result_or_database_input():
    grounding = (PLATFORM / "grounding.py").read_text(encoding="utf-8")
    assert "importlib" not in grounding and "eval(" not in grounding and "exec(" not in grounding
    composer = ast.parse((PLATFORM / "response_composer.py").read_text(encoding="utf-8"))
    function = next(node for node in composer.body if isinstance(node, ast.FunctionDef) and node.name == "compose_leave_balance_response")
    assert [arg.arg for arg in function.args.args] == ["grounding"]
    assert [arg.arg for arg in function.args.kwonlyargs] == ["locale", "timezone"]


def test_registry_contains_only_approved_read_only_capabilities():
    assert len(PLATFORM_REGISTRY) == 3
    definition = PLATFORM_REGISTRY.resolve("leave.balance.read_self", 1)
    assert definition.operation_class is OperationClass.READ


def test_no_frontend_model_migration_prompt_or_provider_references_platform_1d():
    paths = [
        *list((ROOT / "src").rglob("*.ts")), *list((ROOT / "src").rglob("*.tsx")),
        *list((BACKEND / "app" / "models").rglob("*.py")),
        *list((BACKEND / "alembic" / "versions").rglob("*.py")),
        *list((BACKEND / "app" / "ai" / "providers").rglob("*.py")),
        BACKEND / "app" / "ai" / "prompts.py", BACKEND / "app" / "ai" / "prompt_templates.py",
    ]
    for path in paths:
        if path.exists():
            source = path.read_text(encoding="utf-8")
            assert "run_platform_request" not in source, path
            assert "ValidatedGrounding" not in source, path

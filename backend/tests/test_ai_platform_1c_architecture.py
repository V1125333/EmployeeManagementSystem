"""Isolation and authority guards for Platform 1C."""

from __future__ import annotations

import ast
from pathlib import Path

from app.ai_platform.platform_registry import PLATFORM_REGISTRY


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PLATFORM = BACKEND / "app" / "ai_platform"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }


def test_chat_orchestrator_and_legacy_tool_registry_are_not_wired_to_planning():
    for relative in ("app/api/ai.py", "app/ai/orchestrator.py", "app/ai/tool_registry.py"):
        source = (BACKEND / relative).read_text(encoding="utf-8")
        assert "ai_platform.interpreter" not in source
        assert "ai_platform.plan_validator" not in source
        assert "execute_validated_plan" not in source


def test_interpreter_and_validator_have_no_llm_provider_network_sql_shell_or_dynamic_invocation():
    forbidden = {"openai", "requests", "httpx", "socket", "subprocess", "sqlalchemy", "importlib"}
    for name in ("interpreter.py", "plan_validator.py"):
        path = PLATFORM / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = imported_modules(path)
        assert not any(module.split(".")[0] in forbidden for module in imports)
        calls = {
            getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            for node in ast.walk(tree) if isinstance(node, ast.Call)
        }
        assert not ({"eval", "exec", "__import__", "system", "popen"} & calls)


def test_interpreter_cannot_execute_authorize_or_import_application_routes():
    imports = imported_modules(PLATFORM / "interpreter.py")
    forbidden_prefixes = (
        "app.api", "app.services", "app.ai.providers", "app.ai_platform.executor",
        "app.ai_platform.plan_executor", "app.ai_platform.authorization_policy",
    )
    assert not any(module.startswith(forbidden_prefixes) for module in imports)
    source = (PLATFORM / "interpreter.py").read_text(encoding="utf-8")
    assert "execute_capability(" not in source
    assert "execute_validated_plan(" not in source
    assert "authorization_policy(" not in source


def test_platform_registry_exposes_only_approved_explicit_read_capabilities():
    assert len(PLATFORM_REGISTRY) == 3
    assert {(item[0], item[1]) for item in PLATFORM_REGISTRY.list_metadata()} == {
        ("leave.balance.read_self", 1), ("employee.manager.read_self", 1),
        ("project.assignments.list_self", 1),
    }


def test_no_routes_models_migrations_frontend_or_provider_wiring_was_added():
    needles = ("interpret_employee_request", "validate_candidate_plan", "execute_validated_plan")
    paths = [
        *list((BACKEND / "app" / "api").rglob("*.py")),
        *list((BACKEND / "app" / "models").rglob("*.py")),
        *list((BACKEND / "app" / "ai" / "providers").rglob("*.py")),
        *list((BACKEND / "alembic" / "versions").rglob("*.py")),
        *list((ROOT / "src").rglob("*.ts")), *list((ROOT / "src").rglob("*.tsx")),
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert not any(needle in source for needle in needles), path

"""Architecture isolation guards for the Platform 1B capability adapter."""

from __future__ import annotations

import ast
from pathlib import Path

from app.ai.tool_registry import AI_TOOLS
from app.ai_platform.capabilities.leave import LEAVE_BALANCE_CAPABILITY_ID
from app.ai_platform.platform_registry import PLATFORM_REGISTRY


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PLATFORM = BACKEND / "app" / "ai_platform"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_current_chat_and_orchestrator_do_not_import_or_invoke_platform_registry():
    for relative in ("app/api/ai.py", "app/ai/orchestrator.py"):
        path = BACKEND / relative
        source = path.read_text(encoding="utf-8")
        assert "ai_platform" not in source
        assert "PLATFORM_REGISTRY" not in source


def test_existing_leave_tool_registry_remains_separate_and_unchanged_in_scope():
    assert LEAVE_BALANCE_CAPABILITY_ID not in AI_TOOLS
    assert set(AI_TOOLS) == {
        "get_my_leave_balance", "compare_my_leave_balance",
        "get_my_recent_leave_requests", "get_my_leave_request_status",
        "get_my_leave_request_details", "explain_my_leave_decision",
        "check_my_leave_eligibility", "prepare_my_leave_request",
        "get_my_leave_request_draft", "update_my_leave_request_draft",
        "discard_my_leave_request_draft",
    }
    assert len(PLATFORM_REGISTRY) == 3


def test_adapter_calls_safe_tool_and_never_imports_route_handler():
    path = PLATFORM / "capabilities" / "leave.py"
    imported = imports(path)
    assert "app.ai.leave_balance_tool" in imported
    assert not any(module.startswith("app.api") for module in imported)


def test_executor_has_no_dynamic_import_network_sql_shell_or_recursive_execution():
    path = PLATFORM / "executor.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = imports(path)
    forbidden_modules = {"requests", "httpx", "subprocess", "socket", "sqlalchemy"}
    assert not (imported & forbidden_modules)
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            calls.append(getattr(node.func, "id", None) or getattr(node.func, "attr", None))
    assert not ({"__import__", "eval", "exec", "system", "popen"} & set(calls))
    assert "execute_capability" not in calls


def test_no_provider_prompt_frontend_model_or_migration_references_platform_capability():
    checked_paths = [
        *list((BACKEND / "app" / "ai" / "providers").glob("*.py")),
        BACKEND / "app" / "ai" / "prompts.py",
        BACKEND / "app" / "ai" / "prompt_templates.py",
        *list((BACKEND / "app" / "models").glob("*.py")),
        *list((BACKEND / "alembic" / "versions").glob("*.py")),
        *list((ROOT / "src").rglob("*.ts")),
        *list((ROOT / "src").rglob("*.tsx")),
    ]
    for path in checked_paths:
        if path.exists():
            source = path.read_text(encoding="utf-8")
            assert LEAVE_BALANCE_CAPABILITY_ID not in source, path
            assert "app.ai_platform" not in source, path


def test_no_server_compatibility_feature_flag_was_added():
    config_source = (BACKEND / "app" / "core" / "config.py").read_text(encoding="utf-8")
    assert "AI_PLATFORM_LEAVE_BALANCE" not in config_source
    assert "PLATFORM_1B" not in config_source

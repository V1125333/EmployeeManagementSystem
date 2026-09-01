"""AST/import guards proving Platform 1A remains isolated from production."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
PACKAGE = BACKEND / "app" / "ai_platform"
PRODUCTION_AI = (
    BACKEND / "app" / "api" / "ai.py",
    BACKEND / "app" / "ai" / "orchestrator.py",
    BACKEND / "app" / "ai" / "tool_registry.py",
)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_platform_package_does_not_import_fastapi_routes_frontend_or_existing_ai_runtime():
    forbidden_prefixes = (
        "fastapi", "app.api", "app.ai.orchestrator", "app.ai.tool_registry",
        "app.ai.providers", "src", "frontend",
    )
    for path in PACKAGE.glob("*.py"):
        modules = imported_modules(path)
        assert not any(module.startswith(forbidden_prefixes) for module in modules), (path, modules)


def test_production_ai_path_does_not_import_or_invoke_platform_1a():
    for path in PRODUCTION_AI:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        modules = imported_modules(path)
        assert not any(module.startswith("app.ai_platform") for module in modules)
        assert not any(
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "ai_platform"
            for node in ast.walk(tree)
        )


def test_platform_has_no_dynamic_imports_rest_identifiers_or_registration_mutator():
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"__import__", "eval", "exec"}
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not node.value.startswith("/api/")
    registry = importlib.import_module("app.ai_platform.capability_registry").CapabilityRegistry()
    assert not hasattr(registry, "register")


def test_platform_contracts_do_not_define_orm_models_or_migration_metadata():
    for path in PACKAGE.glob("*.py"):
        modules = imported_modules(path)
        assert "sqlalchemy" not in modules
        assert not any(module.startswith("app.models") for module in modules)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        assert "Base" not in class_names
        assert "Alembic" not in class_names


def test_platform_capability_registration_is_explicit_and_centralized():
    definition_calls: list[Path] = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name == "CapabilityDefinition":
                    definition_calls.append(path)
    assert len(definition_calls) == 3
    assert set(definition_calls) == {PACKAGE / "platform_registry.py"}

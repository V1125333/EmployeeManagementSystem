"""AST-based Task 8A debt inventory.

The allowlists make existing debt visible while preventing it from growing.
Task 8G can reduce each allowlist to zero and turn these into strict guards.
"""

from __future__ import annotations

import ast
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def _qualified(path: Path, function: str) -> str:
    return f"{path.relative_to(BACKEND).as_posix()}::{function}"


def _enclosing_function(tree: ast.AST, target: ast.AST) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and target in set(ast.walk(node)):
            return node.name
    return "<module>"


def _direct_model_inserts(model_name: str) -> set[str]:
    found: set[str] = set()
    for path in [*APP.glob("api/*.py"), *APP.glob("services/*.py")]:
        tree = _tree(path)
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add"
                and node.args
                and isinstance(node.args[0], ast.Call)
            ):
                continue
            constructor = node.args[0].func
            name = constructor.id if isinstance(constructor, ast.Name) else None
            if name == model_name:
                found.add(_qualified(path, _enclosing_function(tree, node)))
    return found


def _route_names(tree: ast.Module) -> set[str]:
    result = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in {"get", "post", "put", "patch", "delete"}
            for decorator in node.decorator_list
        ):
            result.add(node.name)
    return result


def _route_to_route_calls() -> set[str]:
    found = set()
    for path in APP.glob("api/*.py"):
        tree = _tree(path)
        routes = _route_names(tree)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in routes:
                continue
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in routes:
                    found.add(f"{_qualified(path, node.name)} -> {call.func.id}")
    return found


def _functions_calling_commit(paths: list[Path]) -> set[str]:
    found = set()
    for path in paths:
        tree = _tree(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "commit"
                for call in ast.walk(node)
            ):
                found.add(_qualified(path, node.name))
    return found


def test_current_direct_notification_insert_allowlist():
    assert _direct_model_inserts("Notification") == {
        "app/api/admin_time_off.py::notify",
        "app/api/announcements.py::create_notifications_for_published",
        "app/api/employees.py::update_employee",
        "app/api/inbox_notifications.py::create_notification",
        "app/api/timesheets.py::create_notification",
        "app/services/allocation_service.py::create_allocation",
        "app/services/allocation_service.py::ensure_allocation_ending_notifications",
        "app/services/auth_service.py::notify_admins_account_locked",
        "app/services/auth_service.py::notify_admins_unlock_requested",
        "app/services/auth_service.py::notify_employee_unlocked",
        "app/services/auth_service.py::reject_unlock",
        "app/services/requests_service.py::_notify",
    }


def test_current_direct_action_inbox_insert_allowlist():
    assert _direct_model_inserts("ActionInboxItem") == {
        "app/api/announcements.py::create_notifications_for_published",
        "app/api/employees.py::remind_emergency_contact",
        "app/services/requests_service.py::_inbox",
    }


def test_current_direct_timesheet_mutation_allowlist():
    """Inventory known row mutation entry points; the canonical service does not exist yet."""
    assert {
        "app/api/timesheets.py::save_my_timesheet_week",
        "app/api/timesheets.py::submit_my_timesheet_week",
        "app/api/timesheets.py::recall_my_timesheet_week",
        "app/api/timesheets.py::copy_my_timesheet_week",
        "app/api/timesheets.py::delete_my_timesheet_week",
        "app/api/timesheets.py::decide_timesheet",
        "app/api/admin_time_off.py::decide_timesheet",
    } == _timesheet_mutators()


def _timesheet_mutators() -> set[str]:
    found = set()
    mutation_fields = {"status", "submitted_at", "reviewed_by", "reviewed_at", "reviewer_notes", "overtime_status"}
    for path in [APP / "api/timesheets.py", APP / "api/admin_time_off.py"]:
        tree = _tree(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            constructs = any(
                isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "TimesheetEntry"
                for call in ast.walk(node)
            )
            deletes = any(
                isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "delete"
                for call in ast.walk(node)
            )
            assigns_state = any(
                isinstance(target, ast.Attribute) and target.attr in mutation_fields
                for statement in ast.walk(node)
                if isinstance(statement, (ast.Assign, ast.AnnAssign))
                for target in (statement.targets if isinstance(statement, ast.Assign) else [statement.target])
            )
            is_admin_timesheet = path.name == "admin_time_off.py" and node.name == "decide_timesheet"
            if constructs or deletes or (assigns_state and (path.name == "timesheets.py" or is_admin_timesheet)):
                found.add(_qualified(path, node.name))
    return found


def test_current_route_to_route_call_allowlist():
    assert _route_to_route_calls() == {
        "app/api/admin_time_off.py::decide_leave -> admin_time_off_dashboard",
        "app/api/admin_time_off.py::adjust_balance -> admin_time_off_dashboard",
        "app/api/admin_time_off.py::update_attendance -> admin_time_off_dashboard",
        "app/api/admin_time_off.py::decide_correction -> admin_time_off_dashboard",
        "app/api/admin_time_off.py::decide_timesheet -> admin_time_off_dashboard",
        "app/api/inbox_notifications.py::get_inbox_count -> get_inbox",
        "app/api/leaves.py::decide_leave_request -> leave_approvals",
        "app/api/timesheets.py::submit_my_timesheet_week -> save_my_timesheet_week",
        "app/api/timesheets.py::decide_timesheet -> timesheet_approvals",
    }


def test_current_route_local_commit_allowlist_for_timesheet_and_notification_paths():
    paths = [
        APP / "api/timesheets.py",
        APP / "api/admin_time_off.py",
        APP / "api/inbox_notifications.py",
        APP / "api/announcements.py",
    ]
    assert _functions_calling_commit(paths) == {
        "app/api/timesheets.py::save_my_timesheet_week",
        "app/api/timesheets.py::submit_my_timesheet_week",
        "app/api/timesheets.py::recall_my_timesheet_week",
        "app/api/timesheets.py::copy_my_timesheet_week",
        "app/api/timesheets.py::delete_my_timesheet_week",
        "app/api/timesheets.py::timesheet_allocation_compliance",
        "app/api/timesheets.py::decide_timesheet",
        "app/api/admin_time_off.py::decide_leave",
        "app/api/admin_time_off.py::adjust_balance",
        "app/api/admin_time_off.py::update_attendance",
        "app/api/admin_time_off.py::decide_correction",
        "app/api/admin_time_off.py::decide_timesheet",
        "app/api/inbox_notifications.py::get_inbox",
        "app/api/inbox_notifications.py::complete_inbox_item",
        "app/api/inbox_notifications.py::decide_leave_request",
        "app/api/inbox_notifications.py::decide_attendance_correction",
        "app/api/inbox_notifications.py::mark_notification_read",
        "app/api/inbox_notifications.py::mark_all_notifications_read",
        "app/api/announcements.py::create_announcement",
        "app/api/announcements.py::update_announcement",
        "app/api/announcements.py::delete_announcement",
        "app/api/announcements.py::acknowledge_announcement",
        "app/api/announcements.py::mark_read",
    }


def test_current_notification_helper_duplication_allowlist():
    helper_names = set()
    for path in [*APP.glob("api/*.py"), *APP.glob("services/*.py")]:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                "create_notification", "notify", "_notify",
            }:
                if any(
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "add"
                    and call.args
                    and isinstance(call.args[0], ast.Call)
                    and isinstance(call.args[0].func, ast.Name)
                    and call.args[0].func.id == "Notification"
                    for call in ast.walk(node)
                ):
                    helper_names.add(_qualified(path, node.name))
    assert helper_names == {
        "app/api/admin_time_off.py::notify",
        "app/api/inbox_notifications.py::create_notification",
        "app/api/timesheets.py::create_notification",
        "app/services/requests_service.py::_notify",
    }

from types import SimpleNamespace

from app.api.employees import resolve_manager_id, stabilize_manager_map


def employee(employee_id, first_name, last_name, role="employee", manager_id=None, reporting_manager=""):
    return SimpleNamespace(
        id=employee_id,
        first_name=first_name,
        last_name=last_name,
        work_email=f"{first_name.lower()}@reknew.ai",
        role=role,
        manager_id=manager_id,
        reporting_manager=reporting_manager,
    )


def assert_acyclic(manager_ids):
    for employee_id in manager_ids:
        visited = set()
        current_id = employee_id
        while current_id:
            assert current_id not in visited
            visited.add(current_id)
            current_id = manager_ids.get(current_id)


def test_legacy_reporting_manager_name_resolves_to_employee_id():
    manager = employee("manager", "Venu", "Madhav Pendurthi", role="manager")
    direct_report = employee("report", "Hari", "Satagopam", reporting_manager="Venu Pendurthi")

    assert resolve_manager_id(direct_report, [manager, direct_report]) == manager.id


def test_explicit_manager_id_takes_precedence_over_legacy_name():
    first_manager = employee("manager-1", "David", "Park", role="manager")
    second_manager = employee("manager-2", "Venu", "Pendurthi", role="manager")
    direct_report = employee(
        "report",
        "Hari",
        "Satagopam",
        manager_id=first_manager.id,
        reporting_manager="Venu Pendurthi",
    )

    assert resolve_manager_id(direct_report, [first_manager, second_manager, direct_report]) == first_manager.id


def test_legacy_cycle_is_broken_and_attached_to_super_admin_root():
    root = employee("root", "Super", "Admin", role="super_admin")
    venu = employee("venu", "Venu", "Pendurthi", role="manager")
    david = employee("david", "David", "Park", role="manager")
    report = employee("report", "Hari", "Satagopam")

    stable = stabilize_manager_map(
        [root, venu, david, report],
        {root.id: None, venu.id: david.id, david.id: venu.id, report.id: venu.id},
    )

    assert stable[venu.id] == root.id
    assert stable[david.id] == venu.id
    assert stable[report.id] == venu.id
    assert_acyclic(stable)

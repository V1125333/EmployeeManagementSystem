"""Generate a no-write RBAC role-normalization report for review."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import inspect, text

from app.core.database import engine
from app.core.rbac import (
    AMBIGUOUS_LEGACY_ROLES,
    EmploymentType,
    SAFE_LEGACY_ROLE_MAPPINGS,
    canonical_employment_type,
    normalize_identifier,
)


REPORT_ROOT = Path(__file__).resolve().parents[2] / "rbac-report"
CSV_PATH = REPORT_ROOT / "rbac-migration-report.csv"
JSON_PATH = REPORT_ROOT / "rbac-migration-report.json"

FIELDS = [
    "Employee ID",
    "Employee Name",
    "Current Role",
    "Proposed Canonical Role",
    "Proposed Employment Type",
    "Risk",
    "Action",
]


def employee_name(employee: dict[str, object]) -> str:
    return " ".join(
        str(part).strip() for part in [employee.get("first_name"), employee.get("last_name")] if part and str(part).strip()
    ) or str(employee.get("work_email") or employee.get("id") or "")


def proposed_employment_type(employee: dict[str, object], normalized_role: str) -> str:
    if normalized_role in {"trainee", "intern", "contractor", "consultant"}:
        return normalized_role
    for value in (employee.get("employment_type"), employee.get("workforce_type")):
        if not value:
            continue
        try:
            return canonical_employment_type(value).value
        except ValueError:
            continue
    return EmploymentType.FULL_TIME.value


def classify_employee(employee: dict[str, object]) -> dict[str, str]:
    current_role = str(employee.get("role") or "")
    normalized_role = normalize_identifier(current_role)
    employment_type = proposed_employment_type(employee, normalized_role)
    if normalized_role in AMBIGUOUS_LEGACY_ROLES:
        proposed_role = ""
        risk = "High"
        action = "Manual security review required before changing this privileged legacy role."
    elif normalized_role in SAFE_LEGACY_ROLE_MAPPINGS:
        proposed_role = SAFE_LEGACY_ROLE_MAPPINGS[normalized_role].value
        risk = "Safe"
        action = "Can be normalized after report approval."
    else:
        proposed_role = ""
        risk = "Unknown"
        action = "Manual review required; role is not in the canonical or safe legacy catalog."

    return {
        "Employee ID": str(employee.get("id") or ""),
        "Employee Name": employee_name(employee),
        "Current Role": current_role,
        "Proposed Canonical Role": proposed_role,
        "Proposed Employment Type": employment_type,
        "Risk": risk,
        "Action": action,
    }


def generate() -> list[dict[str, str]]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    inspector = inspect(engine)
    employee_columns = {column["name"] for column in inspector.get_columns("employees")}
    select_columns = [
        "id",
        "first_name",
        "last_name",
        "work_email",
        "role",
        "workforce_type",
    ]
    if "employment_type" in employee_columns:
        select_columns.append("employment_type")
    else:
        select_columns.append("NULL AS employment_type")
    statement = text(
        "SELECT "
        + ", ".join(select_columns)
        + " FROM employees ORDER BY first_name ASC, last_name ASC"
    )
    with engine.connect() as connection:
        rows = [classify_employee(dict(row._mapping)) for row in connection.execute(statement)]

    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    JSON_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


if __name__ == "__main__":
    generated = generate()
    print(f"Generated {CSV_PATH} and {JSON_PATH} with {len(generated)} employee rows.")

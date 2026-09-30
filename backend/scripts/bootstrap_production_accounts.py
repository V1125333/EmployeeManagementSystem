"""Create or reset the two initial production accounts from environment secrets.

This is intentionally an operator-run script. Passwords are read only from
environment variables and are never printed. Remove the variables and this
script from the Railway pre-deploy command immediately after a successful run.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.models.employee import Employee  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402


ACCOUNTS = (
    {
        "email": "superadmin@reknew.ai",
        "password_variable": "BOOTSTRAP_SUPERADMIN_PASSWORD",
        "first_name": "Super",
        "last_name": "Admin",
        "role": "super_admin",
        "designation": "Super Administrator",
    },
    {
        "email": "vpendurthi@reknew.ai",
        "password_variable": "BOOTSTRAP_EMPLOYEE_PASSWORD",
        "first_name": "V",
        "last_name": "Pendurthi",
        "role": "employee",
        "designation": "Employee",
    },
)


def required_password(variable: str) -> str:
    value = os.getenv(variable, "")
    if len(value) < 12:
        raise RuntimeError(f"{variable} must be set to a password of at least 12 characters.")
    return value


def upsert_account(db, account: dict[str, str]) -> str:
    email = account["email"].lower()
    employee = db.query(Employee).filter(func.lower(Employee.work_email) == email).first()
    action = "reset"
    if employee is None:
        action = "created"
        employee = Employee(
            first_name=account["first_name"],
            last_name=account["last_name"],
            work_email=email,
            phone="0000000000",
            workforce_type="full_time",
            employment_type="full_time",
            role=account["role"],
            employment_status="active",
            location="Onshore",
            joining_date=date.today(),
            date_of_joining=date.today(),
            work_location="Onshore",
            department="",
            designation=account["designation"],
            reporting_manager="",
        )
        db.add(employee)

    employee.role = account["role"]
    employee.password_hash = hash_password(required_password(account["password_variable"]))
    employee.password_changed_at = datetime.utcnow()
    employee.is_active = True
    employee.employment_status = "active"
    employee.is_first_login = False
    employee.setup_code = None
    employee.force_password_change = False
    employee.failed_login_attempts = 0
    employee.failed_reset_attempts = 0
    employee.account_locked = False
    employee.locked_at = None
    employee.locked_until = None
    employee.locked_reason = None
    employee.totp_secret = None
    employee.mfa_enabled = False
    return action


def main() -> None:
    # Validate both secrets before making any database changes.
    for account in ACCOUNTS:
        required_password(account["password_variable"])

    db = SessionLocal()
    try:
        results = [(account["email"], upsert_account(db, account)) for account in ACCOUNTS]
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    for email, action in results:
        print(f"Production account {action}: {email}")


if __name__ == "__main__":
    main()

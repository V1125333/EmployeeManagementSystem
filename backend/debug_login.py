"""
Debug script: check employee record and verify password hash.
Run from backend/ with: python debug_login.py [--reset-password NEW_PASS]

Examples:
  python debug_login.py                          # just diagnose
  python debug_login.py --reset Test@12345       # reset the password directly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(".env")

from app.core.database import engine, SessionLocal
from sqlalchemy import text
from app.services.auth_service import verify_password, hash_password

TARGET_EMAIL = "trilokkambham@reknew.com"

print("=" * 60)
print("Debugging login for: " + TARGET_EMAIL)
print("=" * 60)

reset_mode = "--reset" in sys.argv
new_password = sys.argv[sys.argv.index("--reset") + 1] if reset_mode else None

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT id, work_email, password_hash, "
        "account_locked, force_password_change, failed_login_attempts, "
        "is_active, is_first_login "
        "FROM employees WHERE LOWER(work_email) = LOWER(:email)"
    ), {"email": TARGET_EMAIL})
    rows = result.fetchall()

    if not rows:
        print("NO USER FOUND with that email")
        sys.exit(1)
    if len(rows) > 1:
        print("DUPLICATE USERS FOUND: " + str(len(rows)) + " rows")

    for r in rows:
        d = dict(r._mapping)
        pw_hash = d.pop("password_hash", None)
        employee_id = d["id"]

        print("\nRecord found:")
        print("  id:                    " + str(d["id"]))
        print("  work_email:            " + str(d["work_email"]))
        pw_len = len(pw_hash) if pw_hash else 0
        print("  password_hash:         " + ("SET (len=" + str(pw_len) + ")" if pw_hash else "NULL"))
        if pw_hash:
            print("  hash prefix (7 chars): " + pw_hash[:7])
            is_bcrypt = pw_hash.startswith("$2b$") or pw_hash.startswith("$2a$")
            print("  looks like bcrypt:     " + ("YES" if is_bcrypt else "NO - PROBLEM"))
        print("  is_active:             " + str(d["is_active"]))
        print("  is_first_login:        " + str(d["is_first_login"]))
        print("  account_locked:        " + str(d["account_locked"]))
        print("  force_password_change: " + str(d["force_password_change"]))
        print("  failed_login_attempts: " + str(d["failed_login_attempts"]))

        if pw_hash:
            test_passwords = [
                "Test@1234",
                "Trilok@123",
                "Password@1",
                "Admin@123",
                "Reknew@123",
                "Reknew@1234",
                "Trilok@1234",
                "Trilok@12345",
                "trilok@123",
            ]
            print("\nTesting known passwords against stored hash:")
            found = False
            for p in test_passwords:
                try:
                    match = verify_password(p, pw_hash)
                    print("  '" + p + "': " + ("*** MATCH ***" if match else "no match"))
                    if match:
                        found = True
                except Exception as e:
                    print("  '" + p + "': ERROR - " + str(e))
            if not found:
                print("\n  RESULT: None of the test passwords match.")
                print("  The stored password is unknown. Use --reset to set a new one.")

    # Check for similar emails (duplicates or typos)
    result2 = conn.execute(text(
        "SELECT work_email, "
        "CASE WHEN password_hash IS NOT NULL THEN 'has_pw' ELSE 'no_pw' END as pw, "
        "is_active, account_locked "
        "FROM employees WHERE work_email ILIKE '%trilok%' OR work_email ILIKE '%kambham%'"
    ))
    similar = result2.fetchall()
    if similar:
        print("\nAll similar emails in DB:")
        for s in similar:
            print("  " + str(dict(s._mapping)))

print("\n" + "=" * 60)

# ─── Password Reset Mode ──────────────────────────────────────
if reset_mode:
    if not new_password:
        print("ERROR: provide the new password after --reset")
        sys.exit(1)

    print("\nResetting password for: " + TARGET_EMAIL)
    print("New password:           " + "*" * len(new_password))

    new_hash = hash_password(new_password)
    print("New hash prefix:        " + new_hash[:7])

    db = SessionLocal()
    try:
        from app.models.employee import Employee
        from datetime import datetime
        emp = db.query(Employee).filter(Employee.work_email == TARGET_EMAIL).first()
        if not emp:
            print("ERROR: Employee not found")
            sys.exit(1)
        emp.password_hash = new_hash
        emp.password_changed_at = datetime.utcnow()
        emp.force_password_change = False
        emp.failed_login_attempts = 0
        emp.account_locked = False
        db.commit()

        # Verify immediately
        reloaded = db.query(Employee).filter(Employee.work_email == TARGET_EMAIL).first()
        ok = verify_password(new_password, reloaded.password_hash)
        if ok:
            print("SUCCESS: Password updated and verified. Login should work now.")
        else:
            print("ERROR: Password was saved but verification failed. Check bcrypt.")
    finally:
        db.close()

---
name: security-audit
description: This skill should be used when the user asks to "run a security audit", "security test", "security review", "check for vulnerabilities", "pentest", "find security issues", "harden the app", "is the app secure", "OWASP check", or any mention of security testing, vulnerability scanning, or enterprise security compliance for this application.
version: 1.0.0
---

# Reknew Orbit — Full Security Audit Skill

This skill runs a complete enterprise-grade security review of the Reknew Orbit EMS application. It covers the backend (FastAPI + PostgreSQL + SQLAlchemy), the frontend (React + Vite), the authentication system (bcrypt + TOTP + custom header auth), and the audit logging pipeline.

## Application Security Profile

Before auditing, understand what this application is:

- **Type:** Enterprise HR/EMS — handles PII, payroll data, attendance, employee records
- **Auth model:** Custom header-based (`x-user-id`, `x-user-email`, `x-user-role`, `x-user-name`) — **no real JWT yet** (mock token returned from login)
- **Roles:** `super_admin`, `hr_admin`, `manager`, `employee` — enforced at service layer
- **MFA:** TOTP via pyotp (Microsoft Authenticator compatible)
- **Passwords:** bcrypt via passlib
- **PII fields:** SSN, Aadhaar, PAN, salary, DOB, phone, address — partially encrypted
- **Audit log:** `log_audit()` in `backend/app/services/audit_service.py` with `NEVER_LOG_FIELDS` and `SENSITIVE_VALUE_FIELDS`
- **File storage:** Local disk (`uploads/` directory) — no cloud object storage yet
- **Database:** PostgreSQL via SQLAlchemy ORM (`create_all()`, no Alembic)

---

## Phase 1 — Critical Authentication Vulnerabilities

**Priority: CRITICAL. Check these first.**

### 1.1 Header Spoofing — The Most Critical Issue

The entire authorization system trusts `x-user-id`, `x-user-email`, `x-user-role` HTTP headers with no cryptographic verification.

**Check `backend/app/api/auth.py` `_actor_from_headers()`:**
```python
# Anyone can send any header value — there is no signature verification
x_user_id: str | None = Header(default=None)
```

**What to do:**
- Verify that these headers are NOT forwarded from external clients in production
- Check `backend/app/main.py` CORS configuration — are credentials allowed from unknown origins?
- Read `backend/app/core/config.py` `CORS_ORIGINS` — is it locked to the frontend origin only?
- Flag the mock JWT (`"token": "mock-jwt-token"` in `login()`) as a critical gap requiring real JWT before production
- Document: until real JWT is implemented, this app must run behind a trusted reverse proxy that strips external `x-user-*` headers

**Audit findings format:**
```
CRITICAL: Header auth has no cryptographic verification
File: backend/app/api/auth.py, _actor_from_headers()
Risk: Any user can impersonate any role by setting x-user-role: super_admin
Fix: Implement signed JWT; verify signature server-side before trusting headers
```

### 1.2 TOTP Window and Replay

Check `backend/app/services/auth_service.py` `verify_totp()`:
```python
totp.verify(code, valid_window=1)  # ±30 seconds = 90-second window
```

**Issues to check:**
- Is `valid_window=1` appropriate? (Standard is 1; window > 2 is a finding)
- Are used TOTP codes tracked to prevent replay within the same 30-second window?
- If no replay prevention: flag as MEDIUM — attacker who intercepts a code can reuse it within the same window

### 1.3 Login Lockout Bypass

Check `backend/app/services/auth_service.py` `increment_login_attempts()`:
- Does it correctly lock after exactly `MAX_LOGIN_ATTEMPTS` (default 3)?
- Is `failed_login_attempts` reset properly on successful login via `clear_login_attempts()`?
- Can an attacker bypass lockout by using the `/auth/forgot-password/initiate` flow instead?
- Is the lockout stored in the database (survives server restart) or only in memory?

Check `backend/app/api/auth.py` `RESET_INITIATE_RATE_LIMIT`:
```python
RESET_INITIATE_RATE_LIMIT: dict[str, list[datetime]] = defaultdict(list)
```
**Finding:** This is in-memory — it resets on server restart. Flag as MEDIUM.

### 1.4 Password Reset Session Security

Check `backend/app/models/password_reset.py` and `backend/app/services/auth_service.py`:
- Is `reset_token_hash` storing SHA-256 of the token (not plaintext)?
- Does `complete_reset()` verify `mfa_verified = True` before allowing password change?
- Are expired sessions (`expires_at < utcnow()`) rejected before any other check?
- Are used sessions (`used_at` is set) rejected?
- After a successful reset, are all other open sessions for that employee deleted?

### 1.5 Setup Code Strength

Check `generate_setup_code()` in `auth_service.py`:
```python
# Format: RK-{first 3 of last name}-{birth month}{last 2 of birth year}
# Example: RK-PEN-0695
```
**Finding:** This is deterministic and predictable from public information (name + approximate DOB). An attacker who knows an employee's name and rough birth year can enumerate setup codes. Flag as HIGH.

**Fix to recommend:** Add a random component (`secrets.token_hex(4)`) or make setup codes fully random and admin-distributed.

---

## Phase 2 — Authorization and Access Control (OWASP A01)

For every API route, verify the authorization check happens in the **service layer**, not just the route.

### 2.1 IDOR Checks

For every endpoint that takes an ID in the path or body, verify:
- The service fetches the object AND checks the actor owns it or has permission
- There is no path where an employee can read/modify another employee's data by guessing a UUID

**Check specifically:**
- `GET /requests/{request_id}` — can employee A view employee B's request?
- `GET /employees/{employee_id}` — can a regular employee view any employee's full profile?
- `PATCH /settings/me/{section}` — is `me` enforced server-side or taken from a param?
- `POST /auth/admin-reset-password` — does it verify actor role before fetching target?

### 2.2 Manager Self-Approval

Check `backend/app/services/requests_service.py` (when implemented):
- `approve_request()` must check `request.employee_id != actor.id`
- If missing: manager can approve their own requests → financial/attendance fraud

### 2.3 Role Normalization

Check `backend/app/services/settings_service.py` `normalize_role()`:
- Are all role comparisons going through `normalize_role()` or using raw string comparison?
- Could a role value like `"Super_Admin"` or `" super_admin"` bypass role checks?
- Grep for `role == "super_admin"` vs `normalize_role(role) == "super_admin"` — direct comparisons are a finding

```bash
# Run this check:
grep -rn 'role == ' backend/app/api/ backend/app/services/
# Every match should use normalize_role() or be in a validated context
```

### 2.4 Audit Log Viewer Access

Check `backend/app/api/audit_logs.py` `can_view_audit()`:
- Is `global_access` a real role that can be assigned? If so, document what it grants
- Can a `manager` access audit logs? Should be NO

---

## Phase 3 — Injection Vulnerabilities (OWASP A03)

### 3.1 Raw SQL in SQLAlchemy

SQLAlchemy ORM is generally safe. But `text()` calls with string interpolation are dangerous.

```bash
# Find all raw SQL text() calls:
grep -rn "text(" backend/app/ --include="*.py"
```

For each match, verify the query uses bound parameters (`:param`) not f-strings:
```python
# SAFE:
conn.execute(text("SELECT * FROM employees WHERE id = :id"), {"id": employee_id})

# UNSAFE (SQL injection):
conn.execute(text(f"SELECT * FROM employees WHERE id = '{employee_id}'"))
```

Check the debug_login.py script — it uses `text()` with bound parameters, which is correct.

### 3.2 Search Parameter Injection

Check `backend/app/api/audit_logs.py` `filtered_audit_query()`:
```python
query = query.filter(AuditLog.actor_name.ilike(f"%{actor.strip()}%"))
```
This is safe (SQLAlchemy parameterizes ilike). Verify no raw string concatenation exists in any filter.

### 3.3 File Upload Path Traversal

When file upload is implemented (requests module attachments):
- Verify filenames are sanitized before being used in `os.path.join()`
- A filename like `../../etc/passwd` or `../app/main.py` must be rejected
- Use `werkzeug.utils.secure_filename()` or equivalent
- Store files by UUID, not by original filename

---

## Phase 4 — Sensitive Data Exposure (OWASP A02)

### 4.1 Audit Log PII Leakage

Check `backend/app/services/audit_service.py`:

```python
NEVER_LOG_FIELDS = {"password", "password_hash", "otp", "token", ...}
SENSITIVE_VALUE_FIELDS = {"ssn", "aadhaar", "pan", "salary", ...}
```

**Verify:**
- Every new `log_audit()` call in new features passes through `sanitize_values()`
- The `metadata` dict in audit calls is hand-checked — `sanitize_values()` does NOT automatically clean `metadata`, only `old_values`/`new_values`
- Grep for any `metadata={"password"` or `metadata={"token"` patterns

```bash
grep -rn "metadata={" backend/app/services/ | grep -E "password|token|totp|secret|hash"
```

### 4.2 Debug Logging in Production

Check `backend/app/services/auth_service.py` `_dev_log()`:
```python
def _dev_log(msg: str) -> None:
    if settings.APP_ENV == "development":
        logger.debug("[AUTH_DEBUG] " + msg)
```
**Verify:** `APP_ENV` is set to `"production"` in the production `.env`. The debug logs include auth state (not passwords, but user IDs and lock status) — acceptable in dev, not in prod.

### 4.3 Error Response Information Leakage

Check all API error responses:
- Stack traces must never be returned in production (`FastAPI` default includes detail — verify `debug=False`)
- Generic errors for auth failures ("Invalid email or password" not "User not found")
- Check `backend/app/main.py` — is `app = FastAPI(debug=...)` set correctly per environment?

### 4.4 Temporary Password Exposure

Check `backend/app/services/auth_service.py` `admin_reset_password()`:
```python
return {
    "success": True,
    "temporary_password": temporary_password,  # Plain text in API response
}
```
**Finding:** The temporary password is returned in the API response body. This is acceptable IF:
- The connection is HTTPS only (check TLS termination config)
- The password is shown once and the admin is instructed to share it securely
- It is NOT logged in any audit event, access log, or proxy log

Verify `"temporary_password"` is in `NEVER_LOG_FIELDS` or is excluded from the audit metadata for `admin_password_reset` events.

### 4.5 PII in URL Parameters

Check all `GET` endpoints:
- Are employee IDs or emails ever passed as query parameters (visible in server access logs)?
- Auth endpoints should use POST with body, not GET with query strings

---

## Phase 5 — Security Misconfiguration (OWASP A05)

### 5.1 CORS Policy

Read `backend/app/core/config.py`:
```python
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173,...").split(",")
```

**Check:**
- Is `*` (wildcard) in any CORS origin in production? → CRITICAL finding
- Does the CORS config allow `credentials=True` with specific origins only?
- Check `backend/app/main.py` CORSMiddleware configuration

### 5.2 Database URL Exposure

Check `backend/.env` (do not read the actual values, just verify):
- Is `DATABASE_URL` committed to git? Run `git log --all --full-history -- "**/.env"`
- Is `.env` in `.gitignore`?

### 5.3 Secret Key Rotation

- Is `PII_ENCRYPTION_KEY` present and non-empty in production?
- Are TOTP secrets in the DB encrypted at rest?

### 5.4 Dependencies with Known CVEs

```bash
# Run from backend/:
pip-audit --format=json 2>/dev/null | python -m json.tool
# or:
safety check --json

# Run from project root (frontend):
npm audit --json
```

Flag any HIGH or CRITICAL CVEs in dependencies.

---

## Phase 6 — Broken Access Control in Frontend (OWASP A01)

### 6.1 Client-Side Role Gating Only

Check React pages for role checks:
```bash
grep -rn "role === " src/pages/ src/components/
grep -rn "canView\|isAdmin\|isSuperAdmin" src/
```

**For every UI-level role gate, verify the corresponding API endpoint also enforces the same gate server-side.**

A hidden button does not equal security — the API must refuse unauthorized calls.

### 6.2 Auth State Storage

Check `src/hooks/useAuth.tsx`:
- Is auth state stored in `localStorage`? → XSS risk (tokens in localStorage can be stolen by any JS on the page)
- Is it stored in an `httpOnly` cookie? → safer, but requires cookie-based auth
- Document: until real JWT + httpOnly cookies are implemented, XSS = full auth compromise

### 6.3 Route Guard Coverage

Check `src/App.tsx` or equivalent router file:
- Is every protected route wrapped in a `ProtectedRoute` component?
- Does `ProtectedRoute` check both authentication AND role?
- Is `/force-change-password` properly guarded (requires auth but not the normal protected route)?

---

## Phase 7 — Input Validation (OWASP A03)

### 7.1 Pydantic Schema Coverage

Every API endpoint that accepts a body must use a Pydantic model. Check:
```bash
# Find routes without Pydantic input validation:
grep -n "async def api_" backend/app/api/*.py | head -50
# For each, verify the function signature uses a typed schema, not raw dict
```

### 7.2 Field Length Limits

Check Pydantic schemas for `max_length` on text fields:
- Unbounded `str` fields can be used for DoS (store huge strings)
- All `Text` DB columns should have a corresponding `max_length` in their schema

```bash
grep -rn "str$\|: str " backend/app/schemas/ | grep -v "max_length\|min_length\|Field"
```

### 7.3 Numeric Bounds

For expense amounts, overtime hours, salary fields:
- Are there upper bounds? (`le=500000` for amounts)
- Are negative values rejected? (`gt=0`)

---

## Phase 8 — Cryptography

### 8.1 bcrypt Work Factor

Check `backend/app/services/auth_service.py` `hash_password()`:
```python
bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
```
`bcrypt.gensalt()` defaults to work factor 12. Verify this is current:
- Work factor < 10 → LOW finding (too fast, brute-forceable)
- Work factor 12 → acceptable
- Work factor 14+ → strong

The stored hash prefix `$2b$12$` confirms factor 12. Acceptable.

### 8.2 Reset Token Entropy

Check `generate_reset_token()`:
```python
token = secrets.token_urlsafe(32)  # 32 bytes = 256 bits
```
256 bits from `secrets` module → cryptographically secure. No finding.

### 8.3 Admin Reset Code Entropy

When `generate_admin_reset_code()` is implemented:
- Must use `secrets` module, not `random`
- Minimum 8 characters from alphanumeric charset = ~47 bits → acceptable for 15-min expiry
- Must be stored as hash (SHA-256), not plaintext

### 8.4 Setup Code Entropy

`RK-PEN-0695` has approximately 4 characters of randomness (birth month + last 2 of year):
- 12 months × 100 years = 1200 possible values per last name
- With last name known: ~1200 guesses max → brute-forceable in seconds
- **HIGH finding**: requires fix before production

---

## Phase 9 — Logging and Monitoring (OWASP A09)

### 9.1 Audit Trail Completeness

Verify these events are logged with `log_audit()`:
- [ ] Successful login
- [ ] Failed login (with IP)
- [ ] Account lockout
- [ ] Password change (self and admin-forced)
- [ ] Admin password reset
- [ ] MFA setup
- [ ] Role change
- [ ] Employee record modification (PII fields)
- [ ] Audit log viewed/exported (to detect insider threat)

### 9.2 Audit Log Tamper Protection

Check `backend/app/models/audit.py`:
- Is the `audit_logs` table insert-only? Is there any UPDATE or DELETE route for audit rows?
- Who has database-level DELETE permission on the `audit_logs` table?
- Document: without write-once storage (e.g., PostgreSQL row-level security), a compromised `super_admin` account can delete audit logs

### 9.3 Sensitive Fields Never Logged

Run this check:
```bash
grep -rn "log_audit\|_audit(" backend/app/services/ | grep -E "password|hash|token|secret|totp"
```
Any match where a sensitive field is passed as `old_values` or `new_values` without going through `sanitize_values()` is a finding.

---

## Phase 10 — Rate Limiting and DoS

### 10.1 In-Memory Rate Limits

The following rate limits are in-memory only (reset on restart):
- `RESET_INITIATE_RATE_LIMIT` in `backend/app/api/auth.py`
- `UNLOCK_REQUEST_RATE_LIMIT` (when implemented)

**Finding (MEDIUM):** In-memory rate limits are bypassed by restarting the process or by targeting multiple instances in a load-balanced deployment. Recommend Redis-backed rate limiting (e.g., `slowapi` with Redis backend) before production.

### 10.2 No Global Rate Limiter

Check `backend/app/main.py` — is there any middleware applying rate limits globally?

If no global rate limit middleware exists:
- Login endpoint is only limited by the 3-attempt lockout (per-account, not per-IP)
- An attacker can try 3 passwords on every account in the system
- Recommend: IP-level rate limit on `/auth/` endpoints (max 20 requests/minute/IP)

### 10.3 File Upload Size Limits

When file upload is implemented:
- Check that FastAPI/uvicorn enforces a max body size
- Verify the upload route rejects files > 10MB before writing to disk
- Large file uploads without size checks = disk exhaustion DoS

---

## Phase 11 — Specific Code Patterns to Grep For

Run these searches and investigate every match:

```bash
# 1. eval() or exec() usage — code injection
grep -rn "eval(\|exec(" backend/app/ src/

# 2. Shell injection via subprocess
grep -rn "subprocess\|os.system\|os.popen" backend/app/

# 3. Hardcoded secrets
grep -rn "password\s*=\s*['\"]" backend/app/ --include="*.py" | grep -v "test\|example\|hash\|dummy"
grep -rn "secret\s*=\s*['\"]" backend/app/ --include="*.py"
grep -rn "api_key\s*=\s*['\"]" backend/app/ --include="*.py"

# 4. Unsafe deserialization
grep -rn "pickle\|marshal\|yaml.load(" backend/app/

# 5. Debug endpoints left in production
grep -rn "@router.get\|@router.post" backend/app/api/ | grep -iE "debug|test|admin-only|dev"

# 6. Commented-out auth checks
grep -rn "# TODO.*auth\|# TODO.*security\|# FIXME.*auth" backend/app/

# 7. Raw string format in SQL
grep -rn "text(f\"" backend/app/

# 8. Print statements with sensitive data
grep -rn "print(" backend/app/ --include="*.py" | grep -iE "password|token|secret|hash"

# 9. JWT mock token still referenced
grep -rn "mock-jwt-token" backend/app/ src/

# 10. Frontend env vars exposed to client
grep -rn "process.env\." src/ | grep -v "VITE_"
# (only VITE_ prefixed vars are safe to expose to browser)
```

---

## Phase 12 — Data Protection and Privacy

### 12.1 PII Field Inventory

The following fields contain PII and must be protected:
- `employees.personal_email`, `employees.phone`, `employees.date_of_birth`
- `employees.emergency_contact_phone`, `employees.emergency_contact_name`
- `employees.current_address`, `employees.permanent_address`
- Any salary/compensation fields

Check:
- Do API responses expose PII fields to roles that don't need them? (e.g., does an `employee` role user get to see colleague's DOB via any API?)
- Are PII fields masked in audit logs? (Verified via `SENSITIVE_VALUE_FIELDS` and `ADDRESS_FIELDS` in `audit_service.py`)
- Are the `*_encrypted` shadow columns actually populated and used, or are they empty placeholders?

```bash
grep -rn "_encrypted" backend/app/services/ backend/app/api/
# If no results: PII encryption fields exist in the model but are never written — document as finding
```

### 12.2 Least Privilege API Responses

For `GET /employees/{id}`, check what fields are returned to each role:
- `employee` role should NOT see: salary, bank details, SSN, other employees' personal emails
- `manager` role should see: their direct reports' work info, NOT personal PII
- Serialization function must filter fields by role, not just return the full model

---

## Audit Output Format

For each finding, produce a structured report entry:

```
SEVERITY: CRITICAL | HIGH | MEDIUM | LOW | INFO

Title: [Short description]
File: [path/to/file.py:line_number]
Category: [OWASP category or custom]

Issue:
[What the vulnerability is and why it matters]

Evidence:
[Code snippet or grep output showing the issue]

Risk:
[What an attacker can do if this is exploited]

Fix:
[Specific code change or configuration required]

Fix Priority: [Before production / Before public launch / Post-launch hardening]
```

---

## Final Report Structure

After completing all phases, produce a report with these sections:

1. **Executive Summary** — 3-5 sentences, total findings by severity
2. **Critical Findings** — must fix before any production deployment
3. **High Findings** — fix before public launch
4. **Medium Findings** — fix within 30 days of launch
5. **Low / Informational** — best-practice improvements
6. **Architecture Risk Note** — the mock JWT situation and what it means for deployment readiness
7. **Recommended Hardening Roadmap** — ordered list of the 10 most impactful changes

---

## What This Skill Does NOT Cover

- Network-level security (firewall rules, VPC, TLS termination) — infrastructure team responsibility
- Third-party service security (PostgreSQL hardening, OS-level) — ops responsibility
- Social engineering / phishing — out of scope for code review
- Penetration testing with active exploitation — this is a static code and configuration review only

# Reknew Orbit QA Test Pack

This pack covers completed phases:

1. Employee Management foundation
2. Leave Management
3. Timesheets
4. Allocations
5. Timesheet vs Allocation Compliance
6. Dashboard and Metrics
7. Approval Workflows
8. Attendance / Clock In-Out
9. Sidebar Profile + Settings/Theme Preferences
10. Audit Logs / Activity Center

## Files

- `TEST_DATA.sql`: PostgreSQL seed data for QA.
- `API_TEST_CASES.md`: Backend endpoint and database validation tests.
- `UI_TEST_CASES.md`: Browser workflow and visual behavior tests.
- `QA_CHECKLIST.md`: Release checklist and sign-off template.

## Test Roles

| Role | Email | Primary usage |
|---|---|---|
| Super Admin | `qa.superadmin@reknew.ai` | Admin dashboards, employees, audit export, policy/admin operations |
| HR Admin | `qa.hr@reknew.ai` | Time off admin, leave balances, audit viewing |
| Manager | `qa.manager@reknew.ai` | Timesheet and leave approvals |
| Employee | `qa.trilok@reknew.ai` | Employee portal workflows |
| Trainee | `qa.neha@reknew.ai` | First-login and missing emergency contact scenarios |

## Test Data Coverage

Seed script creates:

- 1 Super Admin
- 1 HR Admin
- 1 Manager
- 5 employees
- Departments and designations
- Projects
- Allocations
- Leave types and balances
- Approved, pending, and rejected leave requests
- Attendance records and correction request
- Draft/submitted/approved timesheet entries
- Notifications and action inbox records
- User settings and preferences
- Activity logs and centralized audit logs

## Execution Order

1. Restore or create a clean QA database.
2. Apply application migrations/table creation.
3. Run `docs/testing/TEST_DATA.sql`.
4. Start backend and frontend.
5. Run API smoke tests.
6. Run UI tests by role.
7. Run edge-case/security tests.
8. Capture failures with screenshot, request payload, response body, and DB query evidence.

## Global Acceptance Criteria

- No completed workflow uses dummy values.
- All primary buttons either work or are intentionally hidden/disabled with a clear reason.
- Role-based access is enforced by backend and frontend.
- Employee ownership is enforced by backend.
- Leave, timesheet, allocation, attendance, settings, and audit records persist correctly.
- Approved records are locked where business rules require locking.
- Manager/admin approvals create employee-facing notifications.
- Sensitive actions create audit logs with actor, action, entity, old/new values where applicable, reason, and timestamp.

## Edge Cases

| Area | Edge case | Expected behavior | Priority |
|---|---|---|---|
| Leave | Sick Leave future date | Blocked server-side and UI-side | P0 |
| Leave | Insufficient balance | Submission blocked; balance unchanged | P0 |
| Leave | End date before start date | Validation error | P0 |
| Leave | Employee submits leave for another employee by payload tampering | Backend rejects | P0 |
| Timesheet | Weekend hours | Blocked | P0 |
| Timesheet | Break hours counted as overtime | Must not happen; only working codes count toward overtime | P0 |
| Timesheet | Approved week edited/reset/deleted | Blocked | P0 |
| Timesheet | Working hours greater than allocation | Compliance warning/report flags variance | P0 |
| Attendance | Duplicate clock-in | Blocked | P0 |
| Attendance | Checkout without check-in | Blocked | P0 |
| Attendance | Check-in again after checkout | Blocked unless admin correction/reopen policy exists | P0 |
| Auth/RBAC | Employee accesses admin page/API | Frontend hides; backend returns 403 | P0 |
| Employee | Employee changes role/work location via DevTools | Backend rejects restricted fields | P0 |
| Settings | Theme changed then refresh | Theme persists | P1 |
| Audit | HR exports audit CSV | Backend returns 403 | P0 |
| Audit | Date filters | Results constrained correctly by created_at range | P1 |

## Manual DB Verification Queries

```sql
SELECT role, COUNT(*) FROM employees GROUP BY role ORDER BY role;
SELECT status, COUNT(*) FROM leave_requests GROUP BY status;
SELECT status, COUNT(*) FROM timesheet_entries GROUP BY status;
SELECT status, COUNT(*) FROM attendance GROUP BY status;
SELECT action, COUNT(*) FROM audit_logs GROUP BY action ORDER BY action;
```

## Defect Severity Guide

| Severity | Meaning | Example |
|---|---|---|
| Blocker | Prevents core workflow or security boundary | Employee can approve own leave |
| Critical | Data corruption or incorrect payroll/compliance outcome | Break counted as overtime |
| Major | Workflow works but key information/action missing | Approved timesheet not locked |
| Minor | Visual or copy issue without functional impact | Alignment gap in a card |
| Trivial | Cosmetic polish | Hover state mismatch |

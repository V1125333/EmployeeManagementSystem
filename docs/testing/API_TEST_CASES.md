# Backend API Test Cases

Use the seed data from `docs/testing/TEST_DATA.sql`. Header examples:

```http
x-user-email: qa.superadmin@reknew.ai
x-user-role: super_admin
x-user-name: Super Admin
```

Use employee headers for ownership tests:

```http
x-user-email: qa.trilok@reknew.ai
x-user-role: employee
x-user-name: Trilok Sai Kambham
```

## Employee Management

| ID | Scenario | Preconditions | Endpoint | Method | Request body | Expected response | Expected DB result | Priority |
|---|---|---|---|---|---|---|---|---|
| API-EMP-001 | List employees | Super Admin exists | `/api/v1/employees/` | GET | N/A | `200`, employees returned | No DB change | P0 |
| API-EMP-002 | Search full name | Seed has Trilok Sai Kambham | `/api/v1/employees/?search=Trilok%20Sai` | GET | N/A | `200`, Trilok returned | No DB change | P0 |
| API-EMP-003 | Create employee | Super Admin headers | `/api/v1/employees/` | POST | `{"first_name":"Riya","last_name":"Nair","work_email":"riya.nair@reknew.ai","country_code":"+91","phone":"9876500001","date_of_birth":"1999-02-11","workforce_type":"full_time","role":"employee","department":"Engineering","designation":"AI Developer","reporting_manager":"David Park","joining_date":"2026-06-25","work_location":"Onshore"}` | `200/201`, employee id/setup code | `employees` row created, audit log created | P0 |
| API-EMP-004 | Update manager/location as admin | Employee exists | `/api/v1/employees/00000000-0000-0000-0000-000000000004` | PUT | `{"reporting_manager":"David Park","work_location":"Remote"}` | `200`, updated fields | `employees.updated_at` and audit row updated | P0 |
| API-EMP-005 | Employee cannot update role | Employee headers | `/api/v1/employees/00000000-0000-0000-0000-000000000004` | PUT | `{"role":"super_admin"}` | `403` | No role change | P0 |
| API-EMP-006 | Export employee CSV | Super Admin headers | `/api/v1/employees/export?format=basic` | GET | N/A | `200`, CSV content | No DB change, audit if implemented | P1 |

## Leave Management

| ID | Scenario | Preconditions | Endpoint | Method | Request body | Expected response | Expected DB result | Priority |
|---|---|---|---|---|---|---|---|---|
| API-LEV-001 | Get leave summary | Employee headers | `/api/v1/leaves/me/summary` | GET | N/A | `200`, balances and requests | No DB change | P0 |
| API-LEV-002 | Submit future casual leave | Employee has balance | `/api/v1/leaves/me/requests` | POST | `{"leave_type_id":"00000000-0000-0000-0000-000000000301","start_date":"2026-07-10","end_date":"2026-07-10","reason":"Personal appointment"}` | `200/201`, status pending | `leave_requests.status='pending'`, manager inbox/notification created | P0 |
| API-LEV-003 | Reject future sick leave | Sick leave policy blocks future dates | `/api/v1/leaves/me/requests` | POST | `{"leave_type_id":"00000000-0000-0000-0000-000000000302","start_date":"2026-07-10","end_date":"2026-07-10","reason":"Future sick leave"}` | `400/422` validation error | No leave request row | P0 |
| API-LEV-004 | Approve leave | Pending leave exists | `/api/v1/leaves/approvals/00000000-0000-0000-0000-000000000702/decision` | POST | `{"decision":"approved","notes":"Approved"}` | `200`, approved | `leave_requests.status='approved'`, balance pending/used updates, audit log | P0 |
| API-LEV-005 | Reject leave requires reason | Pending leave exists | `/api/v1/leaves/approvals/{request_id}/decision` | POST | `{"decision":"rejected","notes":""}` | `400/422` | Leave remains pending | P0 |
| API-LEV-006 | Employee cannot approve own leave | Employee headers | `/api/v1/leaves/approvals/00000000-0000-0000-0000-000000000702/decision` | POST | `{"decision":"approved","notes":"Self approve"}` | `403` | No status change | P0 |
| API-LEV-007 | Update draft leave | Draft request created | `/api/v1/leaves/me/requests/{request_id}` | PUT | `{"reason":"Updated reason"}` | `200` | Draft row updated, audit log | P1 |
| API-LEV-008 | Delete draft leave | Draft request created | `/api/v1/leaves/me/requests/{request_id}` | DELETE | N/A | `200/204` | Draft removed/cancelled only | P1 |

## Timesheets

| ID | Scenario | Preconditions | Endpoint | Method | Request body | Expected response | Expected DB result | Priority |
|---|---|---|---|---|---|---|---|---|
| API-TMS-001 | Get week | Employee headers | `/api/v1/timesheets/me/week?week_start=2026-06-07` | GET | N/A | `200`, approved entries | No DB change | P0 |
| API-TMS-002 | Save draft week | Week not approved | `/api/v1/timesheets/me/week` | POST | `{"week_start":"2026-06-14","entries":[{"work_date":"2026-06-16","entry_code":"PRJ","project_id":"00000000-0000-0000-0000-000000000501","project_name":"Analytics Dashboard","start_time":"09:00","end_time":"13:00","notes":"QA work"}]}` | `200`, status draft | `timesheet_entries` upserted | P0 |
| API-TMS-003 | Submit week | Draft exists | `/api/v1/timesheets/me/week/submit` | POST | `{"week_start":"2026-06-14"}` | `200`, submitted | Status submitted, submitted_at set, manager inbox/audit | P0 |
| API-TMS-004 | Approve timesheet | Manager headers, submitted week | `/api/v1/timesheets/approvals/00000000-0000-0000-0000-000000000004/2026-06-14/decision` | POST | `{"decision":"approved","notes":"Approved"}` | `200` | All week rows approved, reviewed fields set, notification/audit | P0 |
| API-TMS-005 | Reject timesheet requires note | Manager headers | `/api/v1/timesheets/approvals/{employee_id}/{week_start}/decision` | POST | `{"decision":"rejected","notes":""}` | `400/422` | Week remains submitted | P0 |
| API-TMS-006 | Cannot edit approved week | Employee headers, approved week | `/api/v1/timesheets/me/week` | POST | Approved week payload | `400/403` | Approved entries unchanged | P0 |
| API-TMS-007 | Overtime warning calculation | Paid intern, >20 working hours | `/api/v1/timesheets/me/week` | POST | Week with 24 PRJ hours and BRK hours | `200`, overtime field/warning | Working overtime stored; break excluded from overtime | P0 |
| API-TMS-008 | Weekend blocked | Week has Saturday/Sunday | `/api/v1/timesheets/me/week` | POST | Entry on Saturday | `400/422` | No weekend entry created | P0 |
| API-TMS-009 | Recall submitted week | Week submitted, not approved | `/api/v1/timesheets/me/week/recall` | POST | `{"week_start":"2026-06-14"}` | `200`, draft | Week rows status draft, audit log | P1 |
| API-TMS-010 | Delete draft week | Draft week exists | `/api/v1/timesheets/me/week?week_start=2026-06-14` | DELETE | N/A | `200` | Draft entries deleted; submitted/approved blocked | P1 |

## Allocations and Compliance

| ID | Scenario | Preconditions | Endpoint | Method | Request body | Expected response | Expected DB result | Priority |
|---|---|---|---|---|---|---|---|---|
| API-ALC-001 | Create allocation | Admin/manager headers | `/api/v1/allocations/` | POST | `{"employee_id":"00000000-0000-0000-0000-000000000006","project_id":"00000000-0000-0000-0000-000000000503","manager_id":"00000000-0000-0000-0000-000000000003","allocation_percentage":50,"allocation_role":"Trainee Developer","billing_type":"non_billable","start_date":"2026-06-20"}` | `200/201` | Allocation row and audit log | P0 |
| API-ALC-002 | Reject over-allocation | Existing 75% allocation | `/api/v1/allocations/` | POST | Allocation that exceeds policy | `400/422` or warning per policy | No invalid active allocation | P0 |
| API-ALC-003 | Update allocation | Allocation exists | `/api/v1/allocations/00000000-0000-0000-0000-000000000601` | PATCH | `{"allocation_percentage":60,"notes":"QA update"}` | `200` | Allocation updated, audit log | P1 |
| API-ALC-004 | Delete allocation | Allocation exists | `/api/v1/allocations/{allocation_id}` | DELETE | N/A | `200/204` | Row deleted/inactive, audit log | P1 |
| API-ALC-005 | Capacity summary | Employee exists | `/api/v1/allocations/employee/00000000-0000-0000-0000-000000000004/summary` | GET | N/A | `200`, allocation percent/capacity | No DB change | P1 |
| API-CMP-001 | Timesheet vs allocation compliance | Submitted/approved timesheet exists | `/api/v1/timesheets/{timesheet_id}/allocation-compliance` | GET | N/A | `200`, compliance status and variance | No DB change | P0 |
| API-CMP-002 | Detect hours greater than allocation | Intern allocation 20h, week has 24 working h | Compliance endpoint | GET | N/A | Variance/overtime flagged | No DB change | P0 |

## Attendance

| ID | Scenario | Preconditions | Endpoint | Method | Request body | Expected response | Expected DB result | Priority |
|---|---|---|---|---|---|---|---|---|
| API-ATT-001 | Get today's status | Employee headers | `/api/v1/attendance/me/today` | GET | N/A | `200`, current status | No DB change | P0 |
| API-ATT-002 | Check in | No open attendance today | `/api/v1/attendance/me/check-in` | POST | `{}` | `200`, checked in | Attendance row with check_in, status present | P0 |
| API-ATT-003 | Duplicate check in blocked | Already checked in | `/api/v1/attendance/me/check-in` | POST | `{}` | `400/409` | No duplicate active row | P0 |
| API-ATT-004 | Check out | Checked in today | `/api/v1/attendance/me/check-out` | POST | `{}` | `200`, checked out | check_out and total_hours set | P0 |
| API-ATT-005 | Checkout without checkin blocked | No open checkin | `/api/v1/attendance/me/check-out` | POST | `{}` | `400/409` | No attendance update | P0 |
| API-ATT-006 | History | Employee headers | `/api/v1/attendance/me/history` | GET | N/A | `200`, records ordered desc | No DB change | P1 |
| API-ATT-007 | Admin correction approve | Pending correction exists | `/api/v1/admin/time-off/corrections/00000000-0000-0000-0000-000000000811/decision` | POST | `{"decision":"approved","reason":"Verified with manager"}` | `200` | Attendance log updated, correction approved, audit log | P0 |
| API-ATT-008 | Start break availability | Employee checked in | Break endpoint or UI action | POST | `{}` | If break API is implemented: `200` and break started. If not implemented: route/action unavailable and no partial DB write. | Attendance/break data remains consistent | P1 |
| API-ATT-009 | End break availability | Employee on break | Break endpoint or UI action | POST | `{}` | If break API is implemented: `200` and break duration recorded. If not implemented: route/action unavailable and no partial DB write. | Break hours never inflate working hours | P1 |

## Settings, Dashboard, Audit

| ID | Scenario | Preconditions | Endpoint | Method | Request body | Expected response | Expected DB result | Priority |
|---|---|---|---|---|---|---|---|---|
| API-SET-001 | Get preferences | Auth headers | `/api/v1/settings/preferences` | GET | N/A | `200`, current prefs | No DB change | P1 |
| API-SET-002 | Update theme | Auth headers | `/api/v1/settings/preferences/appearance` | PATCH | `{"theme_mode":"light","accent_color":"blue","sidebar_collapsed":true}` | `200`, updated prefs | `user_preferences` updated, audit/activity row | P1 |
| API-DASH-001 | Dashboard KPIs | Super Admin headers | `/api/v1/dashboard/kpis` | GET | N/A | `200`, counts match seed | No DB change | P1 |
| API-AUD-001 | List audit logs | Super Admin headers | `/api/v1/audit-logs?search=timesheet&per_page=25` | GET | N/A | `200`, filtered rows | No DB change | P0 |
| API-AUD-002 | Audit date filter | Super Admin headers | `/api/v1/audit-logs?date_from=2026-06-01T00:00:00&date_to=2026-06-30T23:59:59` | GET | N/A | `200`, only range rows | No DB change | P1 |
| API-AUD-003 | Audit entity timeline | Super Admin headers | `/api/v1/audit-logs/entity/employee/00000000-0000-0000-0000-000000000004` | GET | N/A | `200`, employee audit rows | No DB change | P1 |
| API-AUD-004 | Export audit logs | Super Admin headers | `/api/v1/audit-logs/export` | GET | N/A | `200`, CSV | Audit export event created | P0 |
| API-AUD-005 | HR cannot export audit logs | HR headers | `/api/v1/audit-logs/export` | GET | N/A | `403` | Authorization failure audit row | P0 |

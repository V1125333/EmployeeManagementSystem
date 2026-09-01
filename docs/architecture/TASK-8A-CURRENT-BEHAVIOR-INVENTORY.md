# Task 8A Current Behavior Inventory

Status: characterization of the implementation at the Phase 0 baseline. This
document records behavior; it does not approve or correct known defects.

## Timesheet operations

| Operation | Actor and target | State and validation | Commit, audit, notifications, failure |
|---|---|---|---|
| Get options | Authenticated employee, self | Builds codes and active allocation/project choices; workforce type controls requirement | Read-only; no audit or notification |
| Get week | Authenticated employee, self/week | Loads all entry rows for employee/week | Read-only |
| Save draft | Employee, self/week | Replaces `draft`/`rejected` rows; rejects if any row is `submitted` or `approved`; validates code, project/allocation, calendar, leave and hours | Route commits once; `timesheet.saved`; no notification. Delete/insert is rolled back on pre-commit failure |
| Copy week | Employee, self source/target weeks | Source must exist; target cannot contain submitted/approved rows; calendar and leave validated | Route commits once; `timesheet.copied`; no notification. **Known defect:** copied project rows are not revalidated against target-date allocations |
| Submit | Employee, self/week plus submitted payload | Calls save first, then changes resulting rows to `submitted` | **Two commits:** save/audit commit, then status/audit/notifications commit. Recipients are project managers or fallback reporting manager, plus admin roles, deduplicated in memory. Failure after save leaves a draft |
| Recall | Employee, self/week | Requires at least one `submitted` row | Changes every row to draft, clears all review fields, commits; `timesheet.recalled`; fallback reporting manager notified. **Known defect:** mixed statuses are all reset |
| Delete | Employee, self/week | Rejects when any row is submitted/approved; draft/rejected and empty weeks allowed | `timesheet.deleted` and delete commit together; empty delete is still audited |
| Summary | Employee, self | Latest week by descending week start; synthesized current-week result if empty | Read-only |
| History | Employee, self | Groups row data by week | Read-only |
| Compliance | Owner, reporting manager, HR/admin | Computes report from a seed entry | GET commits an access/denial audit: `allocation_compliance_checked` or its denial form |
| Approval list | Authorized reviewer | Lists submitted weeks and filters with `can_review_timesheet` | Read-only |
| Manager decision | Manager/project manager/admin reviewer, target employee/week | Self-review denied; every row must be submitted | One commit for state, notification and central audit; response calls approval-list route |
| Admin decision | HR/admin role, target employee/week | Self-review denied; every row submitted; rejection reason required | One commit for state, legacy and central audit, and notification; response calls admin dashboard route |

## Manager and administrator decision matrix

| Concern | Manager/general route | Administrative route |
|---|---|---|
| Route | `POST /timesheets/approvals/{employee_id}/{week_start}/decision` | `POST /admin/time-off/timesheets/{employee_id}/{week_start}/decision` |
| Input | `TimesheetDecisionRequest(decision, reviewer_notes<=300)` | `DecisionPayload(decision, reason<=500)` |
| Authorization | Reporting manager, allocated project manager, or admin role via `can_review_timesheet` | HR/admin roles via `require_admin` |
| Rejection reason | Optional | Required |
| Starting state | All rows `submitted` | All rows `submitted` |
| Self-approval | 403 plus central authorization-failure audit commit | 403 without audit |
| Audit | `timesheet.approved` / `timesheet.rejected`; optional variance event | legacy `timesheet_approved/rejected` plus `admin_time_off.timesheet.approved/rejected` |
| Audit entity ID | `employee_id:week_start` | first entry ID |
| Notification | Employee; message appends reviewer note | Employee; reason is not appended |
| Response | Current approval-list payload | Current administrative dashboard payload |
| Transaction | One decision commit; denial paths may commit an audit | One decision commit; most precondition failures do not commit |
| Typical errors | 404 employee/week, 403 self/unauthorized, 400 invalid state | 404 week, 403 role/self, 400 reason/invalid state |

## Notification and action-inbox writes

| Location/event | Actor | Recipient/entity/state | Commit, audit, deduplication, failure |
|---|---|---|---|
| Timesheet submit | Employee | Project managers or fallback manager plus admins; first entry ID | Submit route second commit; timesheet audit; request-local recipient set only; failure can leave saved draft |
| Timesheet recall | Employee | Reporting manager; first entry ID | Recall commit with audit; no persistent deduplication |
| Manager/admin timesheet decision | Reviewer/admin | Employee; first entry ID | Decision commit with differing audit conventions; no deduplication |
| Inbox leave decision | Manager/admin | Leave owner; leave request ID | Mutation and notification commit together; no audit; repeated action rejected by state |
| Inbox attendance decision | Manager/admin | Correction owner; correction ID | Mutation and notification commit together; no audit; repeated action rejected by state |
| Admin time-off actions | Admin/HR | Affected employee; leave/balance/attendance/correction/timesheet entity | Mutation, legacy+central audit, notification commit together; no deduplication |
| Allocation create/update | Supplied authenticated service actor | Allocated employee; allocation ID | Service owns commit unless `commit=False`; central audit; no general deduplication |
| Allocation-ending reminders/startup job | System startup | Employee and manager; allocation ID | Helper commits its batch; query-based sequential deduplication, no unique constraint; concurrent duplicates remain possible |
| Employee requests | Employee/reviewer/payroll actor | Current reviewer, employee, or payroll; request ID | Request service commits business state, audit, notification and inbox; helpers themselves only add. Sequential identical helper calls duplicate |
| Announcements | Admin/author | Every visible employee; announcement ID | Route commit; application query deduplicates notification and pending acknowledgment item; no database uniqueness |
| Employee profile reminder | Employee/admin workflow | Employee action inbox | Route commit; older profile notifications may be removed; no canonical event boundary |
| Employee employment update | Admin | Updated employee; employee ID | Route commit with employee update/audit; direct notification insert |
| Account locked/unlock requested | Authentication flow/system | Admin roles | Calling authentication operation commits; no canonical deduplication |
| Account unlocked/rejected | Admin | Employee | Calling authentication operation commits; no canonical deduplication |
| Mark notification read/all read | Recipient | Notification rows | Route commits; owner-scoped; idempotent by value; no audit |
| Complete inbox item | Assignee | Action inbox item | Route commits; owner-scoped; no audit |
| GET inbox/count cleanup | Recipient | Completes stale profile item and deletes matching notification | **GET mutates and commits.** Count calls inbox route and inherits the side effect |

## Current failure and duplication semantics

- Most notification helpers call `db.add` and depend on their caller to commit.
- Allocation and request services contain their own commit conventions.
- Timesheet submit is the observed exception where a business operation spans two
  commits.
- Announcement and allocation-reminder deduplication is sequential query-based;
  it has no uniqueness protection against concurrent transactions.
- Request, timesheet, authentication, admin, leave, attendance and employee
  notification helpers do not share a durable deduplication key.
- Notification message and navigation fields are caller-controlled within the
  server process. Some paths bound or truncate text; others accept long free-form
  content.


# Frontend UI Test Cases

Test in Chrome/Edge at the local Vite URL. Use seeded users:

- Super Admin: `qa.superadmin@reknew.ai`
- HR: `qa.hr@reknew.ai`
- Manager: `qa.manager@reknew.ai`
- Employee: `qa.trilok@reknew.ai`

## Navigation and Layout

| ID | Screen | Steps | Expected result | Priority |
|---|---|---|---|---|
| UI-NAV-001 | Employee sidebar | Login as employee and inspect sidebar | Shows My Dashboard, Apply Leave, Approvals, Timesheets, Check In / Out, Attendance History, Requests, Documents, Company Handbook, Holidays. No duplicate My Profile link in sidebar. | P0 |
| UI-NAV-002 | Sidebar profile footer | Click profile card in sidebar | Connected dropdown opens with My Profile, Settings, Sign Out. Chevron rotates and menu is attached to card. | P0 |
| UI-NAV-003 | Profile menu keyboard | Focus profile card, press Enter/Space/Escape | Enter/Space opens menu; Escape closes; focus remains usable. | P1 |
| UI-NAV-004 | Sidebar collapse | Collapse and expand sidebar | Collapse button remains discoverable near top; navigation icons remain usable; profile footer remains clean. | P1 |
| UI-NAV-005 | Company Handbook route | Click Company Handbook | Placeholder page opens with title, subtitle, and coming soon empty state. Active nav state is correct. | P1 |

## Employee Dashboard

| ID | Screen | Steps | Expected result | Priority |
|---|---|---|---|---|
| UI-DASH-001 | My Dashboard | Load employee dashboard | Attendance, Available Leave, Timesheet, Pending Actions cards show real values, not dummy text. | P0 |
| UI-DASH-002 | Timesheet summary card | Seed multiple timesheets and load dashboard | Card shows latest week by week_end_date, status badge only, week range, approved/submitted/rejected metadata. | P0 |
| UI-DASH-003 | Timesheet card click | Click Timesheet card | Navigates to Timesheets page filtered to the displayed week. | P1 |
| UI-DASH-004 | Report Sick Today | Click quick action | Opens Apply Leave with Sick Leave selected and today's date, no future sick date selected. | P1 |
| UI-DASH-005 | Recent activity | Approve leave and timesheet as manager, return as employee | Recent Activity shows both approval events separately and in deterministic order. | P1 |
| UI-DASH-006 | Loading state | Switch between pages repeatedly | Dashboard should not flash long-lived "Loading..." values if cached data exists; errors show meaningful alert only when API fails. | P1 |

## Apply Leave

| ID | Screen | Steps | Expected result | Priority |
|---|---|---|---|---|
| UI-LEV-001 | Apply Leave | Open page as employee | Compact form and leave balance cards visible without excessive whitespace. | P0 |
| UI-LEV-002 | Leave type dropdown | Open leave type dropdown | Shows only leave types applicable to user profile/gender/workforce policy. | P0 |
| UI-LEV-003 | Sick Leave future date | Select Sick Leave and choose future date | Future dates are disabled or validation message appears; Submit disabled until fixed. | P0 |
| UI-LEV-004 | Save draft | Fill leave form and click Save Draft | Draft appears in My Leave Requests with draft status and edit/delete icon actions. | P0 |
| UI-LEV-005 | Edit draft | Click pencil icon on draft | Form loads existing draft values; user can update and submit. | P0 |
| UI-LEV-006 | Delete draft | Click trash icon on draft and confirm | Draft removed; no effect on approved requests. | P1 |
| UI-LEV-007 | Submit leave | Submit valid casual leave | Success toast; request appears pending with manager name; balance pending count updates. | P0 |
| UI-LEV-008 | Insufficient balance | Request more leave than available | Shows clear validation error and does not submit. | P0 |
| UI-LEV-009 | Approved leave display in timesheet | Create approved leave for dates in active week | Timesheet cells show approved leave hours and prevent work/break entry for those dates. | P0 |

## Timesheets

| ID | Screen | Steps | Expected result | Priority |
|---|---|---|---|---|
| UI-TMS-001 | Timesheets | Open as employee | Week starts Sunday and ends Saturday; Saturday/Sunday are greyed out. | P0 |
| UI-TMS-002 | Add task modal | Click Add Task | Centered modal/drawer opens; user selects one project/category at a time; no duplicate add controls. | P0 |
| UI-TMS-003 | Add time block | Select work item/day, add 09:00-12:00 PRJ | Cell updates to 3h and block count; totals update. | P0 |
| UI-TMS-004 | Break exclusion | Add 1h BRK each weekday plus 40h PRJ | Working remains 40h, Break 5h, overtime 0h for full-time policy; logged may include break separately. | P0 |
| UI-TMS-005 | Overtime warning | Add working hours above policy | Warning says: "You have Xh of overtime this week. Your standard limit is Yh for this week. Overtime will be sent to your manager for approval when you submit the timesheet." | P0 |
| UI-TMS-006 | No weekend entry | Try adding hours to Saturday/Sunday | No hours are saved; user sees weekend/non-working message. | P0 |
| UI-TMS-007 | Save draft persistence | Add time blocks, refresh before Save Draft | Unsaved values should not be treated as logged server data. After Save Draft, values persist. | P0 |
| UI-TMS-008 | Submit | Click Submit Timesheet | Status becomes submitted, edit controls lock except Recall Submission. Manager sees approval item. | P0 |
| UI-TMS-009 | Approved lock | Manager approves week, employee revisits | Add/reset/delete controls disabled or hidden; approved banner appears with reviewer/date. | P0 |
| UI-TMS-010 | Recall | Submitted but not approved week | Recall button returns week to draft; approved weeks cannot be recalled. | P1 |
| UI-TMS-011 | Leave day totals | Approved leave on Wed/Thu | Daily total shows leave hours separately, work total excludes work/break on leave dates. | P0 |

## Attendance / Clock In-Out

| ID | Screen | Steps | Expected result | Priority |
|---|---|---|---|---|
| UI-ATT-001 | Check In / Out | Open page before check-in | Shows ready state, Not recorded check-in/out, primary Check In button. | P0 |
| UI-ATT-002 | Check in | Click Check In | Session becomes active, timeline shows check-in time, dashboard card updates to Checked in. | P0 |
| UI-ATT-003 | Duplicate check-in UI | After check-in, inspect controls | Check In unavailable; forcing a second click should show server error if attempted. | P0 |
| UI-ATT-004 | Check out | Click Check Out | Shows checked out time and total session duration; dashboard card updates. | P0 |
| UI-ATT-005 | Re-check-in policy | After checkout, click Check In if visible | Expected policy: no second check-in for same day unless admin reopens/corrects attendance. UI and API should block. | P0 |
| UI-ATT-006 | Recent days | Complete attendance records | Recent Days card displays latest attendance with date, range, total hours. | P1 |
| UI-ATT-007 | Break controls | Inspect break action | If breaks are not implemented, show clear disabled/coming-soon state. If implemented, Start Break and End Break update timeline and exclude break from working hours. | P1 |

## Approvals and Manager Review

| ID | Screen | Steps | Expected result | Priority |
|---|---|---|---|---|
| UI-APR-001 | Manager approvals | Login as manager, open Approvals | Shows pending leave/timesheet items assigned to manager. | P0 |
| UI-APR-002 | Timesheet review modal | Click View on timesheet | Premium centered modal opens over strong backdrop; daily work/break/leave details visible; no clipping. | P0 |
| UI-APR-003 | Approve timesheet | Click Approve Timesheet | Success toast; row status updates; employee notification appears. | P0 |
| UI-APR-004 | Reject timesheet reason | Click Reject | Reason prompt required; blank reason blocked. | P0 |
| UI-APR-005 | Approve leave | Approve pending leave | Leave request status/balance/employee notification update. | P0 |

## Settings and Theme Preferences

| ID | Screen | Steps | Expected result | Priority |
|---|---|---|---|---|
| UI-SET-001 | Settings page | Open from profile dropdown | Settings sections load from API. | P1 |
| UI-SET-002 | Theme color | Change accent/theme and save | UI updates immediately and persists after refresh/login. | P0 |
| UI-SET-003 | Sidebar mode | Collapse sidebar and refresh | Preference persists and profile footer still works. | P1 |
| UI-SET-004 | Notification settings | Toggle notification preferences | Success toast; DB preference updated; no unrelated settings change. | P1 |

## Admin Dashboard, Audit Center, and Metrics

| ID | Screen | Steps | Expected result | Priority |
|---|---|---|---|---|
| UI-ADM-001 | Admin dashboard | Login as Super Admin | KPI cards show counts based on employees, attendance, leave, birthdays, anniversaries. | P0 |
| UI-ADM-002 | Search header | Type employee/project/search term | Search results or navigation behavior is functional; no dead control. | P1 |
| UI-ADM-003 | Audit Center filters | Open Audit Trail, filter by `timesheet`, source `user`, date range | Table updates, count updates, no full-page reload. | P0 |
| UI-ADM-004 | Audit detail drawer | Click audit row | Detail drawer opens with actor, entity, changed fields, old/new values, metadata. | P0 |
| UI-ADM-005 | Audit export | Click Export CSV as Super Admin | CSV downloads; export audit event created. | P0 |
| UI-ADM-006 | HR audit export blocked | Login as HR and open Audit Trail | Export hidden or disabled; direct export attempt blocked with message. | P0 |
| UI-ADM-007 | Employee admin page search | Search "Trilok Sai Kambham" | Full-name, partial, case-insensitive, extra-space search works and count says Showing N of total. | P0 |

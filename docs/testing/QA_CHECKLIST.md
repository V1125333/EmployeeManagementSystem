# QA Checklist

## Environment

- [ ] QA database created or reset.
- [ ] Application migrations/table creation completed.
- [ ] `docs/testing/TEST_DATA.sql` executed successfully.
- [ ] Backend running.
- [ ] Frontend running.
- [ ] Browser cache cleared or hard refresh performed.
- [ ] Test users and headers confirmed.

## Employee Management

- [ ] Employee list loads.
- [ ] Employee count updates with search and filters.
- [ ] Full-name search works: `Trilok`, `Sai`, `Kambham`, `Trilok Sai`, `Trilok Sai Kambham`, `  Trilok   Sai  `.
- [ ] Add employee works with valid `.ai`, `.com`, `.edu`, and other valid email domains allowed by policy.
- [ ] Edit employee uses dropdowns for role, department, manager, workforce type, status, and work location.
- [ ] Export CSV works and includes readable employee ID/country code/phone fields.
- [ ] Super Admin can view emergency contact details if present.
- [ ] Missing emergency contact shows placeholder and Send Reminder action.
- [ ] Employee cannot change restricted fields such as role, manager, and work location.

## Leave Management

- [ ] Leave balance cards show available/used/pending values.
- [ ] Leave policy notes show expiry/carry-forward clearly.
- [ ] Save Draft works.
- [ ] Draft edit works.
- [ ] Draft delete works.
- [ ] Submit request works.
- [ ] Approved requests update balance.
- [ ] Rejected requests do not reduce used balance.
- [ ] Sick Leave cannot be submitted for future dates.
- [ ] Leave dates block timesheet work/break entry.

## Timesheets

- [ ] Week starts Sunday and ends Saturday.
- [ ] Saturday/Sunday are greyed out and cannot receive hours.
- [ ] Add Task opens centered modal/drawer.
- [ ] Start/end time blocks calculate correct hours.
- [ ] Break hours are excluded from working/overtime.
- [ ] Overtime warning copy is correct.
- [ ] Save Draft is required before server persistence.
- [ ] Submit sends item to manager.
- [ ] Recall works only before approval.
- [ ] Approve/reject works for manager.
- [ ] Approved timesheet is locked for employee.
- [ ] Dashboard card shows latest week by week_end_date.

## Allocations and Compliance

- [ ] Create allocation works.
- [ ] Update allocation works.
- [ ] Delete/deactivate allocation works.
- [ ] Capacity summary is correct.
- [ ] Timesheet vs allocation compliance flags overages.
- [ ] Compliance does not count break hours as project work.

## Attendance

- [ ] Check In works.
- [ ] Duplicate Check In is blocked.
- [ ] Check Out works.
- [ ] Check Out without Check In is blocked.
- [ ] Check In after Check Out is blocked unless policy explicitly allows reopening.
- [ ] Dashboard attendance card updates.
- [ ] Attendance history shows recent records.
- [ ] Admin correction approval updates attendance log.

## Dashboard and Metrics

- [ ] Employee dashboard cards show real values.
- [ ] Admin dashboard KPI cards match database counts.
- [ ] Pending tasks show correct counts and spacing.
- [ ] Birthday and anniversary cards reveal people clearly.
- [ ] Notifications and inbox behavior is not confusing or duplicated.

## Approval Workflows

- [ ] Manager receives leave approval tasks.
- [ ] Manager receives timesheet approval tasks.
- [ ] Reject actions require reason.
- [ ] Employee receives approval/rejection notification.
- [ ] Approved records show reviewer and reviewed date.

## Sidebar Profile, Settings, Theme

- [ ] Profile is in sidebar footer, not top-right header.
- [ ] Profile dropdown is attached and polished.
- [ ] Dropdown contains My Profile, Settings, Sign Out.
- [ ] Company Handbook appears only in sidebar.
- [ ] Theme/accent persists after refresh.
- [ ] Sidebar collapsed state persists after refresh.

## Audit Logs / Activity Center

- [ ] Audit Trail visible to Super Admin/HR only.
- [ ] Employee cannot access audit APIs.
- [ ] Search filters work.
- [ ] Date filters work.
- [ ] Source/action/entity filters work.
- [ ] Detail drawer shows changed fields and metadata.
- [ ] Entity activity timeline loads on Profile and Staffing Request detail pages.
- [ ] Super Admin can export audit CSV.
- [ ] HR cannot export audit CSV.
- [ ] Auth events are logged: login, failed login, password setup/reset.

## Security Regression

- [ ] Employee cannot submit leave for another employee via payload tampering.
- [ ] Employee cannot approve/reject own requests.
- [ ] Employee cannot edit leave balance.
- [ ] Employee cannot edit approved timesheets.
- [ ] Employee cannot access admin APIs directly.
- [ ] Disabled UI controls are also enforced by backend.
- [ ] Audit log records sensitive admin actions.

## Sign-off

| Area | Owner | Status | Notes |
|---|---|---|---|
| Employee Management |  | Not Started |  |
| Leave Management |  | Not Started |  |
| Timesheets |  | Not Started |  |
| Allocations |  | Not Started |  |
| Compliance |  | Not Started |  |
| Dashboard |  | Not Started |  |
| Approvals |  | Not Started |  |
| Attendance |  | Not Started |  |
| Settings/Profile |  | Not Started |  |
| Audit Logs |  | Not Started |  |

# Reknew Orbit PII and Sensitive Data Security Findings Report

Date: 2026-06-05

## Data Classification

| Classification | Examples | Handling Rule |
| --- | --- | --- |
| Public | Company name, published announcements | No special handling beyond integrity controls |
| Internal | Department, designation, work location, project assignment | Authenticated access only |
| Restricted PII | Work email, country code, phone, DOB, gender, reporting manager | Role-based access, export controls, audit logging |
| Confidential PII | Personal email, emergency contact, address, HR documents, leave/attendance history | Role-based access, ownership checks, audit logging, encryption-ready fields |
| Regulated / Payroll | Bank, tax, SSN/PAN/Aadhaar, payroll vendor ids | Dedicated payroll export level, encryption at rest, strongest audit controls |

## Findings

| Feature | Risk | How It Can Be Misused | Current Protection Found | Required Backend Protection | Priority | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Employee list/export | Browser-built CSV can expose all loaded PII and has no audit trail | Admin exports phone/DOB without server record; DevTools can alter export fields | Admin list endpoint required admin role | Server export endpoint with export level authorization and audit logging | High | Implemented |
| Employee profile preview | Admin views sensitive profile data without sensitive-access audit | Insider can open many employee profiles undetected | Admin-only endpoint | Audit every admin sensitive profile/preview read | High | Implemented |
| HR document generation | API had no auth guard | Any caller could generate HR letters if endpoint discovered | None in endpoint | Admin/HR authorization plus audit log | High | Implemented |
| PII encryption at rest | Existing employee PII is plain columns | Database dump exposes phone, DOB, address, emergency contact | None for current fields | KMS/env-key encryption for confidential fields | High | Encryption service and encrypted placeholder columns added |
| Authentication | Login returns mock token and headers are trusted by API | User can spoof `x-user-id`/`x-user-email` if deployed as-is | Header match check for employee identity | Real signed JWT/session middleware and CSRF/origin protections | Critical | Reported; infrastructure change still required |
| Role-based navigation | Frontend hides routes | User can call admin APIs directly | Many admin APIs also check role | Continue backend role checks on every admin API | High | Mostly present; reinforced for HR docs/export |
| Leave submit/edit | User could tamper dates/employee id if backend trusted payload | Submit Sick Leave in future or for another employee | Uses current employee from auth; server date policy exists | Keep server-side policy validation | High | Already present |
| Timesheets | User could edit approved week if frontend only locked it | Re-enable buttons and submit edits | Server rejects submitted/approved edits/deletes | Keep status transition checks | High | Already present |
| Attendance | User could check in/out out of order | Force disabled buttons in DevTools | Server checks current employee and attendance state | Continue server state validation | High | Already present |
| Leave balances | Employees could edit balances if endpoint lacked role guard | Call balance update API directly | Admin time-off endpoint requires admin | Audit balance changes | High | Already present in admin flow |
| Payroll/Gusto fields | Future payroll fields could be exported accidentally | Payroll ids/tax fields leak in generic CSV | No current payroll endpoint found | Separate payroll schema/export level, encrypted fields, audit | Critical | Export level scaffold added |

## Implemented Controls

- Added `SensitiveAccessAuditLog` database model for sensitive reads and exports.
- Added encryption helpers for confidential field values using AES-GCM with `PII_ENCRYPTION_KEY`.
- Added encrypted placeholder columns for high-sensitivity employee PII and key version tracking.
- Added server-side employee CSV export endpoint with `basic`, `hr`, and `payroll` levels.
- Added backend export authorization and audit logging.
- Updated Employees UI to download CSV from the backend instead of building it in the browser.
- Added admin/HR authorization and audit logging to HR document generation.
- Added audit logging when admins open employee profile and preview details.

## Production Follow-Ups

- Replace mock token/header auth with signed JWT or secure server sessions before production.
- Store `PII_ENCRYPTION_KEY` in a managed secret system or KMS, not in source code.
- Backfill existing plaintext PII into encrypted columns with a controlled migration once the key is configured.
- Add explicit reveal flows for confidential fields with reason capture.
- Add automated API tests for role spoofing, employee ownership, export levels, and approved-timesheet locking.

# Reknew Orbit Audit Trail Findings

## Existing Audit Tables

- `employee_audit_logs`: field-level employee audit history for selected admin-sensitive fields.
- `certificate_audit_logs`: certificate issued/imported/revoked history.
- `sensitive_access_audit_logs`: sensitive profile/document/export access events.
- `activity_log`: general operational audit records, currently used mainly by admin Time Off & Attendance.
- `client_activity_logs`: client onboarding activity feed.

## Existing Services And Helpers

- `backend/app/services/security_service.py`
  - Masks and exports sensitive employee data.
  - Writes to `sensitive_access_audit_logs`.
- `backend/app/api/employees.py`
  - Writes selected employee field changes to `employee_audit_logs`.
- `backend/app/api/admin_time_off.py`
  - Local `log_audit()` helper writes time-off operations to `activity_log`.
- `backend/app/api/certificates.py`
  - Writes certificate lifecycle changes to `certificate_audit_logs`.
- `backend/app/api/client_onboarding.py`
  - Writes client module actions to `client_activity_logs`.

## What Is Already Tracked

- Selected employee role/department/manager/location changes.
- Sensitive profile previews and employee CSV exports.
- Admin time-off decisions, balance adjustments, attendance corrections, and timesheet decisions.
- Certificate issue/import/revoke actions.
- Client onboarding activity feed entries.

## What Is Missing

- No single central audit table for compliance reporting.
- Old/new values are inconsistent across modules.
- Sensitive values are not consistently masked before audit storage.
- Unauthorized attempts are mostly rejected but not consistently audited.
- Employee self-service changes, leave drafts/submissions, attendance check-in/out, timesheet saves/submits/recalls/deletes, and profile image updates are not consistently tracked.
- There is no global Audit Trail UI/API for Super Admin or HR Admin.

## Recommendations

- Keep legacy audit tables for backward compatibility.
- Add centralized append-only `audit_logs`.
- Add a reusable backend `log_audit()` service with masking, changed-field detection, metadata, source, IP, and user-agent capture.
- Wire all sensitive and business-critical actions into the central service over time.
- Expose a read-only Admin Console -> Audit Trail page for Super Admin and HR Admin only.
- Require reasons for high-risk operations such as balance adjustments, attendance corrections, role changes, deactivation, certificate revocation, and permission changes.

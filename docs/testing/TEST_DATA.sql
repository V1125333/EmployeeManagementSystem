-- Reknew Orbit QA seed data
-- Target: PostgreSQL test database
-- Safe to rerun: uses stable IDs and ON CONFLICT upserts.
-- Run only in local/dev QA databases.

BEGIN;

-- Departments
INSERT INTO departments (id, name, code, description, is_active, sort_order, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000000101', 'Engineering', 'ENG', 'Product engineering and delivery', true, 1, NOW(), NOW()),
('00000000-0000-0000-0000-000000000102', 'People Operations', 'HR', 'HR and people operations', true, 2, NOW(), NOW()),
('00000000-0000-0000-0000-000000000103', 'Product', 'PROD', 'Product management and analysis', true, 3, NOW(), NOW()),
('00000000-0000-0000-0000-000000000104', 'Sales', 'SALES', 'Client acquisition and accounts', true, 4, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, code = EXCLUDED.code, updated_at = NOW();

-- Designations
INSERT INTO designations (id, name, level, department_id, is_active, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000000201', 'Super Admin', 6, '00000000-0000-0000-0000-000000000102', true, NOW(), NOW()),
('00000000-0000-0000-0000-000000000202', 'HR Manager', 5, '00000000-0000-0000-0000-000000000102', true, NOW(), NOW()),
('00000000-0000-0000-0000-000000000203', 'Engineering Manager', 5, '00000000-0000-0000-0000-000000000101', true, NOW(), NOW()),
('00000000-0000-0000-0000-000000000204', 'AI Developer', 2, '00000000-0000-0000-0000-000000000101', true, NOW(), NOW()),
('00000000-0000-0000-0000-000000000205', 'Data Analyst', 2, '00000000-0000-0000-0000-000000000103', true, NOW(), NOW()),
('00000000-0000-0000-0000-000000000206', 'Sales Executive', 2, '00000000-0000-0000-0000-000000000104', true, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, level = EXCLUDED.level, department_id = EXCLUDED.department_id, updated_at = NOW();

-- Admin, HR, Manager, and 5 employees.
-- Password hashes are intentionally NULL; use the app setup/login flow for real auth validation.
INSERT INTO employees (
  id, first_name, last_name, work_email, personal_email, country_code, phone, date_of_birth, gender,
  department_id, designation_id, manager_id, workforce_type, workforce_status, role, employment_status,
  location, date_of_joining, onboarding_type, password_hash, is_first_login, setup_code, is_active,
  access_level, mfa_enabled, device_assigned, emergency_contact_name, emergency_contact_phone,
  emergency_contact_relation, current_address, notes, department, designation, reporting_manager,
  joining_date, work_location, created_at, updated_at, updated_by
)
VALUES
('00000000-0000-0000-0000-000000000001', 'Super', 'Admin', 'qa.superadmin@reknew.ai', NULL, '+1', '5550100001', '1988-01-12', 'male', '00000000-0000-0000-0000-000000000102', '00000000-0000-0000-0000-000000000201', NULL, 'full_time', 'internal', 'super_admin', 'active', 'Remote', '2024-01-01', 'Standard Employee', NULL, false, NULL, true, 'global', true, true, NULL, NULL, NULL, NULL, 'QA super admin', 'People Operations', 'Super Admin', '', '2024-01-01', 'Remote', NOW(), NOW(), 'seed'),
('00000000-0000-0000-0000-000000000002', 'Harper', 'Stone', 'qa.hr@reknew.ai', NULL, '+1', '5550100002', '1990-05-22', 'female', '00000000-0000-0000-0000-000000000102', '00000000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000001', 'full_time', 'internal', 'hr_admin', 'active', 'Onshore', '2024-02-01', 'Standard Employee', NULL, false, NULL, true, 'admin', true, true, NULL, NULL, NULL, NULL, 'QA HR user', 'People Operations', 'HR Manager', 'Super Admin', '2024-02-01', 'Onshore', NOW(), NOW(), 'seed'),
('00000000-0000-0000-0000-000000000003', 'David', 'Park', 'qa.manager@reknew.ai', NULL, '+1', '5550100003', '1986-09-18', 'male', '00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000203', '00000000-0000-0000-0000-000000000001', 'full_time', 'internal', 'manager', 'active', 'Remote', '2024-03-01', 'Standard Employee', NULL, false, NULL, true, 'standard', true, true, 'Mira Park', '+15550109999', 'Spouse', 'Seattle, WA', 'QA manager', 'Engineering', 'Engineering Manager', 'Super Admin', '2024-03-01', 'Remote', NOW(), NOW(), 'seed'),
('00000000-0000-0000-0000-000000000004', 'Trilok', 'Sai Kambham', 'qa.trilok@reknew.ai', 'trilok.personal@example.com', '+1', '5722082825', '2001-06-30', 'male', '00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000204', '00000000-0000-0000-0000-000000000003', 'paid_intern', 'internal', 'employee', 'active', 'Onshore', '2026-06-01', 'Standard Employee', NULL, false, NULL, true, 'standard', true, false, 'Sai Pranitha Kambham', '+18062812612', 'Sister', 'Kovvur, Andhra Pradesh', 'QA employee with leave and timesheets', 'Engineering', 'AI Developer', 'David Park', '2026-06-01', 'Onshore', NOW(), NOW(), 'seed'),
('00000000-0000-0000-0000-000000000005', 'Ananya', 'Reddy', 'qa.ananya@reknew.ai', NULL, '+91', '9876543224', '1998-11-08', 'female', '00000000-0000-0000-0000-000000000104', '00000000-0000-0000-0000-000000000206', '00000000-0000-0000-0000-000000000003', 'full_time', 'internal', 'employee', 'active', 'Offshore', '2025-01-10', 'Standard Employee', NULL, false, NULL, true, 'standard', true, true, 'Ravi Reddy', '+919876540000', 'Father', 'Hyderabad, India', 'QA employee', 'Sales', 'Sales Executive', 'David Park', '2025-01-10', 'Offshore', NOW(), NOW(), 'seed'),
('00000000-0000-0000-0000-000000000006', 'Neha', 'Gupta', 'qa.neha@reknew.ai', NULL, '+91', '9876543222', '2002-03-12', 'female', '00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000204', '00000000-0000-0000-0000-000000000003', 'trainee', 'internal', 'trainee', 'active', 'Onshore', '2026-04-01', 'Standard Employee', NULL, true, 'QA-NEHA-01', true, 'standard', false, false, NULL, NULL, NULL, 'Pune, India', 'QA trainee missing emergency contact', 'Engineering', 'AI Developer', 'David Park', '2026-04-01', 'Onshore', NOW(), NOW(), 'seed'),
('00000000-0000-0000-0000-000000000007', 'Maya', 'Patel', 'qa.maya@reknew.ai', NULL, '+1', '5550100007', '1994-08-14', 'female', '00000000-0000-0000-0000-000000000103', '00000000-0000-0000-0000-000000000205', '00000000-0000-0000-0000-000000000003', 'full_time', 'internal', 'employee', 'active', 'Remote', '2024-01-08', 'Standard Employee', NULL, false, NULL, true, 'standard', true, true, 'Arjun Patel', '+15550107777', 'Brother', 'Austin, TX', 'QA employee', 'Product', 'Data Analyst', 'David Park', '2024-01-08', 'Remote', NOW(), NOW(), 'seed'),
('00000000-0000-0000-0000-000000000008', 'Kevin', 'Wright', 'qa.kevin@reknew.ai', NULL, '+44', '7700900008', '1992-12-02', 'male', '00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000204', '00000000-0000-0000-0000-000000000003', 'contractor', 'internal', 'employee', 'inactive', 'Hybrid', '2023-10-31', 'Standard Employee', NULL, false, NULL, false, 'standard', false, true, NULL, NULL, NULL, 'London, UK', 'Inactive edge case', 'Engineering', 'AI Developer', 'David Park', '2023-10-31', 'Hybrid', NOW(), NOW(), 'seed')
ON CONFLICT (id) DO UPDATE SET
  first_name = EXCLUDED.first_name,
  last_name = EXCLUDED.last_name,
  work_email = EXCLUDED.work_email,
  role = EXCLUDED.role,
  employment_status = EXCLUDED.employment_status,
  updated_at = NOW();

-- Leave policies
INSERT INTO leave_types (
  id, name, code, description, default_days_per_year, is_paid, is_carry_forward,
  max_carry_forward_days, allow_future_dates, past_date_limit_days, future_date_warning,
  is_active, sort_order, created_at, updated_at
)
VALUES
('00000000-0000-0000-0000-000000000301', 'Casual Leave', 'CL', 'Planned personal leave', 12, true, true, 5, true, NULL, NULL, true, 1, NOW(), NOW()),
('00000000-0000-0000-0000-000000000302', 'Sick Leave', 'SL', 'Illness or medical recovery', 10, true, false, 0, false, 7, NULL, true, 2, NOW(), NOW()),
('00000000-0000-0000-0000-000000000303', 'Earned Leave', 'EL', 'Accrued annual leave', 15, true, true, 10, true, NULL, NULL, true, 3, NOW(), NOW()),
('00000000-0000-0000-0000-000000000304', 'Loss of Pay', 'LOP', 'Unpaid leave', 0, false, false, 0, true, NULL, NULL, true, 4, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, allow_future_dates = EXCLUDED.allow_future_dates, updated_at = NOW();

-- Leave balances for five employees.
INSERT INTO leave_balances (id, employee_id, leave_type_id, year, total_days, used_days, carry_forward_days, updated_by, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000301', 2026, 12, 2, 0, 'seed', NOW(), NOW()),
('00000000-0000-0000-0000-000000000402', '00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000302', 2026, 10, 0, 0, 'seed', NOW(), NOW()),
('00000000-0000-0000-0000-000000000403', '00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000301', 2026, 12, 1, 0, 'seed', NOW(), NOW()),
('00000000-0000-0000-0000-000000000404', '00000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000302', 2026, 10, 0, 0, 'seed', NOW(), NOW()),
('00000000-0000-0000-0000-000000000405', '00000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000303', 2026, 15, 3, 2, 'seed', NOW(), NOW()),
('00000000-0000-0000-0000-000000000406', '00000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000301', 2026, 12, 0, 0, 'seed', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET total_days = EXCLUDED.total_days, used_days = EXCLUDED.used_days, updated_at = NOW();

-- Projects
INSERT INTO projects (id, name, code, description, client_name, start_date, end_date, status, created_by, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000000501', 'Analytics Dashboard', 'ADB-001', 'Internal analytics dashboard', 'Reknew', '2026-05-01', NULL, 'active', '00000000-0000-0000-0000-000000000001', NOW(), NOW()),
('00000000-0000-0000-0000-000000000502', 'Mobile App MVP', 'MOB-001', 'Client mobile MVP', 'Orbit Labs', '2026-05-15', NULL, 'active', '00000000-0000-0000-0000-000000000001', NOW(), NOW()),
('00000000-0000-0000-0000-000000000503', 'Proof of Concept', 'POC-001', 'AI proof of concept', 'Reknew AI', '2026-06-01', '2026-07-15', 'active', '00000000-0000-0000-0000-000000000001', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, code = EXCLUDED.code, status = EXCLUDED.status, updated_at = NOW();

-- Allocations
INSERT INTO allocations (id, employee_id, project_id, project_name, manager_id, allocation_percentage, allocation_role, billing_type, status, start_date, end_date, notes, created_by, updated_by, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000000601', '00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000501', 'Analytics Dashboard', '00000000-0000-0000-0000-000000000003', 50, 'AI Developer', 'billable', 'active', '2026-06-01', '2026-06-30', 'Intern allocation, 20h/week expected', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', NOW(), NOW()),
('00000000-0000-0000-0000-000000000602', '00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000502', 'Mobile App MVP', '00000000-0000-0000-0000-000000000003', 100, 'Sales Support', 'non_billable', 'active', '2026-06-01', NULL, 'Full-time support allocation', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', NOW(), NOW()),
('00000000-0000-0000-0000-000000000603', '00000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000503', 'Proof of Concept', '00000000-0000-0000-0000-000000000003', 75, 'Analyst', 'billable', 'active', '2026-06-01', '2026-07-15', 'POC allocation', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET allocation_percentage = EXCLUDED.allocation_percentage, status = EXCLUDED.status, updated_at = NOW();

-- Leave requests
INSERT INTO leave_requests (id, employee_id, leave_type_id, start_date, end_date, total_days, is_half_day, reason, status, reviewed_by, reviewed_at, reviewer_notes, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000000701', '00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000301', '2026-06-03', '2026-06-04', 2, false, 'Family event', 'approved', '00000000-0000-0000-0000-000000000003', '2026-06-02 15:00:00', 'Approved', NOW(), NOW()),
('00000000-0000-0000-0000-000000000702', '00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000302', '2026-06-10', '2026-06-10', 1, false, 'Fever', 'pending', NULL, NULL, NULL, NOW(), NOW()),
('00000000-0000-0000-0000-000000000703', '00000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000303', '2026-07-01', '2026-07-05', 5, false, 'Vacation', 'rejected', '00000000-0000-0000-0000-000000000003', '2026-06-05 10:30:00', 'Project coverage required', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, reviewed_by = EXCLUDED.reviewed_by, updated_at = NOW();

-- Attendance records
INSERT INTO attendance (id, employee_id, date, check_in, check_out, total_hours, status, source, remarks, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000000801', '00000000-0000-0000-0000-000000000004', '2026-06-08', '2026-06-08 09:00:00', '2026-06-08 17:30:00', 8.50, 'present', 'system', 'Normal day', NOW(), NOW()),
('00000000-0000-0000-0000-000000000802', '00000000-0000-0000-0000-000000000004', '2026-06-09', '2026-06-09 10:15:00', '2026-06-09 17:00:00', 6.75, 'late', 'system', 'Late arrival edge case', NOW(), NOW()),
('00000000-0000-0000-0000-000000000803', '00000000-0000-0000-0000-000000000005', '2026-06-08', '2026-06-08 09:30:00', NULL, NULL, 'present', 'system', 'Checked in, not checked out', NOW(), NOW()),
('00000000-0000-0000-0000-000000000804', '00000000-0000-0000-0000-000000000007', '2026-06-08', NULL, NULL, 0, 'absent', 'manual', 'No show', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, total_hours = EXCLUDED.total_hours, updated_at = NOW();

INSERT INTO attendance_corrections (id, employee_id, attendance_id, original_check_in, original_check_out, requested_check_in, requested_check_out, reason, status, reviewed_by, reviewed_at, reviewer_notes, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000000811', '00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000802', '2026-06-09 10:15:00', '2026-06-09 17:00:00', '2026-06-09 09:15:00', '2026-06-09 17:00:00', 'Forgot to clock in on arrival', 'pending', NULL, NULL, NULL, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, updated_at = NOW();

-- Timesheets: includes an approved week, submitted week, overtime/compliance edge case, and break rows.
INSERT INTO timesheet_entries (id, employee_id, work_date, week_start, entry_code, project_id, project_name, start_time, end_time, hours, overtime_hours, overtime_requires_approval, overtime_status, notes, status, submitted_at, reviewed_by, reviewed_at, reviewer_notes, time_zone, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000000901', '00000000-0000-0000-0000-000000000004', '2026-06-08', '2026-06-07', 'PRJ', '00000000-0000-0000-0000-000000000501', 'Analytics Dashboard', '09:00:00', '12:00:00', 3, 0, false, 'none', 'Morning work', 'approved', '2026-06-12 18:00:00', '00000000-0000-0000-0000-000000000003', '2026-06-13 09:00:00', 'Approved', 'America/New_York', NOW(), NOW()),
('00000000-0000-0000-0000-000000000902', '00000000-0000-0000-0000-000000000004', '2026-06-08', '2026-06-07', 'BRK', NULL, 'Break / Non-working', '12:00:00', '13:00:00', 1, 0, false, 'none', 'Lunch', 'approved', '2026-06-12 18:00:00', '00000000-0000-0000-0000-000000000003', '2026-06-13 09:00:00', 'Approved', 'America/New_York', NOW(), NOW()),
('00000000-0000-0000-0000-000000000903', '00000000-0000-0000-0000-000000000004', '2026-06-09', '2026-06-07', 'PRJ', '00000000-0000-0000-0000-000000000501', 'Analytics Dashboard', '09:00:00', '13:00:00', 4, 0, false, 'none', 'Feature work', 'approved', '2026-06-12 18:00:00', '00000000-0000-0000-0000-000000000003', '2026-06-13 09:00:00', 'Approved', 'America/New_York', NOW(), NOW()),
('00000000-0000-0000-0000-000000000904', '00000000-0000-0000-0000-000000000004', '2026-06-15', '2026-06-14', 'PRJ', '00000000-0000-0000-0000-000000000501', 'Analytics Dashboard', '09:00:00', '18:00:00', 9, 1, true, 'pending', 'Overtime edge case', 'submitted', '2026-06-20 18:00:00', NULL, NULL, NULL, 'America/New_York', NOW(), NOW()),
('00000000-0000-0000-0000-000000000905', '00000000-0000-0000-0000-000000000005', '2026-06-08', '2026-06-07', 'PRJ', '00000000-0000-0000-0000-000000000502', 'Mobile App MVP', '09:00:00', '17:00:00', 8, 0, false, 'none', 'Submitted full day', 'submitted', '2026-06-12 18:00:00', NULL, NULL, NULL, 'Asia/Kolkata', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, hours = EXCLUDED.hours, updated_at = NOW();

-- Notifications and action inbox approval records
INSERT INTO notifications (id, user_id, title, message, type, notification_type, related_entity_type, related_entity_id, is_read, link_url, created_at)
VALUES
('00000000-0000-0000-0000-000000001001', '00000000-0000-0000-0000-000000000004', 'Timesheet approved', 'Your timesheet for Jun 7 - Jun 13 was approved by David Park.', 'timesheet', 'timesheet_approved', 'timesheet', '2026-06-07', false, '/timesheets?week=2026-06-07', NOW()),
('00000000-0000-0000-0000-000000001002', '00000000-0000-0000-0000-000000000003', 'Leave request pending', 'Ananya Reddy submitted a sick leave request.', 'leave', 'leave_request_pending', 'leave_request', '00000000-0000-0000-0000-000000000702', false, '/approvals', NOW())
ON CONFLICT (id) DO UPDATE SET is_read = EXCLUDED.is_read;

INSERT INTO action_inbox_items (id, assigned_to_user_id, item_type, title, description, status, priority, related_entity_type, related_entity_id, created_at, updated_at)
VALUES
('00000000-0000-0000-0000-000000001101', '00000000-0000-0000-0000-000000000003', 'leave_approval', 'Review sick leave', 'Ananya Reddy requested Sick Leave on Jun 10.', 'pending', 'normal', 'leave_request', '00000000-0000-0000-0000-000000000702', NOW(), NOW()),
('00000000-0000-0000-0000-000000001102', '00000000-0000-0000-0000-000000000003', 'timesheet_approval', 'Review overtime timesheet', 'Trilok submitted a week with overtime.', 'pending', 'urgent', 'timesheet', '2026-06-14', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, updated_at = NOW();

-- Settings/preferences
INSERT INTO user_settings (id, user_id, time_zone, date_format, default_landing_page, theme, sidebar_mode, dashboard_density, mfa_enabled, notification_company_announcements, notification_leave_updates, notification_attendance_reminders, notification_task_assignments, notification_training_notifications, notification_project_allocation_updates, profile_visibility, phone_visibility, birthday_visibility, created_by, updated_by)
VALUES
('00000000-0000-0000-0000-000000001201', '00000000-0000-0000-0000-000000000004', 'America/New_York', 'MM/DD/YYYY', 'Dashboard', 'light', 'expanded', 'comfortable', true, true, true, true, true, true, true, 'Everyone', 'Managers Only', 'Everyone', 'seed', 'seed'),
('00000000-0000-0000-0000-000000001202', '00000000-0000-0000-0000-000000000001', 'America/New_York', 'MM/DD/YYYY', 'Dashboard', 'light', 'expanded', 'comfortable', true, true, true, true, true, true, true, 'Everyone', 'HR Only', 'Everyone', 'seed', 'seed')
ON CONFLICT (user_id) DO UPDATE SET theme = EXCLUDED.theme, sidebar_mode = EXCLUDED.sidebar_mode, updated_by = 'seed';

INSERT INTO user_preferences (id, user_id, theme_mode, accent_color, sidebar_collapsed, compact_mode, timezone, date_format, default_landing_page, language, email_notif_leave_approved, email_notif_leave_rejected, email_notif_timesheet_approved, email_notif_timesheet_rejected, email_notif_allocation_changes, inapp_notifications_enabled)
VALUES
('00000000-0000-0000-0000-000000001301', '00000000-0000-0000-0000-000000000004', 'light', 'olive', false, false, 'America/New_York', 'MM/DD/YYYY', 'Dashboard', 'en-US', true, true, true, true, true, true),
('00000000-0000-0000-0000-000000001302', '00000000-0000-0000-0000-000000000001', 'light', 'blue', false, false, 'America/New_York', 'MM/DD/YYYY', 'Dashboard', 'en-US', true, true, true, true, true, true)
ON CONFLICT (user_id) DO UPDATE SET theme_mode = EXCLUDED.theme_mode, accent_color = EXCLUDED.accent_color, sidebar_collapsed = EXCLUDED.sidebar_collapsed;

-- Legacy activity log and centralized audit log
INSERT INTO activity_log (id, actor_id, action, target_type, target_id, description, metadata_json, ip_address, created_at)
VALUES
('00000000-0000-0000-0000-000000001401', '00000000-0000-0000-0000-000000000003', 'leave_approved', 'leave_request', '00000000-0000-0000-0000-000000000701', 'David Park approved Trilok leave request.', '{"status":"approved"}', '127.0.0.1', NOW()),
('00000000-0000-0000-0000-000000001402', '00000000-0000-0000-0000-000000000004', 'timesheet_submitted', 'timesheet', '2026-06-14', 'Trilok submitted timesheet with overtime.', '{"week_start":"2026-06-14"}', '127.0.0.1', NOW())
ON CONFLICT (id) DO UPDATE SET description = EXCLUDED.description;

INSERT INTO audit_logs (id, actor_user_id, actor_name, actor_role, action, entity_type, entity_id, old_values, new_values, changed_fields, reason, metadata_json, source, ip_address, user_agent, created_at)
VALUES
('00000000-0000-0000-0000-000000001501', '00000000-0000-0000-0000-000000000003', 'David Park', 'manager', 'leave_request.approved', 'leave_request', '00000000-0000-0000-0000-000000000701', '{"status":"pending"}', '{"status":"approved"}', '{"status":{"old":"pending","new":"approved"}}', 'Valid planned leave', '{"approval_level":"manager"}', 'admin', '127.0.0.1', 'qa-seed', NOW()),
('00000000-0000-0000-0000-000000001502', '00000000-0000-0000-0000-000000000004', 'Trilok Sai Kambham', 'employee', 'timesheet.submitted', 'timesheet', '2026-06-14', '{"status":"draft"}', '{"status":"submitted"}', '{"status":{"old":"draft","new":"submitted"}}', NULL, '{"week_start":"2026-06-14","overtime_hours":1}', 'user', '127.0.0.1', 'qa-seed', NOW()),
('00000000-0000-0000-0000-000000001503', '00000000-0000-0000-0000-000000000001', 'Super Admin', 'super_admin', 'employee.updated', 'employee', '00000000-0000-0000-0000-000000000004', '{"work_location":"Remote"}', '{"work_location":"Onshore"}', '{"work_location":{"old":"Remote","new":"Onshore"}}', 'Corrected HR data', '{"security_event":false}', 'admin', '127.0.0.1', 'qa-seed', NOW())
ON CONFLICT (id) DO UPDATE SET action = EXCLUDED.action, changed_fields = EXCLUDED.changed_fields;

COMMIT;

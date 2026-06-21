-- Phase 8: User Settings, Preferences & Theme Management
-- Existing deployments must run this manually because the app uses SQLAlchemy
-- create_all(), which creates missing tables but does not alter live schemas.

CREATE TABLE IF NOT EXISTS user_preferences (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL UNIQUE REFERENCES employees(id) ON DELETE CASCADE,
  theme_mode VARCHAR(20) NOT NULL DEFAULT 'light',
  accent_color VARCHAR(30) NOT NULL DEFAULT 'olive',
  sidebar_collapsed BOOLEAN NOT NULL DEFAULT FALSE,
  compact_mode BOOLEAN NOT NULL DEFAULT FALSE,
  timezone VARCHAR(60) NOT NULL DEFAULT 'Asia/Kolkata',
  date_format VARCHAR(20) NOT NULL DEFAULT 'DD/MM/YYYY',
  default_landing_page VARCHAR(50) NOT NULL DEFAULT 'Dashboard',
  language VARCHAR(20) NOT NULL DEFAULT 'en-US',
  email_notif_leave_approved BOOLEAN NOT NULL DEFAULT TRUE,
  email_notif_leave_rejected BOOLEAN NOT NULL DEFAULT TRUE,
  email_notif_timesheet_approved BOOLEAN NOT NULL DEFAULT TRUE,
  email_notif_timesheet_rejected BOOLEAN NOT NULL DEFAULT TRUE,
  email_notif_allocation_changes BOOLEAN NOT NULL DEFAULT TRUE,
  inapp_notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_user_preferences_user_id ON user_preferences(user_id);

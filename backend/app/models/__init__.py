"""
All database models — importing here ensures SQLAlchemy registers them.
"""

# Table 1: employees + employee intelligence tables
from app.models.employee import Employee, EmployeeAuditLog, EmployeePerformanceSnapshot

# Tables 2-3: departments, designations
from app.models.organization import Department, Designation

# Tables 4-8: leave_types, leave_balances, leave_requests, attendance, attendance_corrections
from app.models.leave_attendance import (
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    Attendance,
    AttendanceCorrection,
)

# Tables 9-11: onboarding_tasks, trainings, training_enrollments
from app.models.training import OnboardingTask, Training, TrainingEnrollment

# Tables 12-15: channels, channel_members, messages, message_reactions
from app.models.chat import Channel, ChannelMember, Message, MessageReaction

# Resource allocation foundation
from app.models.allocation import Allocation

# Staffing requests and candidate matches
from app.models.staffing_request import StaffingRequest, StaffingRequestCandidate

# Tables 16-19+: projects, allocations, announcements, notifications, activity_log
from app.models.operations import (
    Project,
    TimesheetEntry,
    Announcement,
    AnnouncementAudience,
    AnnouncementAcknowledgment,
    AnnouncementRead,
    Notification,
    ActionInboxItem,
    ActivityLog,
)

# User preference and support tables
from app.models.settings import UserSettings, SupportTicket
from app.models.user_preferences import UserPreferences

# Client onboarding tables
from app.models.client_onboarding import (
    Client,
    ClientOnboarding,
    ClientChecklistItem,
    ClientTask,
    ClientTeamMember,
    ClientDocument,
    ClientMilestone,
    ClientActivityLog,
)

# Certificate verification tables
from app.models.certificate import Certificate, CertificateAuditLog

# Sensitive data access audit
from app.models.security import SensitiveAccessAuditLog

# Centralized compliance audit trail
from app.models.audit import AuditLog

"""
All database models — importing here ensures SQLAlchemy registers them.
"""

# Table 1: employees
from app.models.employee import Employee

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

# Tables 16-19+: projects, allocations, announcements, notifications, activity_log
from app.models.operations import (
    Project,
    Allocation,
    Announcement,
    Notification,
    ActivityLog,
)

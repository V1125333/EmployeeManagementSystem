import type {
  KpiMetric,
  PendingTask,
  DepartmentCount,
  AttendancePoint,
  LeaveEntry,
  CalendarDay,
  NavItem,
} from '@/types';

// ─── KPI Metrics (realistic for 45 employees) ───
export const kpiMetrics: KpiMetric[] = [
  { label: 'Total Employees', value: '45', trend: '+2', trendUp: true, icon: 'Users', color: 'var(--color-brand-navy)' },
  { label: 'Active Employees', value: '42', trend: '+1', trendUp: true, icon: 'UserCheck', color: 'var(--color-brand-orange)' },
  { label: 'Inactive', value: '3', trend: '-1', trendUp: true, icon: 'UserX', color: 'var(--color-text-muted)' },
  { label: 'Pending Leave', value: '4', trend: '+2', trendUp: false, icon: 'Calendar', color: 'var(--color-brand-orange)' },
  { label: "Today's Attendance", value: '91%', trend: '+2.3%', trendUp: true, icon: 'CheckCircle', color: 'var(--color-brand-navy)' },
  { label: 'Upcoming Birthdays', value: '2', trend: 'this week', trendUp: null, icon: 'Cake', color: 'var(--color-brand-orange)' },
  { label: 'Work Anniversaries', value: '1', trend: 'this month', trendUp: null, icon: 'Award', color: 'var(--color-text-muted)' },
];

// ─── Pending Tasks (only 4 items for MVP) ───
export const pendingTasks: PendingTask[] = [
  { label: 'Leave Approvals', count: 4, urgent: 1, color: 'var(--color-brand-orange)' },
  { label: 'Attendance Corrections', count: 2, urgent: 0, color: 'var(--color-brand-navy)' },
  { label: 'Onboarding Tasks', count: 3, urgent: 1, color: 'var(--color-brand-orange)' },
  { label: 'Profile Updates', count: 5, urgent: 2, color: 'var(--color-text-muted)' },
];

// ─── Department Data (realistic for 45 employees) ───
export const departmentData: DepartmentCount[] = [
  { dept: 'Engineering', count: 14 },
  { dept: 'Product', count: 5 },
  { dept: 'Design', count: 4 },
  { dept: 'Marketing', count: 5 },
  { dept: 'Sales', count: 7 },
  { dept: 'Operations', count: 4 },
  { dept: 'People', count: 3 },
  { dept: 'Finance', count: 3 },
];

export const deptChartColors = [
  'var(--color-brand-navy)',
  'var(--color-brand-orange)',
  'var(--color-text-muted)',
  'var(--color-accent-mid)',
  'var(--color-brand-navy)',
  'var(--color-brand-orange)',
  'var(--color-text-muted)',
  'var(--color-accent-mid)',
];

// ─── Attendance Trend ───
export const attendanceData: AttendancePoint[] = [
  { day: '12 May', rate: 93 },
  { day: '13 May', rate: 91 },
  { day: '14 May', rate: 95 },
  { day: '15 May', rate: 89 },
  { day: '16 May', rate: 86 },
  { day: '19 May', rate: 93 },
  { day: '20 May', rate: 91 },
  { day: '21 May', rate: 95 },
  { day: '22 May', rate: 88 },
  { day: '23 May', rate: 84 },
];

// ─── On Leave Today ───
export const onLeaveToday: LeaveEntry[] = [
  { name: 'Maya Patel', type: 'Vacation', duration: 'May 14–18', avatar: 'MP' },
  { name: 'Tom Keller', type: 'Sick Leave', duration: 'May 16', avatar: 'TK' },
  { name: 'Lin Chen', type: 'Personal', duration: 'May 16–17', avatar: 'LC' },
];

export const newJoiners = [
  { name: 'Priya Rao', role: 'Product Designer', department: 'Design', startDate: 'Jun 10, 2026', avatar: 'PR' },
  { name: 'Ethan Brooks', role: 'Backend Engineer', department: 'Engineering', startDate: 'Jun 17, 2026', avatar: 'EB' },
  { name: 'Sara Khan', role: 'People Operations Associate', department: 'People', startDate: 'Jun 24, 2026', avatar: 'SK' },
];

export const activityFeed = [
  { title: 'Asha Nair submitted a leave request', time: '10 minutes ago', type: 'leave' },
  { title: 'Rahul Mehta updated his profile', time: '32 minutes ago', type: 'profile' },
  { title: 'Nina Paul completed onboarding', time: '1 hour ago', type: 'onboarding' },
  { title: 'May payroll documents were published', time: '2 hours ago', type: 'documents' },
];

export const announcements = [
  { title: 'Quarterly town hall scheduled', body: 'Join the all-hands meeting this Friday at 4 PM.', date: 'Jun 3, 2026' },
  { title: 'Updated leave policy published', body: 'The revised policy is now available in HR documents.', date: 'Jun 1, 2026' },
  { title: 'Office maintenance notice', body: 'Facilities work is planned for the weekend.', date: 'May 29, 2026' },
];

// ─── Team Leave Calendar ───
export const leaveCalendar: CalendarDay[] = Array.from({ length: 31 }, (_, i) => {
  const day = i + 1;
  const hasLeave = [2, 5, 6, 12, 14, 15, 16, 17, 18, 21, 23, 27, 28].includes(day);
  return { day, count: hasLeave ? Math.floor(Math.random() * 3) + 1 : 0 };
});

// ─── Navigation ───
export const mainNavItems: NavItem[] = [
  { key: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard', path: '/dashboard' },
  { key: 'employees', label: 'Employees', icon: 'Users', path: '/employees' },
  { key: 'onboarding', label: 'Onboarding Center', icon: 'UserPlus', path: '/onboarding' },
  { key: 'client', label: 'Client Onboarding', icon: 'Briefcase', path: '/client-onboarding' },
  { key: 'projects', label: 'Projects', icon: 'Briefcase', path: '/projects' },
  { key: 'timeoff', label: 'Time Off & Attendance', icon: 'CalendarDays', path: '/time-off' },
  { key: 'team', label: 'Team Allocation', icon: 'Network', path: '/team-allocation' },
  { key: 'assets', label: 'Assets & Access', icon: 'Package', path: '/assets' },
];

export const adminNavItems: NavItem[] = [
    { key: 'users', label: 'User Management', icon: 'Settings', path: '/admin/users' },
    { key: 'roles', label: 'Roles & Permissions', icon: 'Shield', path: '/admin/roles' },
    { key: 'policies', label: 'Policies', icon: 'FileText', path: '/admin/policies' },
    { key: 'security', label: 'Security Center', icon: 'Shield', path: '/admin/security' },
    { key: 'certificates', label: 'Certificates', icon: 'Award', path: '/admin/certificates' },
  { key: 'hr-documents', label: 'HR Documents', icon: 'Files', path: '/admin/hr-documents' },
  { key: 'audit-trail', label: 'Audit Trail', icon: 'Shield', path: '/admin/audit-trail' },
];

export const resourceNavItems: NavItem[] = [
  { key: 'bench-availability', label: 'Bench & Availability', icon: 'Users', path: '/bench' },
  { key: 'staffing-requests', label: 'Staffing Requests', icon: 'ClipboardList', path: '/staffing-requests' },
  { key: 'workforce-forecasting', label: 'Workforce Forecasting', icon: 'CalendarClock', path: '/forecasting' },
  { key: 'talent-profiles', label: 'Talent Profiles', icon: 'Award', path: '/talent-profiles' },
];

export const employeeNavItems: NavItem[] = [
  { key: 'employee-dashboard', label: 'My Dashboard', icon: 'LayoutDashboard', path: '/employee' },
  { key: 'leave', label: 'Apply Leave', icon: 'CalendarPlus', path: '/employee/apply-leave' },
  { key: 'leave-approvals', label: 'Approvals', icon: 'ClipboardCheck', path: '/employee/approvals' },
  { key: 'timesheets', label: 'Timesheets', icon: 'Clock3', path: '/employee/timesheets' },
  { key: 'check-in', label: 'Check In / Out', icon: 'LogIn', path: '/employee/check-in' },
  { key: 'requests', label: 'Requests', icon: 'Send', path: '/employee/requests' },
  { key: 'documents', label: 'Documents', icon: 'Files', path: '/employee/documents' },
  { key: 'projects', label: 'My Allocations', icon: 'Briefcase', path: '/projects' },
  { key: 'career-profile', label: 'My Career Profile', icon: 'Award', path: '/employee/career-profile' },
  { key: 'company-handbook', label: 'Company Handbook', icon: 'BookOpen', path: '/employee/company-handbook' },
  { key: 'holidays', label: 'Holidays', icon: 'PartyPopper', path: '/employee/holidays' },
];

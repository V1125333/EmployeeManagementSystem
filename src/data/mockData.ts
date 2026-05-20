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
  { label: 'Total Employees', value: '45', trend: '+2', trendUp: true, icon: 'Users', color: '#66785F' },
  { label: 'Active Employees', value: '42', trend: '+1', trendUp: true, icon: 'UserCheck', color: '#7BAE7F' },
  { label: 'Inactive', value: '3', trend: '-1', trendUp: true, icon: 'UserX', color: '#9CA3AF' },
  { label: 'Pending Leave', value: '4', trend: '+2', trendUp: false, icon: 'Calendar', color: '#D6A85F' },
  { label: "Today's Attendance", value: '91%', trend: '+2.3%', trendUp: true, icon: 'CheckCircle', color: '#7E9BB7' },
  { label: 'Upcoming Birthdays', value: '2', trend: 'this week', trendUp: null, icon: 'Cake', color: '#D97C7C' },
  { label: 'Work Anniversaries', value: '1', trend: 'this month', trendUp: null, icon: 'Award', color: '#A3B18A' },
];

// ─── Pending Tasks (only 4 items for MVP) ───
export const pendingTasks: PendingTask[] = [
  { label: 'Leave Approvals', count: 4, urgent: 1, color: '#D6A85F' },
  { label: 'Attendance Corrections', count: 2, urgent: 0, color: '#7E9BB7' },
  { label: 'Onboarding Tasks', count: 3, urgent: 1, color: '#7BAE7F' },
  { label: 'Profile Updates', count: 5, urgent: 2, color: '#A3B18A' },
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
  '#66785F', '#A3B18A', '#7E9BB7', '#D6A85F',
  '#D97C7C', '#7BAE7F', '#8B9F82', '#B8C4A8',
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

// ─── Team Leave Calendar ───
export const leaveCalendar: CalendarDay[] = Array.from({ length: 31 }, (_, i) => {
  const day = i + 1;
  const hasLeave = [2, 5, 6, 12, 14, 15, 16, 17, 18, 21, 23, 27, 28].includes(day);
  return { day, count: hasLeave ? Math.floor(Math.random() * 3) + 1 : 0 };
});

// ─── Navigation ───
export const mainNavItems: NavItem[] = [
  { key: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard', path: '/' },
  { key: 'employees', label: 'Employees', icon: 'Users', path: '/employees' },
  { key: 'onboarding', label: 'Onboarding Center', icon: 'UserPlus', path: '/onboarding' },
  { key: 'client', label: 'Client Onboarding', icon: 'Briefcase', path: '/client-onboarding' },
  { key: 'timeoff', label: 'Time Off & Attendance', icon: 'CalendarDays', path: '/time-off' },
  { key: 'team', label: 'Team Allocation', icon: 'Network', path: '/team-allocation' },
  { key: 'assets', label: 'Assets & Access', icon: 'Package', path: '/assets' },
];

export const adminNavItems: NavItem[] = [
  { key: 'users', label: 'User Management', icon: 'Settings', path: '/admin/users' },
  { key: 'roles', label: 'Roles & Permissions', icon: 'Shield', path: '/admin/roles' },
  { key: 'policies', label: 'Policies', icon: 'FileText', path: '/admin/policies' },
];

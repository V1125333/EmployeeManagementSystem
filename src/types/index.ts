// ─── Employee Types ───
export interface Employee {
  id: string;
  name: string;
  email: string;
  role: string;
  department: string;
  location: string;
  status: 'active' | 'inactive' | 'onboarding' | 'offboarding';
  avatar: string;
  joinDate: string;
  manager?: string;
  phone?: string;
}

// ─── KPI Types ───
export interface KpiMetric {
  label: string;
  value: string;
  trend: string;
  trendUp: boolean | null;
  icon: string;
  color: string;
}

// ─── Pending Task Types ───
export interface PendingTask {
  label: string;
  count: number;
  urgent: number;
  color: string;
}

// ─── Department Data ───
export interface DepartmentCount {
  dept: string;
  count: number;
}

// ─── Attendance Data ───
export interface AttendancePoint {
  day: string;
  rate: number;
}

// ─── Leave ───
export interface LeaveEntry {
  name: string;
  type: string;
  duration: string;
  avatar: string;
}

export interface CalendarDay {
  day: number;
  count: number;
}

// ─── Navigation ───
export interface NavItem {
  key: string;
  label: string;
  icon: string;
  path: string;
}

// ─── (Announcement type reserved for future) ───

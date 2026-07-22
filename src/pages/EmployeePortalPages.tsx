import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Bell,
  ArrowRight, Briefcase,
  BookOpen,
  CalendarCheck, CalendarClock, CalendarPlus, CheckCircle2, ChevronDown, ClipboardCheck,
  Clock3, Copy, Download, FileText, FolderKanban, LogIn, Pencil, Plus,
  RefreshCw, Send, Trash2, Upload, UsersRound, WalletCards, X,
} from 'lucide-react';
import { Badge, Button, Card, CardHeader } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const attendanceCache: Record<string, {
  today: AttendanceRecord | null;
  history: AttendanceRecord[];
  joiningDate: string;
}> = {};

const dashboardCache: Record<string, {
  leaveSummary: LeaveSummary | null;
  timesheetSummary: TimesheetSummary | null;
  timesheetHistory: TimesheetWeek[];
  leaveApprovalRows: LeaveRequestItem[];
  timesheetApprovalRows: TimesheetApprovalItem[];
  activeProjects: DashboardAllocation[];
  actionInboxRows: ActionInboxItem[];
  employeeContext: EmployeeDashboardContext | null;
}> = {};

interface AttendanceRecord {
  id?: string | null;
  date: string;
  check_in?: string | null;
  check_out?: string | null;
  total_hours?: number | null;
  status: string;
  is_checked_in: boolean;
}

interface TimesheetCode {
  code: string;
  label: string;
  requires_project: boolean;
}

interface TimesheetProject {
  id: string | null;
  name: string;
  code: string;
  group?: 'PROJECTS' | 'INTERNAL ACTIVITIES' | 'LEAVE ACTIVITIES' | string;
  allocation_percentage?: number | null;
  allocation_role?: string | null;
  disabled?: boolean;
}

interface GridTimesheetProject extends TimesheetProject {
  gridKey: string;
  baseKey: string;
  duplicateLabel?: string;
}

interface TimesheetEntry {
  id: string;
  work_date: string;
  entry_code: string;
  project_id: string | null;
  project_name: string;
  start_time?: string | null;
  end_time?: string | null;
  hours: number;
  overtime_hours: number;
  overtime_requires_approval: boolean;
  overtime_status: string;
  status: string;
}

interface TimesheetLeaveDay {
  date: string;
  status: string;
  leave_type: string;
  hours: number;
}

interface TimesheetWeek {
  week_start: string;
  week_end: string;
  status: string;
  submitted_at?: string | null;
  total_hours: number;
  working_hours: number;
  break_hours: number;
  leave_hours: number;
  regular_hours: number;
  overtime_hours: number;
  weekly_limit_hours: number;
  daily_limit_hours: number | null;
  warnings: string[];
  time_zone: string;
  submitted_to?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  reviewer_notes?: string | null;
  entries: TimesheetEntry[];
  leave_days: TimesheetLeaveDay[];
}

interface DashboardAllocation {
  id: string;
  project_id: string | null;
  project_name: string | null;
  project_code?: string | null;
  project_client_name?: string | null;
  project_status?: string | null;
  project_start_date?: string | null;
  project_end_date?: string | null;
  project_location?: string | null;
  manager_name: string | null;
  allocation_percentage: number;
  allocation_role: string;
  status: string;
  start_date: string;
  end_date: string | null;
  created_at?: string | null;
}

interface DashboardPerson {
  id: string;
  name: string;
  email: string;
  designation: string;
  department: string;
  profile_image_url?: string | null;
  today_status?: 'working' | 'on_leave' | 'not_checked_in';
}

interface EmployeeDashboardContext {
  employee: DashboardPerson;
  manager: DashboardPerson | null;
  direct_reports: DashboardPerson[];
}

interface TimesheetSummary {
  week_start: string;
  week_end: string;
  status: string;
  submitted_at?: string | null;
  submitted_to?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  reviewer_notes?: string | null;
  total_hours: number;
  working_hours: number;
  break_hours: number;
  leave_hours: number;
}

interface TimesheetRow {
  id: string;
  workDate: string;
  entryCode: string;
  projectKey: string;
  projectName: string;
  startTime: string;
  endTime: string;
  notes: string;
}

interface LeaveBalanceItem {
  leave_type_id: string;
  type: string;
  code: string;
  date_policy?: {
    allow_future_dates: boolean;
    past_date_limit_days?: number | null;
    future_date_warning?: string | null;
  };
  total: number;
  available: number | string;
  effective_available?: number | string;
  used: number;
  pending: number;
  is_paid: boolean;
  is_carry_forward: boolean;
  max_carry_forward_days: number;
  expiry_label: string;
}

interface LeaveRequestItem {
  id: string;
  employee_name: string;
  leave_type_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  total_days: number;
  holiday_id?: string | null;
  reason: string;
  status: string;
  reporting_manager?: string | null;
  pending_with?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  reviewer_notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface LeaveSummary {
  reporting_manager?: string | null;
  joining_date?: string | null;
  min_request_date?: string | null;
  balances: LeaveBalanceItem[];
  requests: LeaveRequestItem[];
}

interface HolidayItem {
  id: string;
  name: string;
  holiday_date: string;
  holiday_type: 'public' | 'company' | 'floating' | 'optional' | string;
  regions: string;
}

interface WorkingDaysSummary {
  working_days: number;
  weekends: number;
  holidays: number;
  holiday_names: string[];
}

interface NotificationHistoryItem {
  id: string;
  title: string;
  message?: string | null;
  type: string;
  notification_type?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  is_read: boolean;
  link_url?: string | null;
  created_at?: string | null;
}

interface ActionInboxItem {
  id: string;
  item_type: string;
  title: string;
  description?: string | null;
  employee_name?: string | null;
  status: string;
  priority: string;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  created_at?: string | null;
}

interface TimesheetApprovalItem {
  employee_id: string;
  employee_name: string;
  reporting_manager?: string | null;
  week_start: string;
  week_end: string;
  status: string;
  total_hours: number;
  working_hours: number;
  break_hours: number;
  leave_hours: number;
  regular_hours: number;
  overtime_hours: number;
  submitted_at?: string | null;
  reviewed_by?: string | null;
  reviewer_notes?: string | null;
  entries: TimesheetEntry[];
  leave_days: TimesheetLeaveDay[];
}

interface RequestApprovalItem {
  id: string;
  employee_name: string;
  ticket_number?: string | null;
  request_type: string;
  request_type_label: string;
  title: string;
  status: string;
  start_date?: string | null;
  end_date?: string | null;
  request_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  details_label?: string | null;
  reason?: string | null;
  current_owner_name?: string | null;
  pending_days?: number | null;
}

type RejectionIntent =
  | { kind: 'leave'; id: string; title: string; subtitle?: string }
  | { kind: 'timesheet'; approval: TimesheetApprovalItem; title: string; subtitle?: string }
  | { kind: 'request'; request: RequestApprovalItem; title: string; subtitle?: string };

interface ComplianceProjectRow {
  project_id?: string | null;
  project_name: string;
  allocation_percentage: number;
  expected_hours: number;
  actual_hours: number;
  variance_hours: number;
  status: 'compliant' | 'warning' | 'violation';
}

interface ComplianceReport {
  employee_id: string;
  timesheet_id: string;
  week_start: string;
  week_end: string;
  expected_weekly_hours: number;
  used_default_hours: boolean;
  no_allocations_found: boolean;
  project_rows: ComplianceProjectRow[];
  unallocated_hours: number;
  total_expected_hours: number;
  total_actual_hours: number;
  total_variance_hours: number;
  overall_status: 'compliant' | 'warning' | 'violation' | 'not_applicable';
  compliant_threshold: number;
  warning_threshold: number;
}

function useAttendance() {
  const { user } = useAuth();
  const cacheKey = user?.id || user?.email || '';
  const cachedAttendance = cacheKey ? attendanceCache[cacheKey] : undefined;
  const [today, setToday] = useState<AttendanceRecord | null>(cachedAttendance?.today ?? null);
  const [history, setHistory] = useState<AttendanceRecord[]>(cachedAttendance?.history ?? []);
  const [joiningDate, setJoiningDate] = useState(cachedAttendance?.joiningDate ?? '');
  const [loading, setLoading] = useState(!cachedAttendance);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<'check-in' | 'check-out' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const loadAttendance = useCallback(async () => {
    if (!user) return;
    const currentCache = cacheKey ? attendanceCache[cacheKey] : undefined;
    setLoading(!currentCache);
    setError(null);
    try {
      const contextRes = await fetch(`${API_BASE}/attendance/me/context`, { headers });
      if (!contextRes.ok) throw new Error('Could not load attendance date limits.');
      const contextData = await contextRes.json();
      const defaultTo = contextData.today as string;
      const thirtyDaysAgo = toDateInput(addDays(new Date(`${defaultTo}T00:00:00`), -29));
      const defaultFrom = contextData.joining_date > thirtyDaysAgo ? contextData.joining_date : thirtyDaysAgo;
      const query = new URLSearchParams({ date_from: defaultFrom, date_to: defaultTo });
      const [todayRes, historyRes] = await Promise.all([
        fetch(`${API_BASE}/attendance/me/today`, { headers }),
        fetch(`${API_BASE}/attendance/me/history?${query.toString()}`, { headers }),
      ]);
      if (!todayRes.ok) throw new Error('Could not load today\'s attendance.');
      if (!historyRes.ok) throw new Error('Could not load attendance history.');
      const todayData = await todayRes.json();
      const historyData = await historyRes.json();
      setToday(todayData);
      setHistory(historyData);
      setJoiningDate(contextData.joining_date);
      if (cacheKey) {
        attendanceCache[cacheKey] = { today: todayData, history: historyData, joiningDate: contextData.joining_date };
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load attendance.');
    } finally {
      setLoading(false);
    }
  }, [cacheKey, headers, user]);

  const loadHistory = useCallback(async (dateFrom: string, dateTo: string) => {
    setHistoryLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
      const response = await fetch(`${API_BASE}/attendance/me/history?${query.toString()}`, { headers });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || 'Could not load attendance history.');
      setHistory(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load attendance history.');
    } finally {
      setHistoryLoading(false);
    }
  }, [headers]);

  const runAction = useCallback(async (action: 'check-in' | 'check-out') => {
    setActionLoading(action);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/attendance/me/${action}`, {
        method: 'POST',
        headers,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || `Could not ${action.replace('-', ' ')}.`);
      await loadAttendance();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Attendance action failed.');
    } finally {
      setActionLoading(null);
    }
  }, [headers, loadAttendance]);

  useEffect(() => {
    loadAttendance();
  }, [loadAttendance]);

  return {
    today,
    history,
    joiningDate,
    loading,
    historyLoading,
    actionLoading,
    error,
    checkIn: () => runAction('check-in'),
    checkOut: () => runAction('check-out'),
    loadHistory,
  };
}

function parseApiDateTime(value?: string | null) {
  if (!value) return null;
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

function formatTime(value?: string | null) {
  if (!value) return 'Not recorded';
  return parseApiDateTime(value)?.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) || 'Not recorded';
}

function formatDate(value?: string | null) {
  if (!value) return 'Today';
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(value?: string | null) {
  if (!value) return '';
  return parseApiDateTime(value)?.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) || '';
}

function requestApprovalDates(row: RequestApprovalItem) {
  if (row.start_date && row.end_date) {
    return row.start_date === row.end_date
      ? formatDate(row.start_date)
      : `${formatDate(row.start_date)} - ${formatDate(row.end_date)}`;
  }
  if (row.request_date) return formatDate(row.request_date);
  return '-';
}

function requestApprovalMeta(row: RequestApprovalItem) {
  const parts = [row.details_label || row.reason].filter(Boolean);
  if (row.start_time && row.end_time) parts.push(`${row.start_time.slice(0, 5)}-${row.end_time.slice(0, 5)}`);
  return parts.join(' · ');
}

function canReviewApprovals(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return ['manager', 'super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalized);
}

function formatHours(value?: number | null) {
  if (value === null || value === undefined) return 'In progress';
  const hours = Math.floor(value);
  const minutes = Math.round((value - hours) * 60);
  return `${hours}h ${minutes}m`;
}

function formatElapsed(start?: string | null, end = new Date()) {
  if (!start) return '0h 0m';
  const startTime = parseApiDateTime(start)?.getTime() || 0;
  const endTime = end.getTime();
  const minutesTotal = Math.max(0, Math.floor((endTime - startTime) / 60000));
  const hours = Math.floor(minutesTotal / 60);
  const minutes = minutesTotal % 60;
  return `${hours}h ${minutes}m`;
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? `${value}` : `${Math.round(value * 10) / 10}`;
}

function complianceBadgeVariant(status: ComplianceReport['overall_status'] | ComplianceProjectRow['status']) {
  if (status === 'compliant') return 'success';
  if (status === 'warning') return 'warning';
  if (status === 'violation') return 'error';
  return 'neutral';
}

function complianceStatusLabel(status: ComplianceReport['overall_status'] | ComplianceProjectRow['status']) {
  return status.replace('_', ' ');
}

function signedHours(value: number) {
  if (value === 0) return '0h';
  return `${value > 0 ? '+' : ''}${formatNumber(value)}h`;
}

function attendanceLabel(today: AttendanceRecord | null) {
  if (!today?.check_in) return 'Not checked in';
  if (today.is_checked_in) return 'Checked in';
  return 'Checked out';
}

function toDateInput(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function startOfLocalWeek(value = new Date()) {
  const dateValue = new Date(value);
  const day = dateValue.getDay();
  dateValue.setDate(dateValue.getDate() - day);
  dateValue.setHours(0, 0, 0, 0);
  return dateValue;
}

function addDays(value: Date, days: number) {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return next;
}

function maxDateInput(...values: Array<string | undefined | null>) {
  return values.filter(Boolean).sort().pop() || undefined;
}

function effectiveLeaveAvailable(leave: LeaveBalanceItem) {
  if (typeof leave.effective_available === 'number') return leave.effective_available;
  if (typeof leave.total === 'number') {
    const used = typeof leave.used === 'number' ? leave.used : 0;
    const pending = typeof leave.pending === 'number' ? leave.pending : 0;
    return Math.max(leave.total - used - pending, 0);
  }
  return typeof leave.available === 'number' ? leave.available : null;
}

function isWeekendDate(value: Date | string) {
  const dateValue = typeof value === 'string' ? new Date(`${value}T00:00:00`) : value;
  const day = dateValue.getDay();
  return day === 0 || day === 6;
}

function weekLabel(weekStart: string) {
  const start = new Date(`${weekStart}T00:00:00`);
  const end = addDays(start, 6);
  const startLabel = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const endLabel = end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  return `${startLabel} - ${endLabel}`;
}

const TASK_COPY_SEPARATOR = '::copy-';

function timesheetProjectKey(project?: TimesheetProject) {
  return project?.id || project?.code || '';
}

function baseTimesheetProjectKey(key: string) {
  return key.includes(TASK_COPY_SEPARATOR) ? key.split(TASK_COPY_SEPARATOR)[0] : key;
}

function makeDuplicateTimesheetKey(baseKey: string, existingKeys: string[]) {
  let copyNumber = existingKeys.filter((key) => baseTimesheetProjectKey(key) === baseKey).length + 1;
  let candidate = `${baseKey}${TASK_COPY_SEPARATOR}${copyNumber}`;
  while (existingKeys.includes(candidate)) {
    copyNumber += 1;
    candidate = `${baseKey}${TASK_COPY_SEPARATOR}${copyNumber}`;
  }
  return candidate;
}

function makeTimesheetRow(project?: TimesheetProject, code = 'PRJ', workDate = toDateInput(new Date()), projectKey = timesheetProjectKey(project) || code): TimesheetRow {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    workDate,
    entryCode: code,
    projectKey,
    projectName: project?.name || (code === 'POC' ? 'Proof of Concept' : code === 'BRK' ? 'Break / Non-working' : 'Project work'),
    startTime: code === 'BRK' ? '12:00' : '09:00',
    endTime: code === 'BRK' ? '13:00' : '17:00',
    notes: '',
  };
}

function rowsFromTimesheet(week: TimesheetWeek, projects: TimesheetProject[]) {
  if (!week.entries.length) return [];
  return week.entries.filter((entry) => entry.entry_code !== 'BRK').map((entry) => {
    const project = entry.project_id
      ? projects.find((item) => item.id === entry.project_id)
      : projects.find((item) => item.code === entry.entry_code)
        || projects.find((item) => item.name === entry.project_name);
    return {
      id: `${entry.work_date}-${entry.entry_code}-${entry.start_time || ''}-${entry.end_time || ''}-${entry.project_id || entry.project_name}`,
      workDate: entry.work_date,
      entryCode: entry.entry_code,
      projectKey: project?.id || project?.code || entry.entry_code,
      projectName: entry.project_name,
      startTime: (entry.start_time || '09:00').slice(0, 5),
      endTime: (entry.end_time || '17:00').slice(0, 5),
      notes: '',
    };
  });
}

function timeToMinutes(value: string) {
  const [hour, minute] = value.split(':').map(Number);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return 0;
  return hour * 60 + minute;
}

function minutesToTime(value: number) {
  const bounded = Math.max(0, Math.min(value, 23 * 60 + 59));
  const hour = Math.floor(bounded / 60);
  const minute = bounded % 60;
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

function endTimeFromHours(startTime: string, hours: number) {
  return minutesToTime(timeToMinutes(startTime || '09:00') + Math.max(0, hours) * 60);
}

function timeBlockHours(row: TimesheetRow) {
  if (!row.startTime || !row.endTime || row.endTime <= row.startTime) return 0;
  return Math.round(((timeToMinutes(row.endTime) - timeToMinutes(row.startTime)) / 60) * 100) / 100;
}

function PageShell({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('animate-fade-up', className)}>
      <div className={description ? 'mb-5' : 'mb-3'}>
        <h1 className="text-2xl font-bold text-[var(--color-brand-navy)] tracking-tight mb-1">{title}</h1>
        {description && <p className="text-sm text-gray-500">{description}</p>}
      </div>
      {children}
    </div>
  );
}

const HOLIDAY_REGIONS = [
  { code: 'all', label: 'All' },
  { code: 'IN', label: 'India' },
  { code: 'AE', label: 'UAE' },
  { code: 'US', label: 'United States' },
] as const;

function holidayRegionLabel(regions: string) {
  const normalized = regions.toUpperCase();
  if (normalized.includes('ALL')) return 'Global';
  if (normalized.includes('IN')) return 'India';
  if (normalized.includes('AE')) return 'UAE';
  if (normalized.includes('US')) return 'United States';
  return regions;
}

function holidayTypeVariant(type: string): 'olive' | 'warning' | 'neutral' {
  if (type === 'company') return 'olive';
  if (type === 'floating') return 'warning';
  return 'neutral';
}

function holidayTypeLabel(type: string) {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

function HolidayCalendarContent({
  headers,
}: {
  headers: Record<string, string>;
}) {
  const [holidays, setHolidays] = useState<HolidayItem[]>([]);
  const [loadingHolidays, setLoadingHolidays] = useState(false);
  const [holidayError, setHolidayError] = useState<string | null>(null);
  const [holidayRegionFilter, setHolidayRegionFilter] = useState<'all' | 'IN' | 'AE' | 'US'>('all');

  useEffect(() => {
    let cancelled = false;
    const loadHolidays = async () => {
      setLoadingHolidays(true);
      setHolidayError(null);
      try {
        const today = toDateInput(new Date());
        const nextYear = toDateInput(addDays(new Date(`${today}T00:00:00`), 365));
        const params = new URLSearchParams({ from_date: today, to_date: nextYear });
        const res = await fetch(`${API_BASE}/holidays?${params.toString()}`, { headers });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(data?.detail || 'Could not load holidays.');
        if (!cancelled) setHolidays(data.holidays || []);
      } catch (err) {
        if (!cancelled) setHolidayError(err instanceof Error ? err.message : 'Could not load holidays.');
      } finally {
        if (!cancelled) setLoadingHolidays(false);
      }
    };
    loadHolidays();
    return () => { cancelled = true; };
  }, [headers]);

  const filteredHolidays = useMemo(() => holidays.filter((holiday) => {
    if (holidayRegionFilter === 'all') return true;
    const regions = holiday.regions.toUpperCase().split(',').map((item) => item.trim());
    return regions.includes('ALL') || regions.includes(holidayRegionFilter);
  }), [holidayRegionFilter, holidays]);

  const holidaysByMonth = useMemo(() => {
    const grouped = new Map<string, HolidayItem[]>();
    filteredHolidays.forEach((holiday) => {
      const key = new Date(`${holiday.holiday_date}T00:00:00`).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
      grouped.set(key, [...(grouped.get(key) || []), holiday]);
    });
    return Array.from(grouped.entries());
  }, [filteredHolidays]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {HOLIDAY_REGIONS.map((region) => (
          <button
            key={region.code}
            onClick={() => setHolidayRegionFilter(region.code)}
            className={cn(
              'rounded-btn border px-3 py-2 text-sm font-semibold transition-colors',
              holidayRegionFilter === region.code
                ? 'border-accent bg-accent text-white'
                : 'border-[var(--color-border)] bg-white text-gray-600 hover:border-accent/30 hover:text-accent'
            )}
          >
            {region.label}
          </button>
        ))}
      </div>
      {holidayError && (
        <div className="rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {holidayError}
        </div>
      )}
      <Card className="overflow-hidden">
        <CardHeader title="Upcoming Holidays" icon={<CalendarCheck size={17} />} />
        {loadingHolidays ? (
          <div className="px-5 py-8 text-sm text-gray-500">Loading holidays...</div>
        ) : holidaysByMonth.length === 0 ? (
          <div className="px-5 py-8 text-sm text-gray-500">No upcoming holidays for this region.</div>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {holidaysByMonth.map(([month, monthHolidays]) => (
              <div key={month} className="px-5 py-4">
                <div className="mb-3 text-xs font-bold uppercase tracking-wide text-gray-400">{month}</div>
                <div className="space-y-2">
                  {monthHolidays.map((holiday) => (
                    <div key={holiday.id} className="grid gap-3 rounded-lg border border-[var(--color-border)] bg-white px-4 py-3 text-sm md:grid-cols-[90px_1fr_140px_110px] md:items-center">
                      <div className="font-bold text-[var(--color-brand-navy)]">
                        {new Date(`${holiday.holiday_date}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </div>
                      <div className="font-semibold text-[var(--color-brand-navy)]">{holiday.name}</div>
                      <div className="text-gray-500">{holidayRegionLabel(holiday.regions)}</div>
                      <div className="md:text-right">
                        <Badge variant={holidayTypeVariant(holiday.holiday_type)}>{holidayTypeLabel(holiday.holiday_type)}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
  onClick,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <Card
      className={cn('p-5', onClick && 'cursor-pointer transition-all hover:-translate-y-0.5 hover:border-accent/30 hover:shadow-card-lg')}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(event) => {
        if (onClick && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault();
          onClick();
        }
      }}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[12px] font-semibold text-gray-500">{label}</div>
          <div className="mt-2 text-2xl font-bold text-[var(--color-brand-navy)]">{value}</div>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-light text-accent">
          {icon}
        </div>
      </div>
    </Card>
  );
}

function AllocationCompliancePanel({
  report,
  loading = false,
  open,
  onToggle,
  action,
}: {
  report: ComplianceReport | null;
  loading?: boolean;
  open: boolean;
  onToggle?: () => void;
  action?: React.ReactNode;
}) {
  if (loading) {
    return (
      <div className="rounded-lg border border-[var(--color-border)] bg-white px-4 py-3 text-sm text-gray-500">
        Checking allocation compliance...
      </div>
    );
  }
  if (!report) return null;

  const isIssue = report.overall_status === 'warning' || report.overall_status === 'violation';
  return (
    <div className={cn(
      'rounded-lg border bg-white shadow-[0_6px_18px_rgba(17,24,39,0.05)]',
      isIssue ? 'border-status-warning/30' : 'border-[var(--color-border)]'
    )}>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-bold text-[var(--color-brand-navy)]">Allocation Compliance</span>
            <Badge variant={complianceBadgeVariant(report.overall_status)}>
              {complianceStatusLabel(report.overall_status)}
            </Badge>
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Expected week: {formatNumber(report.expected_weekly_hours)}h. Compliant within {formatNumber(report.compliant_threshold)}h, warning above {formatNumber(report.compliant_threshold)}h, violation above {formatNumber(report.warning_threshold)}h.
            {report.used_default_hours ? ' Default weekly hours were used.' : ''}
          </div>
        </div>
        {onToggle && <span className="text-xs font-semibold text-accent">{open ? 'Hide' : 'Show'}</span>}
      </button>
      {open && (
        <div className="border-t border-[var(--color-border)] px-4 py-3">
          {report.no_allocations_found ? (
            <div className="rounded-lg border border-[var(--color-border)] bg-warm-bg px-4 py-3 text-sm text-gray-600">
              No active allocations were found for this week. Compliance is not applicable, but {formatNumber(report.unallocated_hours)}h were logged without an allocation.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-left text-xs">
                <thead className="bg-warm-bg text-[10px] uppercase tracking-wide text-gray-400">
                  <tr>
                    <th className="px-3 py-2 font-bold">Project</th>
                    <th className="px-3 py-2 text-right font-bold">Allocation</th>
                    <th className="px-3 py-2 text-right font-bold">Expected</th>
                    <th className="px-3 py-2 text-right font-bold">Actual</th>
                    <th className="px-3 py-2 text-right font-bold">Variance</th>
                    <th className="px-3 py-2 text-right font-bold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {report.project_rows.map((row) => (
                    <tr key={`${row.project_id || row.project_name}-${row.allocation_percentage}`}>
                      <td className="px-3 py-2 font-semibold text-[var(--color-brand-navy)]">{row.project_name}</td>
                      <td className="px-3 py-2 text-right text-gray-500">{row.allocation_percentage}%</td>
                      <td className="px-3 py-2 text-right">{formatNumber(row.expected_hours)}h</td>
                      <td className="px-3 py-2 text-right">{formatNumber(row.actual_hours)}h</td>
                      <td className={cn('px-3 py-2 text-right font-semibold', row.status !== 'compliant' && 'text-status-warning')}>{signedHours(row.variance_hours)}</td>
                      <td className="px-3 py-2 text-right"><Badge variant={complianceBadgeVariant(row.status)}>{row.status}</Badge></td>
                    </tr>
                  ))}
                  <tr className="bg-warm-bg/60">
                    <td className="px-3 py-2 font-bold text-[var(--color-brand-navy)]">Unallocated hours</td>
                    <td className="px-3 py-2 text-right text-gray-400" colSpan={3}>Logged against projects without active allocation</td>
                    <td className={cn('px-3 py-2 text-right font-bold', report.unallocated_hours > report.compliant_threshold && 'text-status-warning')}>{formatNumber(report.unallocated_hours)}h</td>
                    <td className="px-3 py-2 text-right">-</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
          {isIssue && (
            <div className="mt-3 rounded-lg border border-status-warning/20 bg-status-warning/10 px-3 py-2 text-sm text-status-warning">
              This timesheet has allocation variance. It can still be submitted or approved, but the variance will remain visible for review and audit.
            </div>
          )}
          {action && <div className="mt-3 flex justify-end gap-2">{action}</div>}
        </div>
      )}
    </div>
  );
}

function statusLabel(status?: string | null) {
  if (!status || status === 'not_started' || status === 'not_submitted') return 'Not Submitted';
  return status.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function TimesheetSummaryCard({
  summary,
  loading,
  onClick,
}: {
  summary: TimesheetSummary | null;
  loading: boolean;
  onClick: () => void;
}) {
  const status = summary ? statusLabel(summary.status) : loading ? 'Loading...' : 'Not Submitted';
  const statusVariantName: 'olive' | 'error' | 'warning' | 'neutral' = summary?.status === 'approved'
    ? 'olive'
    : summary?.status === 'rejected'
      ? 'error'
      : summary?.status === 'submitted'
        ? 'warning'
        : 'neutral';
  const weekText = summary ? weekLabel(summary.week_start) : weekLabel(toDateInput(startOfLocalWeek()));
  const detailRows = summary?.status === 'approved'
    ? [
        ['Week', weekText],
        ['Approved By', summary.reviewed_by || 'Manager'],
        ['Approved On', summary.reviewed_at ? formatDate(summary.reviewed_at.slice(0, 10)) : '-'],
      ]
    : summary?.status === 'submitted'
      ? [
          ['Week', weekText],
          ['Submitted On', summary.submitted_at ? formatDate(summary.submitted_at.slice(0, 10)) : '-'],
          ['Awaiting', summary.submitted_to ? `${summary.submitted_to} Approval` : 'Manager Approval'],
        ]
      : summary?.status === 'rejected'
        ? [
            ['Week', weekText],
            ['Rejected By', summary.reviewed_by || 'Manager'],
            ['Rejected On', summary.reviewed_at ? formatDate(summary.reviewed_at.slice(0, 10)) : '-'],
          ]
        : [
            ['Week', weekText],
            ['Action', 'Submit Timesheet'],
          ];

  return (
    <Card
      className="cursor-pointer p-5 transition-all hover:-translate-y-0.5 hover:border-accent/30 hover:shadow-card-lg"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onClick();
        }
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[12px] font-semibold text-gray-500">Timesheet</div>
          <div className="mt-2">
            <Badge variant={statusVariantName}>{status}</Badge>
          </div>
          <div className="mt-2 space-y-0.5 text-xs text-gray-500">
            {detailRows.map(([label, value]) => (
              <div key={label} className="flex gap-1.5">
                <span className="font-semibold text-gray-500">{label}:</span>
                <span className="truncate text-[var(--color-brand-navy)]">{value}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-light text-accent">
          <Clock3 size={21} />
        </div>
      </div>
    </Card>
  );
}

function SimpleTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: Array<Array<React.ReactNode>>;
}) {
  return (
    <Card className="overflow-hidden">
      <table className="w-full text-left text-sm">
        <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
          <tr>
            {headers.map((header) => (
              <th key={header} className="px-5 py-3 font-bold">{header}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--color-border)]">
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="text-[var(--color-brand-navy)]">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="px-5 py-4">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function AttendanceDashCard({
  today,
  loading,
  actionLoading,
  activeProjects,
  leaveSummary,
  onCheckIn,
  onCheckOut,
  onClick,
}: {
  today: AttendanceRecord | null;
  loading: boolean;
  actionLoading: 'check-in' | 'check-out' | null;
  activeProjects: DashboardAllocation[];
  leaveSummary: LeaveSummary | null;
  onCheckIn: () => void;
  onCheckOut: () => void;
  onClick: () => void;
}) {
  const [tick, setTick] = useState(Date.now());
  const todayInput = toDateInput(new Date());
  const todayLeave = (leaveSummary?.requests || []).find((request) => (
    request.status === 'approved' && request.start_date <= todayInput && request.end_date >= todayInput
  ));
  const isCheckedIn = !!today?.is_checked_in;
  const hasCheckedOut = !!today?.check_out && !isCheckedIn;
  const sessionStart = today?.check_in ? parseApiDateTime(today.check_in) : null;

  useEffect(() => {
    if (!isCheckedIn) return undefined;
    const timer = window.setInterval(() => setTick(Date.now()), 30000);
    return () => window.clearInterval(timer);
  }, [isCheckedIn]);

  const expectedCheckout = useMemo(() => {
    if (!sessionStart) return null;
    const value = new Date(sessionStart);
    value.setHours(value.getHours() + 8);
    return value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }, [sessionStart, tick]);

  const status = loading
    ? 'loading'
    : todayLeave
      ? 'on_leave'
      : isCheckedIn
        ? 'working'
        : hasCheckedOut
          ? 'checked_out'
          : 'not_checked_in';

  const label = status === 'working'
    ? 'Working now'
    : status === 'checked_out'
      ? 'Checked out'
      : status === 'on_leave'
        ? 'On leave'
        : status === 'loading'
          ? 'Loading'
          : 'Not checked in';
  const badgeVariant: 'olive' | 'warning' | 'neutral' = status === 'working'
    ? 'olive'
    : status === 'on_leave'
      ? 'warning'
      : 'neutral';
  const currentProject = activeProjects[0]?.project_name || 'No active project';

  return (
    <Card
      className="min-h-[168px] cursor-pointer p-5 transition-all hover:-translate-y-0.5 hover:border-accent/30 hover:shadow-card-lg"
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-label="Open attendance page"
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onClick();
        }
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-gray-400">Today</div>
          {loading ? (
            <div className="mt-4 space-y-3">
              <div className="h-5 w-28 animate-pulse rounded bg-gray-100" />
              <div className="h-3 w-40 animate-pulse rounded bg-gray-100" />
            </div>
          ) : (
            <>
              <div className="mt-2 flex items-center gap-2">
                <Badge variant={badgeVariant}>{label}</Badge>
              </div>
              <div className="mt-3 text-2xl font-bold text-[var(--color-brand-navy)]">
                {status === 'working' && sessionStart ? formatElapsed(today?.check_in) : status === 'checked_out' ? formatHours(today?.total_hours || 0) : status === 'on_leave' ? '8h leave' : '--'}
              </div>
              <div className="mt-2 space-y-1 text-xs text-gray-500">
                {status === 'working' && (
                  <>
                    <div>Checked in at <span className="font-semibold text-[var(--color-brand-navy)]">{formatTime(today?.check_in)}</span></div>
                    <div>Expected checkout {expectedCheckout || '-'}</div>
                    <div className="truncate">Project: {currentProject}</div>
                  </>
                )}
                {status === 'checked_out' && (
                  <>
                    <div>{formatTime(today?.check_in)} - {formatTime(today?.check_out)}</div>
                    <div>Status: {statusLabel(today?.status)}</div>
                  </>
                )}
                {status === 'on_leave' && (
                  <div>{todayLeave?.leave_type} approved for today</div>
                )}
                {status === 'not_checked_in' && (
                  <div>Start your day when you are ready.</div>
                )}
              </div>
            </>
          )}
        </div>
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-light text-accent">
          <LogIn size={21} />
        </div>
      </div>
      {!loading && !todayLeave && (
        <div className="mt-4">
          {isCheckedIn ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={(event) => {
                event.stopPropagation();
                onCheckOut();
              }}
              disabled={actionLoading === 'check-out'}
            >
              {actionLoading === 'check-out' ? 'Checking out...' : 'Check Out'}
            </Button>
          ) : !hasCheckedOut ? (
            <Button
              size="sm"
              onClick={(event) => {
                event.stopPropagation();
                onCheckIn();
              }}
              disabled={actionLoading === 'check-in'}
            >
              {actionLoading === 'check-in' ? 'Checking in...' : 'Check In'}
            </Button>
          ) : null}
        </div>
      )}
    </Card>
  );
}

function LeaveDashCard({
  leaveSummary,
  onClick,
}: {
  leaveSummary: LeaveSummary | null;
  onClick: () => void;
}) {
  const todayInput = toDateInput(new Date());
  const available = (leaveSummary?.balances || []).reduce((sum, leave) => {
    const effective = effectiveLeaveAvailable(leave);
    return effective !== null ? sum + effective : sum;
  }, 0);
  const used = (leaveSummary?.balances || []).reduce((sum, leave) => (
    typeof leave.used === 'number' ? sum + leave.used : sum
  ), 0);
  const progress = available + used > 0 ? Math.min(100, Math.round((available / (available + used)) * 100)) : 0;
  const upcomingLeave = (leaveSummary?.requests || [])
    .filter((request) => request.status === 'approved' && request.start_date >= todayInput)
    .sort((a, b) => a.start_date.localeCompare(b.start_date))[0];
  const breakdown = (leaveSummary?.balances || [])
    .filter((leave) => effectiveLeaveAvailable(leave) !== null && leave.type !== 'Loss of Pay')
    .slice(0, 4);
  const expiryWarning = (leaveSummary?.balances || []).find((leave) => (
    (effectiveLeaveAvailable(leave) || 0) > 0 && !leave.is_carry_forward && leave.expiry_label
  ));

  return (
    <Card
      className="min-h-[168px] cursor-pointer p-5 transition-all hover:-translate-y-0.5 hover:border-accent/30 hover:shadow-card-lg"
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-label="Open leave page"
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onClick();
        }
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-gray-400">Leave Balance</div>
          {!leaveSummary ? (
            <div className="mt-4 space-y-3">
              <div className="h-5 w-32 animate-pulse rounded bg-gray-100" />
              <div className="h-3 w-full animate-pulse rounded bg-gray-100" />
            </div>
          ) : (
            <>
              <div className="mt-2 text-2xl font-bold text-[var(--color-brand-navy)]">{formatNumber(available)} days</div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-accent-light">
                <div
                  className={cn('h-full rounded-full', available <= 1 ? 'bg-status-error' : available <= 5 ? 'bg-status-warning' : 'bg-accent')}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-gray-500">
                {breakdown.map((leave) => (
                  <div key={leave.leave_type_id} className="truncate">
                    <span className="font-semibold text-[var(--color-brand-navy)]">{leave.code || leave.type}:</span> {formatNumber(effectiveLeaveAvailable(leave) || 0)}
                  </div>
                ))}
              </div>
              <div className="mt-3 text-xs text-gray-500">
                {upcomingLeave
                  ? `Next: ${upcomingLeave.leave_type} on ${formatDate(upcomingLeave.start_date)}`
                  : expiryWarning
                    ? `${expiryWarning.type} ${expiryWarning.expiry_label}`
                    : 'No upcoming leave'}
              </div>
            </>
          )}
        </div>
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-light text-accent">
          <WalletCards size={21} />
        </div>
      </div>
    </Card>
  );
}

function TimesheetDashCard({
  summary,
  loading,
  onClick,
}: {
  summary: TimesheetSummary | null;
  loading: boolean;
  onClick: () => void;
}) {
  const weekText = summary ? weekLabel(summary.week_start) : weekLabel(toDateInput(startOfLocalWeek()));
  const workingHours = summary?.working_hours || 0;
  const progress = Math.min(100, Math.round((workingHours / 40) * 100));
  const statusVariantName: 'success' | 'error' | 'warning' | 'neutral' = summary?.status === 'approved'
    ? 'success'
    : summary?.status === 'rejected'
      ? 'error'
      : summary?.status === 'submitted'
        ? 'warning'
        : 'neutral';
  const detailRows = summary?.status === 'approved'
    ? [
        ['Week', weekText],
        ['Approved By', summary.reviewed_by || 'Manager'],
        ['Approved On', summary.reviewed_at ? formatDate(summary.reviewed_at.slice(0, 10)) : '-'],
      ]
    : summary?.status === 'submitted'
      ? [
          ['Week', weekText],
          ['Submitted On', summary.submitted_at ? formatDate(summary.submitted_at.slice(0, 10)) : '-'],
          ['Awaiting', summary.submitted_to ? `${summary.submitted_to} Approval` : 'Manager Approval'],
        ]
      : summary?.status === 'rejected'
        ? [
            ['Week', weekText],
            ['Rejected By', summary.reviewed_by || 'Manager'],
            ['Rejected On', summary.reviewed_at ? formatDate(summary.reviewed_at.slice(0, 10)) : '-'],
          ]
        : [
            ['Week', weekText],
            ['Remaining', `${formatNumber(Math.max(0, 40 - workingHours))}h to target`],
          ];

  return (
    <Card
      className="min-h-[168px] cursor-pointer p-5 transition-all hover:-translate-y-0.5 hover:border-accent/30 hover:shadow-card-lg"
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-label="Open timesheets page"
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onClick();
        }
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-gray-400">Timesheet</div>
          {loading ? (
            <div className="mt-4 space-y-3">
              <div className="h-5 w-24 animate-pulse rounded bg-gray-100" />
              <div className="h-3 w-40 animate-pulse rounded bg-gray-100" />
            </div>
          ) : (
            <>
              <div className="mt-2">
                <Badge variant={statusVariantName}>{summary ? statusLabel(summary.status) : 'Not Submitted'}</Badge>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-accent-light">
                <div
                  className={cn(
                    'h-full rounded-full',
                    summary?.status === 'approved'
                      ? 'bg-accent'
                      : summary?.status === 'submitted'
                        ? 'bg-accent'
                        : workingHours >= 40
                          ? 'bg-accent'
                          : workingHours >= 24
                            ? 'bg-status-warning'
                            : 'bg-status-error'
                  )}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="mt-3 space-y-0.5 text-xs text-gray-500">
                {detailRows.map(([label, value]) => (
                  <div key={label} className="flex gap-1.5">
                    <span className="font-semibold text-gray-500">{label}:</span>
                    <span className="truncate text-[var(--color-brand-navy)]">{value}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-light text-accent">
          <Clock3 size={21} />
        </div>
      </div>
    </Card>
  );
}

function ActionsDashCard({
  leaveSummary,
  timesheetSummary,
  approvalRows,
  timesheetApprovalRows,
  actionInboxRows,
  onNavigate,
}: {
  leaveSummary: LeaveSummary | null;
  timesheetSummary: TimesheetSummary | null;
  approvalRows: LeaveRequestItem[];
  timesheetApprovalRows: TimesheetApprovalItem[];
  actionInboxRows: ActionInboxItem[];
  onNavigate: (path: string) => void;
}) {
  const pendingOwnRequests = (leaveSummary?.requests || []).filter((request) => request.status === 'pending').length;
  const pendingTimesheet = timesheetSummary?.status === 'submitted' || timesheetSummary?.status === 'approved' ? 0 : 1;
  const inboxPath = (item: ActionInboxItem) => {
    if (item.item_type === 'profile_update') return '/profile';
    if (item.related_entity_type === 'announcement') return '/notifications';
    return '/notifications';
  };
  const items = [
    ...actionInboxRows.map((item, index) => ({
      title: item.title,
      meta: item.description || item.employee_name || 'Action required',
      path: inboxPath(item),
      status: item.priority === 'urgent' ? 'Urgent' : 'Review',
      priority: index,
    })),
    ...(pendingTimesheet ? [{
      title: 'Submit this week timesheet',
      meta: 'Timesheet not submitted',
      path: '/employee/timesheets',
      status: 'Due',
      priority: 100,
    }] : []),
    ...(pendingOwnRequests ? [{
      title: `${pendingOwnRequests} leave request${pendingOwnRequests === 1 ? '' : 's'} pending`,
      meta: 'Waiting for manager review',
      path: '/employee/apply-leave',
      status: 'Pending',
      priority: 200,
    }] : []),
    ...(approvalRows.length ? [{
      title: `${approvalRows.length} leave approval${approvalRows.length === 1 ? '' : 's'}`,
      meta: 'Assigned to you',
      path: '/employee/approvals',
      status: 'Review',
      priority: 300,
    }] : []),
    ...(timesheetApprovalRows.length ? [{
      title: `${timesheetApprovalRows.length} timesheet approval${timesheetApprovalRows.length === 1 ? '' : 's'}`,
      meta: 'Assigned to you',
      path: '/employee/approvals',
      status: 'Review',
      priority: 400,
    }] : []),
  ].sort((a, b) => a.priority - b.priority);
  const totalActions = items.length;

  return (
    <Card className="min-h-[168px] p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[12px] font-semibold uppercase tracking-wide text-gray-400">Pending Actions</div>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-2xl font-bold text-[var(--color-brand-navy)]">{totalActions}</span>
            <Badge variant={totalActions ? 'warning' : 'olive'}>{totalActions ? 'Needs review' : 'All clear'}</Badge>
          </div>
        </div>
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-light text-accent">
          {totalActions ? <ClipboardCheck size={21} /> : <CheckCircle2 size={21} />}
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {items.slice(0, 4).map((item) => (
          <button
            key={`${item.title}-${item.path}`}
            type="button"
            className="flex w-full items-center justify-between gap-3 rounded-lg border border-[var(--color-border)] px-3 py-2 text-left transition hover:border-accent/30 hover:bg-accent-light focus:outline-none focus:ring-2 focus:ring-accent/20"
            onClick={() => onNavigate(item.path)}
          >
            <span className="min-w-0">
              <span className="block truncate text-xs font-semibold text-[var(--color-brand-navy)]">{item.title}</span>
              <span className="block truncate text-[11px] text-gray-500">{item.meta}</span>
            </span>
            <Badge variant={item.status === 'Due' ? 'warning' : 'neutral'}>{item.status}</Badge>
          </button>
        ))}
        {!items.length && (
          <div className="rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2 text-xs text-gray-500">
            No pending actions right now.
          </div>
        )}
      </div>
    </Card>
  );
}

function dashboardInitials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'NA';
}

function EmployeeStatusTile({
  label,
  value,
  detail,
  icon,
  borderColor,
  iconClass,
  valueClass = 'text-[#1f2430]',
  onClick,
}: {
  label: string;
  value: React.ReactNode;
  detail: React.ReactNode;
  icon: React.ReactNode;
  borderColor: string;
  iconClass: string;
  valueClass?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="relative min-h-[158px] overflow-hidden rounded-2xl border border-[#ece5d8] bg-white p-5 text-left shadow-[0_3px_10px_rgba(60,40,10,.025)] transition hover:-translate-y-0.5 hover:shadow-[0_10px_24px_rgba(60,40,10,.08)]"
      style={{ borderTop: `3px solid ${borderColor}` }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="text-[11px] font-bold uppercase tracking-[.08em] text-[#9a927f]">{label}</div>
        <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', iconClass)}>{icon}</div>
      </div>
      <div className={cn('mt-3 text-[27px] font-bold leading-tight tracking-[-.025em]', valueClass)}>{value}</div>
      <div className="mt-2 text-[12px] leading-relaxed text-[#8a8371]">{detail}</div>
    </button>
  );
}

function DashboardQuickAction({ icon, label, onClick, disabled = false }: { icon: React.ReactNode; label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className="flex min-h-[58px] items-center gap-3 rounded-xl border border-[#ece5d8] bg-[#fffdf9] px-4 py-3 text-left text-[12px] font-bold text-[#1f2430] transition hover:border-[#d97a34]/40 hover:bg-[#fbf5ea] disabled:cursor-not-allowed disabled:opacity-50">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#fbeee1] text-[#d97a34]">{icon}</span>
      {label}
    </button>
  );
}

export function EmployeeDashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { today, loading, actionLoading, error, checkIn, checkOut } = useAttendance();
  const isCheckedIn = !!today?.is_checked_in;
  const dashboardCacheKey = user?.id || user?.email || '';
  const cachedDashboard = dashboardCacheKey ? dashboardCache[dashboardCacheKey] : undefined;
  const [leaveSummary, setLeaveSummary] = useState<LeaveSummary | null>(cachedDashboard?.leaveSummary ?? null);
  const [timesheetSummary, setTimesheetSummary] = useState<TimesheetSummary | null>(cachedDashboard?.timesheetSummary ?? null);
  const [timesheetHistory, setTimesheetHistory] = useState<TimesheetWeek[]>(cachedDashboard?.timesheetHistory ?? []);
  const [approvalRows, setApprovalRows] = useState<LeaveRequestItem[]>(cachedDashboard?.leaveApprovalRows ?? []);
  const [timesheetApprovalRows, setTimesheetApprovalRows] = useState<TimesheetApprovalItem[]>(cachedDashboard?.timesheetApprovalRows ?? []);
  const [activeProjects, setActiveProjects] = useState<DashboardAllocation[]>(cachedDashboard?.activeProjects ?? []);
  const [actionInboxRows, setActionInboxRows] = useState<ActionInboxItem[]>(cachedDashboard?.actionInboxRows ?? []);
  const [employeeContext, setEmployeeContext] = useState<EmployeeDashboardContext | null>(cachedDashboard?.employeeContext ?? null);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  useEffect(() => {
    if (!user) return;
    Promise.all([
      fetch(`${API_BASE}/leaves/me/summary`, { headers }).then((res) => res.ok ? res.json() : null),
      fetch(`${API_BASE}/timesheets/me/summary`, { headers }).then((res) => res.ok ? res.json() : null),
      fetch(`${API_BASE}/timesheets/me/history`, { headers }).then((res) => res.ok ? res.json() : null),
      fetch(`${API_BASE}/leaves/approvals`, { headers }).then((res) => res.ok ? res.json() : null),
      fetch(`${API_BASE}/timesheets/approvals`, { headers }).then((res) => res.ok ? res.json() : null),
      fetch(`${API_BASE}/inbox`, { headers }).then((res) => res.ok ? res.json() : null),
      user.id ? fetch(`${API_BASE}/allocations/employee/${user.id}/active`, { headers }).then((res) => res.ok ? res.json() : null) : Promise.resolve(null),
      fetch(`${API_BASE}/dashboard/employee-context`, { headers }).then((res) => res.ok ? res.json() : null),
    ]).then(([leaveData, timesheetSummaryData, timesheetHistoryData, approvalsData, timesheetApprovalsData, inboxData, activeProjectsData, employeeContextData]) => {
      const existingCache = dashboardCacheKey ? dashboardCache[dashboardCacheKey] : undefined;
      const nextLeaveSummary = leaveData || existingCache?.leaveSummary || null;
      const nextTimesheetSummary = timesheetSummaryData || existingCache?.timesheetSummary || null;
      const nextTimesheetHistory = timesheetHistoryData || existingCache?.timesheetHistory || [];
      const nextApprovalRows = approvalsData?.approvals || existingCache?.leaveApprovalRows || [];
      const nextTimesheetApprovalRows = timesheetApprovalsData?.approvals || existingCache?.timesheetApprovalRows || [];
      const nextActionInboxRows = inboxData?.items || existingCache?.actionInboxRows || [];
      const nextActiveProjects = activeProjectsData || existingCache?.activeProjects || [];
      const nextEmployeeContext = employeeContextData || existingCache?.employeeContext || null;
      if (leaveData) setLeaveSummary(leaveData);
      if (timesheetSummaryData) setTimesheetSummary(timesheetSummaryData);
      if (timesheetHistoryData) setTimesheetHistory(timesheetHistoryData);
      if (approvalsData?.approvals) setApprovalRows(approvalsData.approvals);
      if (timesheetApprovalsData?.approvals) setTimesheetApprovalRows(timesheetApprovalsData.approvals);
      if (inboxData?.items) setActionInboxRows(inboxData.items);
      if (activeProjectsData) setActiveProjects(activeProjectsData);
      if (employeeContextData) setEmployeeContext(employeeContextData);
      if (dashboardCacheKey) {
        dashboardCache[dashboardCacheKey] = {
          leaveSummary: nextLeaveSummary,
          timesheetSummary: nextTimesheetSummary,
          timesheetHistory: nextTimesheetHistory,
          leaveApprovalRows: nextApprovalRows,
          timesheetApprovalRows: nextTimesheetApprovalRows,
          activeProjects: nextActiveProjects,
          actionInboxRows: nextActionInboxRows,
          employeeContext: nextEmployeeContext,
        };
      }
    }).catch(() => {
      // Keep dashboard usable even if one summary endpoint is temporarily unavailable.
    });
  }, [dashboardCacheKey, headers, user]);

  const timesheetCardWeekStart = timesheetSummary?.week_start || toDateInput(startOfLocalWeek());
  const openTimesheetSummary = () => navigate(`/employee/timesheets?week_start=${encodeURIComponent(timesheetCardWeekStart)}`);
  const activityTime = (value?: string | null): number => {
    if (!value) return 0;
    const parsed = parseApiDateTime(value)?.getTime();
    return Number.isFinite(parsed) ? parsed || 0 : 0;
  };
  const timesheetActivityRows = timesheetHistory
    .filter((week) => week.status && week.status !== 'not_started')
    .map((week) => ({
      title: `Timesheet ${statusLabel(week.status)}`,
      meta: `Week: ${weekLabel(week.week_start)}`,
      status: week.status,
      key: `timesheet-${week.week_start}-${week.status}`,
      activityAt: activityTime(week.reviewed_at || week.submitted_at || week.week_end),
    }));
  const dashboardActivity: Array<{
    title: string;
    meta: string;
    status: string;
    key: string;
    activityAt: number;
  }> = [
    ...(leaveSummary?.requests || []).map((request) => ({
      title: `${request.leave_type} ${request.status}`,
      meta: request.status === 'pending'
        ? `Pending with ${request.pending_with || request.reporting_manager || 'manager'}`
        : `${formatDate(request.start_date)} - ${formatDate(request.end_date)}`,
      status: request.status,
      key: `leave-${request.id}`,
      activityAt: activityTime(request.updated_at || request.reviewed_at || request.created_at || request.start_date),
    })),
    ...timesheetActivityRows,
    ...activeProjects.map((allocation) => ({
      title: `Allocated to ${allocation.project_name || 'project'}`,
      meta: `${allocation.allocation_role} · ${allocation.allocation_percentage}% allocation`,
      status: allocation.status,
      key: `allocation-${allocation.id}`,
      activityAt: activityTime(allocation.created_at || allocation.start_date),
    })),
  ].sort((a, b) => b.activityAt - a.activityAt).slice(0, 4);

  const currentEmployee = employeeContext?.employee;
  const employeeName = currentEmployee?.name || user?.name || 'Employee';
  const firstName = employeeName.split(/\s+/).filter(Boolean)[0] || 'there';
  const greetingHour = new Date().getHours();
  const greeting = greetingHour < 12 ? 'Good morning' : greetingHour < 17 ? 'Good afternoon' : 'Good evening';
  const dateLabel = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  const totalAllocation = Math.min(100, activeProjects.reduce((sum, allocation) => sum + Number(allocation.allocation_percentage || 0), 0));
  const leaveBalances = leaveSummary?.balances || [];
  const leaveTotal = leaveBalances.reduce((sum, leave) => sum + (effectiveLeaveAvailable(leave) || 0), 0);
  const leaveByCode = new Map(leaveBalances.map((leave) => [(leave.code || leave.type).toUpperCase(), effectiveLeaveAvailable(leave) || 0]));
  const leaveBreakdown = ['CL', 'SL', 'EL', 'CO'].map((code) => `${code} ${formatNumber(leaveByCode.get(code) || 0)}`).join(' · ');
  const isCheckedOut = !!today?.check_out && !isCheckedIn;
  const attendanceValue = isCheckedIn ? formatElapsed(today?.check_in) : isCheckedOut ? formatHours(today?.total_hours || 0) : '0h 0m';
  const attendanceDetail = isCheckedIn
    ? `Checked in at ${formatTime(today?.check_in)} · Working`
    : isCheckedOut
      ? `Checked out · ${statusLabel(today?.status || 'present')}`
      : 'Not checked in yet';
  const timesheetStatus = timesheetSummary?.status || 'not_submitted';
  const timesheetNeedsAttention = !['submitted', 'approved'].includes(timesheetStatus);
  const remainingTimesheetHours = Math.max(0, 40 - Number(timesheetSummary?.working_hours || 0));
  const timesheetDueDate = timesheetSummary?.week_end ? formatDate(timesheetSummary.week_end) : formatDate(toDateInput(addDays(startOfLocalWeek(), 6)));
  const pendingOwnLeave = (leaveSummary?.requests || []).filter((request) => request.status === 'pending').length;
  const pendingOwnTimesheet = timesheetNeedsAttention ? 1 : 0;
  const managerApprovalCount = approvalRows.length + timesheetApprovalRows.length;
  const pendingActionCount = actionInboxRows.length + pendingOwnLeave + pendingOwnTimesheet + managerApprovalCount;
  const directReports = employeeContext?.direct_reports || [];

  return (
    <div className="animate-fade-up text-[#1f2430]">
      <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <h1 className="text-[26px] font-bold tracking-[-.035em]">{greeting}, {firstName} <span aria-hidden>👋</span></h1>
          <p className="mt-1 text-sm text-[#8a8371]">{dateLabel} · Here&apos;s your day at a glance.</p>
        </div>
        <Button onClick={isCheckedIn ? checkOut : checkIn} disabled={!!actionLoading || isCheckedOut} className="border-[#d97a34] bg-[#d97a34] px-6 shadow-[0_8px_18px_rgba(217,122,52,.2)] hover:bg-[#c9611f]" icon={<LogIn size={16} />}>
          {actionLoading ? 'Updating...' : isCheckedIn ? 'Check Out' : isCheckedOut ? 'Day Complete' : 'Check In'}
        </Button>
      </div>

      {error && <div className="mb-5 rounded-xl border border-[#d64545]/20 bg-[#fcecec] px-4 py-3 text-sm text-[#d64545]">{error}</div>}

      <section className="mb-5 grid gap-5 rounded-2xl border border-[#ece5d8] bg-[#fbf5ea] p-5 shadow-[0_3px_10px_rgba(60,40,10,.025)] lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-center">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#e79a55] to-[#c9611f] text-lg font-bold text-white shadow-[0_4px_12px_rgba(201,97,31,.25)]">{dashboardInitials(employeeName)}</div>
          <div className="min-w-0"><div className="truncate text-[17px] font-bold">{employeeName}</div><div className="truncate text-sm text-[#8a8371]">{currentEmployee?.designation || 'Employee'} · {currentEmployee?.department || 'Department not set'}</div></div>
        </div>
        <div className="border-t border-[#e6dac6] pt-4 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
          <div className="text-[10px] font-bold uppercase tracking-[.08em] text-[#9a927f]">Reports To</div>
          <div className="mt-2 flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#2b3243] text-[10px] font-bold text-white">{dashboardInitials(employeeContext?.manager?.name || 'Self')}</span>
            <span className="max-w-[140px] truncate text-sm font-bold">{employeeContext?.manager?.name || 'No manager'}</span>
            <button type="button" onClick={() => navigate('/profile?tab=organization')} className="whitespace-nowrap text-xs font-semibold text-[#d97a34]">Org chart →</button>
          </div>
        </div>
        <div className="min-w-[180px] border-t border-[#e6dac6] pt-4 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
          <div className="flex justify-between text-[10px] font-bold uppercase tracking-[.08em] text-[#9a927f]"><span>Allocation</span><span className="text-[#1f2430]">{totalAllocation}%</span></div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#eadfca]"><div className="h-full rounded-full bg-[#d97a34]" style={{ width: `${totalAllocation}%` }} /></div>
          <div className="mt-1.5 text-[11px] text-[#8a8371]">Across {activeProjects.length} active {activeProjects.length === 1 ? 'project' : 'projects'}</div>
        </div>
      </section>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <EmployeeStatusTile label="Today" value={loading ? 'Loading...' : attendanceValue} detail={attendanceDetail} icon={<ArrowRight size={17} />} borderColor="#d97a34" iconClass="bg-[#fbeee1] text-[#d97a34]" onClick={() => navigate('/employee/check-in')} />
        <EmployeeStatusTile label="Leave Balance" value={`${formatNumber(leaveTotal)} days`} detail={leaveBreakdown} icon={<CalendarCheck size={17} />} borderColor="#5b8c5a" iconClass="bg-[#e5f3e5] text-[#5b8c5a]" onClick={() => navigate('/employee/apply-leave')} />
        <EmployeeStatusTile label="Timesheet" value={statusLabel(timesheetStatus)} detail={`${formatNumber(remainingTimesheetHours)}h to target · due ${timesheetDueDate}`} icon={<Clock3 size={17} />} borderColor={timesheetNeedsAttention ? '#d64545' : '#5b8c5a'} iconClass={timesheetNeedsAttention ? 'bg-[#fcecec] text-[#d64545]' : 'bg-[#e5f3e5] text-[#5b8c5a]'} valueClass={timesheetNeedsAttention ? 'text-[#d64545]' : 'text-[#5b8c5a]'} onClick={openTimesheetSummary} />
        <EmployeeStatusTile label="Pending Actions" value={String(pendingActionCount)} detail={pendingActionCount ? 'Items need your attention' : 'You are all caught up'} icon={<ClipboardCheck size={17} />} borderColor="#2b3243" iconClass="bg-[#f0f1f6] text-[#2b3243]" onClick={() => navigate('/employee/requests')} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <div className="space-y-5">
          <section className="overflow-hidden rounded-2xl border border-[#ece5d8] bg-white shadow-[0_3px_10px_rgba(60,40,10,.025)]">
            <div className="flex items-center justify-between border-b border-[#ece5d8] px-5 py-4">
              <div className="flex items-center gap-2.5"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#fbeee1] text-[#d97a34]"><FolderKanban size={17} /></span><h2 className="text-[15px] font-bold">My Projects</h2><Badge variant="warning">{activeProjects.length} active</Badge></div>
              <button type="button" onClick={() => navigate('/projects')} className="text-xs font-bold text-[#d97a34]">All allocations →</button>
            </div>
            <div className="space-y-3 p-5">
              {activeProjects.length === 0 ? <div className="rounded-xl border border-dashed border-[#ded3bf] bg-[#fffdf9] px-5 py-10 text-center text-sm text-[#8a8371]">You do not have an active project allocation yet.</div> : activeProjects.map((allocation, index) => {
                const atRisk = ['on_hold', 'cancelled'].includes((allocation.project_status || '').toLowerCase());
                const projectMark = allocation.project_code || allocation.project_name || `P${index + 1}`;
                const projectEnd = allocation.project_end_date || allocation.end_date;
                return (
                  <div key={allocation.id} className="grid gap-4 rounded-xl border border-[#ece5d8] bg-[#fffdf9] p-4 md:grid-cols-[auto_minmax(0,1fr)_170px] md:items-center">
                    <div className={cn('flex h-12 w-12 items-center justify-center rounded-xl text-xs font-bold text-white', index % 2 ? 'bg-[#4d5873]' : 'bg-[#d97a34]')}>{projectMark.slice(0, 3).toUpperCase()}</div>
                    <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><div className="truncate text-sm font-bold">{allocation.project_name || 'Assigned project'}</div><span className={cn('rounded-full px-2 py-0.5 text-[10px] font-bold', atRisk ? 'bg-[#fcecec] text-[#d64545]' : 'bg-[#e5f3e5] text-[#5b8c5a]')}>{atRisk ? 'At risk' : 'On track'}</span></div><div className="mt-1 text-xs text-[#8a8371]">{allocation.project_client_name || 'Internal'} · {allocation.allocation_role || 'Team member'}</div></div>
                    <div><div className="mb-2 flex justify-between gap-3 text-[11px] text-[#8a8371]"><span>{formatDate(allocation.project_start_date || allocation.start_date)}–{projectEnd ? formatDate(projectEnd) : 'Ongoing'}</span><strong className="text-[#1f2430]">{allocation.allocation_percentage}%</strong></div><div className="h-1.5 overflow-hidden rounded-full bg-[#eee6d7]"><div className="h-full rounded-full bg-[#d97a34]" style={{ width: `${Math.min(100, allocation.allocation_percentage)}%` }} /></div></div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border border-[#ece5d8] bg-white shadow-[0_3px_10px_rgba(60,40,10,.025)]">
            <div className="flex items-center gap-2.5 border-b border-[#ece5d8] px-5 py-4"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#fbeee1] text-[#d97a34]"><CalendarClock size={17} /></span><h2 className="text-[15px] font-bold">Recent Activity</h2></div>
            <div className="px-5 py-2">{dashboardActivity.length === 0 ? <div className="py-8 text-center text-sm text-[#8a8371]">No recent activity yet.</div> : dashboardActivity.map((item, index) => <div key={item.key} className="relative flex gap-4 border-b border-[#f0e9dc] py-4 last:border-0"><div className="relative z-10 mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-[#d97a34] ring-4 ring-[#fbeee1]" />{index < dashboardActivity.length - 1 && <span className="absolute left-[4px] top-7 h-[calc(100%-12px)] w-px bg-[#e5dac7]" />}<div className="min-w-0 flex-1"><div className="text-sm font-bold">{item.title}</div><div className="mt-1 text-xs text-[#8a8371]">{item.meta}</div></div><Badge variant={item.status === 'approved' || item.status === 'submitted' || item.status === 'active' ? 'olive' : item.status === 'rejected' ? 'error' : 'warning'}>{statusLabel(item.status)}</Badge></div>)}</div>
          </section>
        </div>

        <div className="space-y-5">
          {directReports.length > 0 && <section className="overflow-hidden rounded-2xl border border-[#ece5d8] bg-white shadow-[0_3px_10px_rgba(60,40,10,.025)]">
            <div className="flex items-center justify-between border-b border-[#ece5d8] px-5 py-4"><div className="flex items-center gap-2.5"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#f0f1f6] text-[#4d5873]"><UsersRound size={17} /></span><h2 className="text-[15px] font-bold">My Team</h2><span className="text-xs text-[#8a8371]">{directReports.length} people</span></div><button type="button" onClick={() => navigate('/team-allocation')} className="text-xs font-bold text-[#d97a34]">Manage →</button></div>
            <div className="p-5">
              {managerApprovalCount > 0 && <button type="button" onClick={() => navigate('/employee/approvals')} className="mb-4 flex w-full items-center justify-between rounded-xl border border-[#eed4b5] bg-[#fbf5ea] px-4 py-3 text-left text-xs font-bold text-[#a7561b]"><span>{managerApprovalCount} {managerApprovalCount === 1 ? 'approval' : 'approvals'} waiting on you</span><span>Review →</span></button>}
              <div className="space-y-4">{directReports.slice(0, 6).map((report) => <div key={report.id} className="flex items-center gap-3"><div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#efe7d8] text-xs font-bold text-[#8a6a3a]">{dashboardInitials(report.name)}<span className={cn('absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full ring-2 ring-white', report.today_status === 'on_leave' ? 'bg-[#e2a532]' : report.today_status === 'working' ? 'bg-[#42bf77]' : 'bg-[#b8b4aa]')} /></div><div className="min-w-0 flex-1"><div className="truncate text-sm font-bold">{report.name}</div><div className="truncate text-xs text-[#8a8371]">{report.designation || report.department || 'Team member'}</div></div><span className={cn('text-xs font-semibold', report.today_status === 'on_leave' ? 'text-[#c87816]' : report.today_status === 'working' ? 'text-[#4c8b3f]' : 'text-[#8a8371]')}>{report.today_status === 'on_leave' ? 'On leave' : report.today_status === 'working' ? 'Working' : 'Not checked in'}</span></div>)}</div>
            </div>
          </section>}

          <section className="rounded-2xl border border-[#ece5d8] bg-white p-5 shadow-[0_3px_10px_rgba(60,40,10,.025)]">
            <h2 className="mb-4 text-[15px] font-bold">Quick Actions</h2>
            <div className="grid grid-cols-2 gap-3">
              <DashboardQuickAction icon={<CalendarPlus size={15} />} label="Apply Leave" onClick={() => navigate('/employee/apply-leave')} />
              <DashboardQuickAction icon={<Clock3 size={15} />} label="Submit Timesheet" onClick={() => navigate('/employee/timesheets')} />
              <DashboardQuickAction icon={<CalendarCheck size={15} />} label="Report Sick" onClick={() => navigate('/employee/apply-leave?quick=sick-today')} />
              <DashboardQuickAction icon={<LogIn size={15} />} label={isCheckedIn ? 'Check Out' : isCheckedOut ? 'Day Complete' : 'Check In'} onClick={isCheckedIn ? checkOut : checkIn} disabled={!!actionLoading || isCheckedOut} />
              <DashboardQuickAction icon={<Send size={15} />} label="New Request" onClick={() => navigate('/employee/requests')} />
              <DashboardQuickAction icon={<Briefcase size={15} />} label="My Projects" onClick={() => navigate('/projects')} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );

}

export function ApplyLeavePage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [leaveSummary, setLeaveSummary] = useState<LeaveSummary | null>(null);
  const [reportingManager, setReportingManager] = useState('Not assigned');
  const [leaveForm, setLeaveForm] = useState({
    leaveTypeId: '',
    fromDate: '',
    toDate: '',
    reason: '',
  });
  const [editingLeaveId, setEditingLeaveId] = useState<string | null>(null);
  const [loadingLeave, setLoadingLeave] = useState(true);
  const [savingLeave, setSavingLeave] = useState<'draft' | 'submit' | null>(null);
  const [leaveError, setLeaveError] = useState<string | null>(null);
  const [leaveSuccess, setLeaveSuccess] = useState<string | null>(null);
  const [quickLeaveApplied, setQuickLeaveApplied] = useState(false);
  const [floatingHolidays, setFloatingHolidays] = useState<HolidayItem[]>([]);
  const [selectedHolidayId, setSelectedHolidayId] = useState('');
  const [workingDays, setWorkingDays] = useState<WorkingDaysSummary | null>(null);
  const [loadingWorkingDays, setLoadingWorkingDays] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmWithdrawId, setConfirmWithdrawId] = useState<string | null>(null);
  const [withdrawingLeaveId, setWithdrawingLeaveId] = useState<string | null>(null);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const loadLeaveSummary = useCallback(async () => {
    if (!user) return;
    setLoadingLeave(true);
    setLeaveError(null);
    try {
      const res = await fetch(`${API_BASE}/leaves/me/summary`, { headers });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not load leave details.');
      setLeaveSummary(data);
      setReportingManager(data.reporting_manager || 'Not assigned');
      const firstAvailableLeave = (data.balances || []).find((leave: LeaveBalanceItem) => {
        const effective = effectiveLeaveAvailable(leave);
        return !leave.is_paid || effective === null || effective > 0;
      }) || data.balances?.[0];
      setLeaveForm((current) => ({
        ...current,
        leaveTypeId: current.leaveTypeId || firstAvailableLeave?.leave_type_id || '',
      }));
    } catch (err) {
      setLeaveError(err instanceof Error ? err.message : 'Could not load leave details.');
    } finally {
      setLoadingLeave(false);
    }
  }, [headers, user]);

  useEffect(() => {
    loadLeaveSummary();
  }, [loadLeaveSummary]);

  const updateLeaveForm = (key: keyof typeof leaveForm, value: string) => {
    setLeaveForm((current) => {
      const next = { ...current, [key]: value };
      if (key === 'fromDate' && next.toDate && value && next.toDate < value) {
        next.toDate = value;
      }
      return next;
    });
  };

  const saveLeaveRequest = async (action: 'draft' | 'submit') => {
    setSavingLeave(action);
    setLeaveError(null);
    setLeaveSuccess(null);
    try {
      if (!leaveForm.leaveTypeId || !leaveForm.fromDate || !leaveForm.toDate || (!isHolidayLeave && !leaveForm.reason.trim())) {
        throw new Error(isHolidayLeave ? 'Select leave type and holiday before saving.' : 'Select leave type, dates, and enter a reason before saving.');
      }
      if (isHolidayLeave && !selectedHolidayId) {
        throw new Error('Select the holiday you want to take.');
      }
      if (leaveForm.toDate < leaveForm.fromDate) {
        throw new Error('End date must be on or after start date.');
      }
      if (minAllowedDate && (leaveForm.fromDate < minAllowedDate || leaveForm.toDate < minAllowedDate)) {
        if (leaveSummary?.joining_date && (leaveForm.fromDate < leaveSummary.joining_date || leaveForm.toDate < leaveSummary.joining_date)) {
          throw new Error(`Leave cannot be applied before your joining date (${formatDate(leaveSummary.joining_date)}).`);
        }
        throw new Error('Cannot apply leave for a past date.');
      }
      if (maxAllowedDate && leaveForm.fromDate > maxAllowedDate) {
        throw new Error(selectedPolicy?.allow_future_dates === false ? `${selectedLeaveType?.type || 'This leave type'} cannot be applied for future dates.` : 'Leave cannot be applied more than 90 days in advance.');
      }
      if (action === 'submit' && selectedLeaveUnavailable) {
        throw new Error((selectedLeaveType?.pending || 0) > 0 ? `No balance available - ${formatNumber(selectedLeaveType?.pending || 0)} days are pending approval.` : 'Leave balance exhausted.');
      }
      if (
        action === 'submit'
        && selectedLeaveType?.is_paid
        && selectedEffectiveAvailable !== null
        && workingDays
        && workingDays.working_days > selectedEffectiveAvailable
      ) {
        throw new Error(`You only have ${formatNumber(selectedEffectiveAvailable)} effective day${selectedEffectiveAvailable === 1 ? '' : 's'} available after pending requests.`);
      }
      if (leavePolicyMessage && selectedPolicy?.allow_future_dates === false) {
        throw new Error(leavePolicyMessage);
      }
      const res = await fetch(`${API_BASE}/leaves/me/requests${editingLeaveId ? `/${editingLeaveId}` : ''}`, {
        method: editingLeaveId ? 'PUT' : 'POST',
        headers,
        body: JSON.stringify({
          leave_type_id: leaveForm.leaveTypeId,
          start_date: leaveForm.fromDate,
          end_date: leaveForm.toDate,
          reason: isHolidayLeave ? `${selectedLeaveType?.type || 'Holiday'}: ${selectedHoliday?.name || 'Selected holiday'}` : leaveForm.reason.trim(),
          holiday_id: isHolidayLeave ? selectedHolidayId : null,
          action,
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not save leave request.');
      setLeaveSummary(data);
      setReportingManager(data.reporting_manager || 'Not assigned');
      setEditingLeaveId(null);
      setLeaveForm((current) => ({
        leaveTypeId: (data.balances || []).find((leave: LeaveBalanceItem) => {
          const effective = effectiveLeaveAvailable(leave);
          return !leave.is_paid || effective === null || effective > 0;
        })?.leave_type_id || data.balances?.[0]?.leave_type_id || current.leaveTypeId,
        fromDate: '',
        toDate: '',
        reason: '',
      }));
      setSelectedHolidayId('');
      setLeaveSuccess(action === 'draft' ? 'Leave request saved as draft.' : `Leave request submitted. Pending with ${data.reporting_manager || 'Super Admin'}.`);
    } catch (err) {
      setLeaveError(err instanceof Error ? err.message : 'Could not save leave request.');
    } finally {
      setSavingLeave(null);
    }
  };

  const leaveBalances = leaveSummary?.balances || [];
  const leaveRequests = leaveSummary?.requests || [];
  const selectedLeaveType = leaveBalances.find((leave) => leave.leave_type_id === leaveForm.leaveTypeId);
  const selectedLeaveCode = selectedLeaveType?.code?.toUpperCase() || '';
  const isHolidayLeave = ['FL', 'OH'].includes(selectedLeaveCode);
  const selectedHoliday = floatingHolidays.find((holiday) => holiday.id === selectedHolidayId);
  const selectedPolicy = selectedLeaveType?.date_policy;
  const todayInput = toDateInput(new Date());
  const serverMinRequestDate = leaveSummary?.min_request_date || todayInput;
  const policyMinAllowedDate = selectedPolicy?.past_date_limit_days != null
    ? toDateInput(addDays(new Date(`${todayInput}T00:00:00`), -selectedPolicy.past_date_limit_days))
    : undefined;
  const minAllowedDate = maxDateInput(todayInput, leaveSummary?.joining_date || undefined, serverMinRequestDate, policyMinAllowedDate);
  const maxAdvanceDate = toDateInput(addDays(new Date(`${todayInput}T00:00:00`), 90));
  const maxAllowedDate = selectedPolicy?.allow_future_dates === false ? todayInput : maxAdvanceDate;
  const selectedHasFutureDate = [leaveForm.fromDate, leaveForm.toDate].some((value) => value && value > todayInput);
  const leavePolicyMessage = selectedLeaveType && selectedPolicy?.allow_future_dates === false && selectedHasFutureDate
    ? `${selectedLeaveType.type} cannot be applied for future dates.`
    : selectedLeaveType && selectedPolicy?.future_date_warning && selectedHasFutureDate
      ? selectedPolicy.future_date_warning
      : null;
  const selectedEffectiveAvailable = selectedLeaveType ? effectiveLeaveAvailable(selectedLeaveType) : null;
  const selectedLeaveUnavailable = Boolean(
    selectedLeaveType?.is_paid
    && selectedEffectiveAvailable !== null
    && selectedEffectiveAvailable <= 0
  );
  const firstSelectableLeaveTypeId = useMemo(() => {
    const firstAvailable = leaveBalances.find((leave) => {
      const effective = effectiveLeaveAvailable(leave);
      return !leave.is_paid || effective === null || effective > 0;
    });
    return firstAvailable?.leave_type_id || leaveBalances[0]?.leave_type_id || '';
  }, [leaveBalances]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const loadFloatingHolidays = async () => {
      try {
        const res = await fetch(`${API_BASE}/holidays/available-floating`, { headers });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(data?.detail || 'Could not load available holidays.');
        if (!cancelled) setFloatingHolidays(data.holidays || []);
      } catch {
        if (!cancelled) setFloatingHolidays([]);
      }
    };
    loadFloatingHolidays();
    return () => { cancelled = true; };
  }, [headers, user]);

  useEffect(() => {
    if (!selectedHoliday) return;
    setLeaveForm((current) => ({
      ...current,
      fromDate: selectedHoliday.holiday_date,
      toDate: selectedHoliday.holiday_date,
      reason: `${selectedLeaveType?.type || 'Holiday'}: ${selectedHoliday.name}`,
    }));
  }, [selectedHoliday, selectedLeaveType?.type]);

  useEffect(() => {
    if (!leaveForm.fromDate || !leaveForm.toDate) {
      setWorkingDays(null);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setLoadingWorkingDays(true);
      try {
        const params = new URLSearchParams({ start_date: leaveForm.fromDate, end_date: leaveForm.toDate });
        const res = await fetch(`${API_BASE}/holidays/working-days?${params.toString()}`, { headers });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(data?.detail || 'Could not calculate working days.');
        if (!cancelled) setWorkingDays(data);
      } catch {
        if (!cancelled) setWorkingDays(null);
      } finally {
        if (!cancelled) setLoadingWorkingDays(false);
      }
    }, 500);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [headers, leaveForm.fromDate, leaveForm.toDate]);

  useEffect(() => {
    if (quickLeaveApplied || loadingLeave || leaveBalances.length === 0) return;
    if (searchParams.get('quick') !== 'sick-today') return;
    const sickLeave = leaveBalances.find((leave) => leave.code?.toUpperCase() === 'SL' || leave.type.toLowerCase() === 'sick leave');
    if (!sickLeave) {
      setLeaveError('Sick Leave is not available for your profile.');
      setQuickLeaveApplied(true);
      return;
    }
    setLeaveForm({
      leaveTypeId: sickLeave.leave_type_id,
      fromDate: todayInput,
      toDate: todayInput,
      reason: 'Reporting sick leave for today.',
    });
    setLeaveSuccess('Sick Leave for today is ready. Review and submit the request.');
    setQuickLeaveApplied(true);
  }, [leaveBalances, loadingLeave, quickLeaveApplied, searchParams, todayInput]);

  const cancelLeaveEdit = () => {
    setEditingLeaveId(null);
    setLeaveForm((current) => ({
      leaveTypeId: firstSelectableLeaveTypeId || current.leaveTypeId,
      fromDate: '',
      toDate: '',
      reason: '',
    }));
    setSelectedHolidayId('');
    setLeaveSuccess(null);
  };

  const editLeaveDraft = (request: LeaveRequestItem) => {
    if (request.status !== 'draft') return;
    setEditingLeaveId(request.id);
    setLeaveForm({
      leaveTypeId: request.leave_type_id,
      fromDate: request.start_date,
      toDate: request.end_date,
      reason: request.reason || '',
    });
    setSelectedHolidayId(request.holiday_id || '');
    setLeaveError(null);
    setLeaveSuccess('Draft loaded. Make your changes and save or submit.');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const deleteLeaveDraft = async (request: LeaveRequestItem) => {
    if (request.status !== 'draft') return;
    if (confirmDeleteId !== request.id) {
      setConfirmDeleteId(request.id);
      return;
    }
    setSavingLeave('draft');
    setLeaveError(null);
    setLeaveSuccess(null);
    try {
      const res = await fetch(`${API_BASE}/leaves/me/requests/${request.id}`, {
        method: 'DELETE',
        headers,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not delete draft leave request.');
      setLeaveSummary(data);
      if (editingLeaveId === request.id) {
        setEditingLeaveId(null);
        setLeaveForm((current) => ({
          leaveTypeId: (data.balances || []).find((leave: LeaveBalanceItem) => {
            const effective = effectiveLeaveAvailable(leave);
            return !leave.is_paid || effective === null || effective > 0;
          })?.leave_type_id || data.balances?.[0]?.leave_type_id || current.leaveTypeId,
          fromDate: '',
          toDate: '',
          reason: '',
        }));
      }
      setLeaveSuccess('Draft leave request deleted.');
      setConfirmDeleteId(null);
    } catch (err) {
      setLeaveError(err instanceof Error ? err.message : 'Could not delete draft leave request.');
    } finally {
      setSavingLeave(null);
    }
  };

  const withdrawLeaveRequest = async (request: LeaveRequestItem) => {
    if (request.status !== 'pending') return;
    if (confirmWithdrawId !== request.id) {
      setConfirmWithdrawId(request.id);
      setConfirmDeleteId(null);
      return;
    }
    setWithdrawingLeaveId(request.id);
    setLeaveError(null);
    setLeaveSuccess(null);
    try {
      const res = await fetch(`${API_BASE}/leaves/me/requests/${request.id}/withdraw`, {
        method: 'POST',
        headers,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not withdraw leave request.');
      setLeaveSummary(data);
      setLeaveSuccess('Pending leave request withdrawn.');
      setConfirmWithdrawId(null);
    } catch (err) {
      setLeaveError(err instanceof Error ? err.message : 'Could not withdraw leave request.');
    } finally {
      setWithdrawingLeaveId(null);
    }
  };

  const requestedWorkingDays = workingDays?.working_days || 0;
  const balanceNow = selectedEffectiveAvailable;
  const balanceAfter = balanceNow === null ? null : balanceNow - requestedWorkingDays;
  const hasInsufficientBalance = Boolean(
    selectedLeaveType?.is_paid
    && balanceAfter !== null
    && requestedWorkingDays > 0
    && balanceAfter < 0
  );
  const formComplete = Boolean(
    leaveForm.leaveTypeId
    && leaveForm.fromDate
    && leaveForm.toDate
    && (isHolidayLeave ? selectedHolidayId : leaveForm.reason.trim())
  );
  const submitDisabled = Boolean(
    savingLeave
    || loadingLeave
    || loadingWorkingDays
    || !formComplete
    || requestedWorkingDays <= 0
    || selectedLeaveUnavailable
    || hasInsufficientBalance
    || (leavePolicyMessage && selectedPolicy?.allow_future_dates === false)
  );
  const requestDateLabel = leaveForm.fromDate && leaveForm.toDate
    ? `${formatDate(leaveForm.fromDate)} – ${formatDate(leaveForm.toDate)}`
    : 'Select dates';

  return (
    <PageShell
      title="Apply Leave"
      description="Request time off and see its impact on your balance before submitting."
      className="-mx-[var(--layout-main-padding-x)] -my-[var(--layout-main-padding-y)] min-h-screen bg-[#f7f3ec] px-[var(--layout-main-padding-x)] py-[var(--layout-main-padding-y)]"
    >
      {leaveError && <div className="mb-4 rounded-xl border border-[#d64545]/20 bg-[#fcecec] px-4 py-3 text-sm text-[#d64545]">{leaveError}</div>}
      {leaveSuccess && <div className="mb-4 rounded-xl border border-[#3f9b52]/20 bg-[#e5f3e5] px-4 py-3 text-sm text-[#3f7d3f]">{leaveSuccess}</div>}

      {editingLeaveId && <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#d97a34]/25 bg-[#fff7ef] px-4 py-3 text-sm text-[#a7561b]"><span className="font-semibold">Editing saved draft</span><button type="button" onClick={cancelLeaveEdit} className="text-xs font-bold text-[#d97a34] hover:underline">Cancel edit</button></div>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(330px,1fr)] xl:items-start">
        <section className="rounded-2xl border border-[#ece5d8] bg-white p-5 shadow-[0_3px_10px_rgba(60,40,10,.025)] sm:p-7">
          <div className="grid gap-5">
            <label className="block">
              <span className="mb-2 block text-[13px] font-bold text-[#1f2430]">Leave Type</span>
              <div className="relative">
                <select value={leaveForm.leaveTypeId} onChange={(event) => { updateLeaveForm('leaveTypeId', event.target.value); setSelectedHolidayId(''); setLeaveError(null); }} className="h-12 w-full appearance-none rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-4 pr-11 text-sm font-medium text-[#1f2430] outline-none transition focus:border-[#d97a34] focus:ring-2 focus:ring-[#d97a34]/10">
                  {leaveBalances.map((leave) => {
                    const effective = effectiveLeaveAvailable(leave);
                    const disabled = Boolean(leave.is_paid && effective !== null && effective <= 0);
                    return <option key={leave.leave_type_id} value={leave.leave_type_id} disabled={disabled}>{leave.type}{effective !== null ? ` — ${formatNumber(effective)} available` : ' — no balance limit'}{disabled ? leave.pending > 0 ? ' (pending)' : ' (exhausted)' : ''}</option>;
                  })}
                </select>
                <ChevronDown size={17} aria-hidden="true" className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[#b8611f]" />
              </div>
            </label>

            {isHolidayLeave && <div>
              <div className="mb-2 text-[13px] font-bold text-[#1f2430]">Select Holiday</div>
              <div className="grid gap-2 sm:grid-cols-2">
                {floatingHolidays.filter((holiday) => selectedLeaveCode === 'FL' ? holiday.holiday_type === 'floating' : holiday.holiday_type === 'optional').length === 0 ? <div className="rounded-[10px] border border-dashed border-[#ddd1bc] bg-[#faf8f3] px-4 py-5 text-sm text-[#8a8371] sm:col-span-2">No available holidays for this leave type.</div> : floatingHolidays.filter((holiday) => selectedLeaveCode === 'FL' ? holiday.holiday_type === 'floating' : holiday.holiday_type === 'optional').map((holiday) => {
                  const isUnavailableDate = Boolean((minAllowedDate && holiday.holiday_date < minAllowedDate) || (maxAllowedDate && holiday.holiday_date > maxAllowedDate));
                  return <label key={holiday.id} className={cn('flex gap-3 rounded-[10px] border px-4 py-3', isUnavailableDate ? 'cursor-not-allowed border-[#ece5d8] bg-gray-50 opacity-60' : selectedHolidayId === holiday.id ? 'cursor-pointer border-[#d97a34] bg-[#fff7ef]' : 'cursor-pointer border-[#e4daca] bg-[#faf8f3] hover:border-[#d97a34]/50')}><input type="radio" checked={selectedHolidayId === holiday.id} disabled={isUnavailableDate} onChange={() => setSelectedHolidayId(holiday.id)} className="mt-1 accent-[#d97a34]" /><span><span className="block text-sm font-bold">{holiday.name}</span><span className="mt-0.5 block text-xs text-[#8a8371]">{formatDate(holiday.holiday_date)} · {holidayRegionLabel(holiday.regions)}</span></span></label>;
                })}
              </div>
            </div>}

            <div className="grid gap-4 sm:grid-cols-2">
              <label><span className="mb-2 block text-[13px] font-bold text-[#1f2430]">From</span><input type="date" value={leaveForm.fromDate} min={minAllowedDate} max={maxAllowedDate} onChange={(event) => updateLeaveForm('fromDate', event.target.value)} className="h-12 w-full rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-4 text-sm text-[#1f2430] outline-none transition focus:border-[#d97a34] focus:ring-2 focus:ring-[#d97a34]/10" /></label>
              <label><span className="mb-2 block text-[13px] font-bold text-[#1f2430]">To</span><input type="date" value={leaveForm.toDate} min={leaveForm.fromDate || minAllowedDate} max={maxAllowedDate} onChange={(event) => updateLeaveForm('toDate', event.target.value)} className="h-12 w-full rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-4 text-sm text-[#1f2430] outline-none transition focus:border-[#d97a34] focus:ring-2 focus:ring-[#d97a34]/10" /></label>
            </div>

            <div className="flex min-h-[52px] flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-[#ead8bd] bg-[#fbf5ea] px-4 py-3 text-sm text-[#8a6a3a]">
              <CalendarCheck size={17} className="text-[#d97a34]" />
              {loadingWorkingDays ? <span>Calculating working days…</span> : leaveForm.fromDate && leaveForm.toDate ? <><span>You&apos;re requesting</span><strong className="text-[15px] text-[#b8611f]">{requestedWorkingDays} working {requestedWorkingDays === 1 ? 'day' : 'days'}</strong><span>({requestDateLabel} · {workingDays?.weekends || 0} weekend day{workingDays?.weekends === 1 ? '' : 's'}{workingDays?.holidays ? ` and ${workingDays.holidays} holiday${workingDays.holidays === 1 ? '' : 's'}` : ''} excluded)</span></> : <span>Select a date range to calculate working days; weekends and company holidays will be excluded.</span>}
            </div>

            {!isHolidayLeave && <label className="block">
              <div className="mb-2 flex justify-between gap-4"><span className="text-[13px] font-bold text-[#1f2430]">Reason</span><span className="text-xs text-[#a99e8a]">{leaveForm.reason.length} / 200</span></div>
              <textarea value={leaveForm.reason} onChange={(event) => updateLeaveForm('reason', event.target.value)} placeholder="Add a short reason…" rows={4} maxLength={200} className="w-full resize-none rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-4 py-3 text-sm text-[#1f2430] outline-none transition placeholder:text-[#aaa394] focus:border-[#d97a34] focus:ring-2 focus:ring-[#d97a34]/10" />
              {leavePolicyMessage && <div className={cn('mt-2 text-xs font-semibold', selectedPolicy?.allow_future_dates === false ? 'text-[#d64545]' : 'text-[#c47b1a]')}>{leavePolicyMessage}</div>}
            </label>}
          </div>
        </section>

        <aside className="rounded-2xl border border-[#ece5d8] bg-white p-5 shadow-[0_3px_10px_rgba(60,40,10,.025)] sm:p-7 xl:sticky xl:top-5">
          <div className="mb-5 flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#fbeee1] text-[#d97a34]"><Send size={17} /></span><h2 className="text-[17px] font-bold">Request Summary</h2></div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between gap-4"><span className="text-[#8a8371]">Leave type</span><strong className="text-right">{selectedLeaveType?.type || 'Not selected'}</strong></div>
            <div className="flex justify-between gap-4"><span className="text-[#8a8371]">Dates</span><strong className="text-right">{requestDateLabel}</strong></div>
            <div className="flex justify-between gap-4"><span className="text-[#8a8371]">Working days</span><strong>{loadingWorkingDays ? '…' : `${requestedWorkingDays} ${requestedWorkingDays === 1 ? 'day' : 'days'}`}</strong></div>
          </div>
          <div className="my-5 border-t border-[#eadfce]" />
          <div className="space-y-3 text-sm">
            <div className="flex justify-between gap-4"><span className="text-[#8a8371]">Balance now</span><strong>{balanceNow === null ? 'No limit' : `${formatNumber(balanceNow)} days`}</strong></div>
            <div className="flex justify-between gap-4"><span className="text-[#8a8371]">After this request</span><strong className={hasInsufficientBalance ? 'text-[#d64545]' : 'text-[#3f9b52]'}>{balanceAfter === null ? 'No limit' : `${formatNumber(balanceAfter)} days`}</strong></div>
            {hasInsufficientBalance && <div className="rounded-lg bg-[#fcecec] px-3 py-2 text-xs font-semibold text-[#d64545]">This request exceeds your available balance.</div>}
          </div>
          <div className="mt-5 flex items-center gap-3 rounded-xl border border-[#e5d9c5] bg-[#fbf5ea] px-4 py-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#2b3243] text-[11px] font-bold text-white">{dashboardInitials(reportingManager)}</span>
            <div className="min-w-0"><div className="text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">Approver</div><div className="truncate text-sm font-bold">{reportingManager}</div></div>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <Button variant="ghost" disabled={!!savingLeave || loadingLeave || !formComplete} onClick={() => saveLeaveRequest('draft')} className="border-[#e4daca] bg-white text-[#1f2430] hover:bg-[#fbf5ea]">{savingLeave === 'draft' ? 'Saving…' : 'Save Draft'}</Button>
            <Button disabled={submitDisabled} onClick={() => saveLeaveRequest('submit')} className="border-[#d97a34] bg-[#d97a34] shadow-[0_7px_16px_rgba(217,122,52,.18)] hover:bg-[#c9611f]">{savingLeave === 'submit' ? 'Submitting…' : editingLeaveId ? 'Submit Draft' : 'Submit Request'}</Button>
          </div>
        </aside>
      </div>

      <section className="mt-5 rounded-2xl border border-[#ece5d8] bg-white p-5 shadow-[0_3px_10px_rgba(60,40,10,.025)] sm:p-7">
        <div className="mb-5 flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#fbeee1] text-[#d97a34]"><WalletCards size={18} /></span><h2 className="text-[17px] font-bold">Leave Balance</h2></div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {loadingLeave ? <div className="rounded-xl border border-[#ece5d8] bg-[#faf8f3] p-5 text-sm text-[#8a8371]">Loading leave balances…</div> : leaveBalances.map((leave) => {
            const total = typeof leave.total === 'number' ? leave.total : 0;
            const available = effectiveLeaveAvailable(leave) || 0;
            const used = typeof leave.used === 'number' ? leave.used : 0;
            const pending = typeof leave.pending === 'number' ? leave.pending : 0;
            const usedPercent = total > 0 ? Math.min(100, (used / total) * 100) : 0;
            const pendingPercent = total > 0 ? Math.min(100 - usedPercent, (pending / total) * 100) : 0;
            const availablePercent = total > 0 ? Math.max(0, 100 - usedPercent - pendingPercent) : 0;
            const selected = leave.leave_type_id === leaveForm.leaveTypeId;
            return <button type="button" key={leave.leave_type_id} onClick={() => { updateLeaveForm('leaveTypeId', leave.leave_type_id); setSelectedHolidayId(''); }} className={cn('relative rounded-2xl border p-5 text-left transition', selected ? 'border-2 border-[#d97a34] bg-[#fff7ef] shadow-[0_7px_18px_rgba(217,122,52,.1)]' : 'border-[#ece5d8] bg-[#fffdf9] hover:border-[#d97a34]/40')}>
              {selected && <span className="absolute -top-2.5 left-4 rounded-full bg-[#d97a34] px-2.5 py-1 text-[9px] font-bold tracking-wide text-white">APPLYING</span>}
              <div className="flex items-start justify-between gap-3"><div><div className="text-sm font-bold">{leave.type}</div><div className="mt-1 text-[10px] font-semibold uppercase tracking-[.08em] text-[#a99e8a]">Days available</div></div><div className={cn('text-[25px] font-bold', available <= 0 ? 'text-[#aaa394]' : 'text-[#d97a34]')}>{typeof leave.available === 'string' ? leave.available : formatNumber(available)}</div></div>
              <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-[#eee9df]"><span className="h-full bg-[#aba69d]" style={{ width: `${usedPercent}%` }} /><span className="h-full bg-[#e0a23a]" style={{ width: `${pendingPercent}%` }} /><span className="h-full bg-[#d97a34]" style={{ width: `${availablePercent}%` }} /></div>
              <div className="mt-3 text-xs text-[#8a8371]">Used {formatNumber(used)} · Pending {formatNumber(pending)}</div>
              <div className="mt-3 border-t border-[#eee5d6] pt-3 text-[11px] text-[#a99e8a]">{leave.expiry_label || (leave.is_carry_forward ? `Carry forward up to ${formatNumber(leave.max_carry_forward_days)} days` : 'No balance expiry')}</div>
            </button>;
          })}
        </div>
      </section>

      <section className="mt-5 overflow-hidden rounded-2xl border border-[#ece5d8] bg-white shadow-[0_3px_10px_rgba(60,40,10,.025)]">
        <div className="flex items-center gap-3 border-b border-[#ece5d8] px-5 py-4 sm:px-7"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#e5f3e5] text-[#3f9b52]"><ClipboardCheck size={18} /></span><h2 className="text-[17px] font-bold">My Leave Requests</h2></div>
        {leaveRequests.length === 0 ? <div className="m-5 rounded-xl border border-dashed border-[#ddd1bc] px-5 py-10 text-center sm:m-7"><div className="text-sm font-semibold text-[#8a8371]">No leave requests yet.</div><div className="mt-1 text-xs text-[#a99e8a]">Submitted requests will appear here with their approval status.</div></div> : <div className="overflow-x-auto"><div className="min-w-[900px]"><div className="grid grid-cols-[1.1fr_1fr_1.3fr_110px_130px] gap-4 border-b border-[#ece5d8] bg-[#faf8f3] px-7 py-3 text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]"><div>Leave</div><div>Dates</div><div>Reason / Progress</div><div className="text-center">Status</div><div className="text-center">Actions</div></div><div className="divide-y divide-[#eee7dc]">{leaveRequests.map((request) => <div key={request.id}>
          <div className="grid grid-cols-[1.1fr_1fr_1.3fr_110px_130px] items-center gap-4 px-7 py-4 text-sm"><div><div className="font-bold">{request.leave_type}</div><div className="mt-1 text-xs text-[#8a8371]">{formatNumber(request.total_days)} working {request.total_days === 1 ? 'day' : 'days'}</div></div><div className="text-xs text-[#8a8371]">{formatDate(request.start_date)} – {formatDate(request.end_date)}</div><div className="min-w-0"><div className="truncate text-xs text-[#8a8371]">{request.reason}</div><div className="mt-1 text-[11px] text-[#a99e8a]">{request.status === 'pending' ? `Pending with ${request.pending_with || reportingManager}` : request.reviewed_by ? `Reviewed by ${request.reviewed_by}` : 'Saved draft'}</div></div><div className="flex justify-center"><Badge variant={request.status === 'approved' ? 'success' : request.status === 'rejected' ? 'error' : request.status === 'pending' ? 'warning' : 'neutral'}>{statusLabel(request.status)}</Badge></div><div className="flex justify-center gap-2">{request.status === 'draft' ? <><button type="button" onClick={() => editLeaveDraft(request)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#ead8bd] bg-[#fff7ef] text-[#d97a34]" aria-label="Edit draft"><Pencil size={14} /></button><button type="button" disabled={!!savingLeave} onClick={() => deleteLeaveDraft(request)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#ece5d8] text-[#8a8371] hover:bg-[#fcecec] hover:text-[#d64545]" aria-label="Delete draft"><Trash2 size={14} /></button></> : request.status === 'pending' ? <button type="button" disabled={withdrawingLeaveId === request.id} onClick={() => withdrawLeaveRequest(request)} className="rounded-lg border border-[#ece5d8] px-3 py-2 text-xs font-bold text-[#d64545] hover:bg-[#fcecec] disabled:opacity-50">Withdraw</button> : <span className="text-xs text-[#a99e8a]">—</span>}</div></div>
          {confirmDeleteId === request.id && <div className="mx-7 mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-[#d64545]/20 bg-[#fcecec] px-3 py-2 text-sm text-[#d64545]"><span className="mr-auto font-semibold">Delete this draft?</span><Button size="sm" variant="ghost" onClick={() => setConfirmDeleteId(null)}>Cancel</Button><Button size="sm" onClick={() => deleteLeaveDraft(request)}>Yes, delete</Button></div>}
          {confirmWithdrawId === request.id && <div className="mx-7 mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-[#d64545]/20 bg-[#fcecec] px-3 py-2 text-sm text-[#d64545]"><span className="mr-auto font-semibold">Withdraw this pending request?</span><Button size="sm" variant="ghost" onClick={() => setConfirmWithdrawId(null)}>Cancel</Button><Button size="sm" onClick={() => withdrawLeaveRequest(request)} disabled={withdrawingLeaveId === request.id}>{withdrawingLeaveId === request.id ? 'Withdrawing…' : 'Yes, withdraw'}</Button></div>}
        </div>)}</div></div></div>}
      </section>
    </PageShell>
  );

}

function RejectionReasonModal({
  intent,
  submitting,
  onClose,
  onConfirm,
}: {
  intent: RejectionIntent;
  submitting: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const canSubmit = reason.trim().length > 0;

  return createPortal(
    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/35 p-6 backdrop-blur-sm">
      <Card className="w-full max-w-lg overflow-hidden shadow-[0_24px_80px_rgba(31,41,55,0.24)]">
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-6 py-5">
          <div>
            <h2 className="text-lg font-bold text-[var(--color-brand-navy)]">Reject approval</h2>
            <p className="mt-1 text-sm text-gray-500">{intent.title}</p>
          </div>
          <button onClick={onClose} disabled={submitting} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg disabled:cursor-not-allowed disabled:opacity-50">
            <X size={18} />
          </button>
        </div>
        <div className="p-6">
          {intent.subtitle && (
            <div className="mb-4 rounded-xl border border-[var(--color-border)] bg-warm-bg p-4 text-sm text-gray-600">
              {intent.subtitle}
            </div>
          )}
          <label className="grid gap-2 text-sm font-semibold text-[var(--color-brand-navy)]">
            Rejection reason
            <textarea
              value={reason}
              maxLength={300}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Explain why this approval is being rejected."
              className="min-h-[120px] rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-3 text-sm outline-none focus:border-accent"
              autoFocus
            />
          </label>
          <div className="mt-2 flex justify-between gap-3 text-xs text-gray-500">
            <span>This reason will be visible to the employee and saved for audit history.</span>
            <span>{reason.length}/300</span>
          </div>
        </div>
        <div className="flex justify-end gap-3 border-t border-[var(--color-border)] px-6 py-4">
          <Button variant="ghost" disabled={submitting} onClick={onClose}>Keep Pending</Button>
          <Button disabled={submitting || !canSubmit} onClick={() => onConfirm(reason.trim())}>
            {submitting ? 'Rejecting' : 'Reject'}
          </Button>
        </div>
      </Card>
    </div>,
    document.body
  );
}

export function LeaveApprovalsPage() {
  const { user } = useAuth();
  const [leaveApprovalRows, setLeaveApprovalRows] = useState<LeaveRequestItem[]>([]);
  const [timesheetApprovalRows, setTimesheetApprovalRows] = useState<TimesheetApprovalItem[]>([]);
  const [requestApprovalRows, setRequestApprovalRows] = useState<RequestApprovalItem[]>([]);
  const [loadingApprovals, setLoadingApprovals] = useState(true);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewTimesheet, setReviewTimesheet] = useState<TimesheetApprovalItem | null>(null);
  const [reviewCompliance, setReviewCompliance] = useState<ComplianceReport | null>(null);
  const [reviewComplianceLoading, setReviewComplianceLoading] = useState(false);
  const [reviewComplianceOpen, setReviewComplianceOpen] = useState(false);
  const [rejectionIntent, setRejectionIntent] = useState<RejectionIntent | null>(null);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const loadApprovals = useCallback(async () => {
    if (!user || !canReviewApprovals(user.role)) return;
    setLoadingApprovals(true);
    setApprovalError(null);
    try {
      const [leaveRes, timesheetRes, requestRes] = await Promise.all([
        fetch(`${API_BASE}/leaves/approvals`, { headers }),
        fetch(`${API_BASE}/timesheets/approvals`, { headers }),
        fetch(`${API_BASE}/requests/queue`, { headers }),
      ]);
      const leaveData = await leaveRes.json().catch(() => null);
      const timesheetData = await timesheetRes.json().catch(() => null);
      const requestData = await requestRes.json().catch(() => null);
      if (!leaveRes.ok) throw new Error(leaveData?.detail || 'Could not load leave approvals.');
      if (!timesheetRes.ok) throw new Error(timesheetData?.detail || 'Could not load timesheet approvals.');
      if (!requestRes.ok) throw new Error(requestData?.detail || 'Could not load request approvals.');
      setLeaveApprovalRows(leaveData.approvals || []);
      setTimesheetApprovalRows(timesheetData.approvals || []);
      setRequestApprovalRows(requestData.items || []);
    } catch (err) {
      setApprovalError(err instanceof Error ? err.message : 'Could not load approvals.');
    } finally {
      setLoadingApprovals(false);
    }
  }, [headers, user]);

  useEffect(() => {
    loadApprovals();
  }, [loadApprovals]);

  useEffect(() => {
    const entryId = reviewTimesheet?.entries?.[0]?.id;
    if (!entryId || !user) {
      setReviewCompliance(null);
      setReviewComplianceLoading(false);
      return;
    }
    let cancelled = false;
    setReviewCompliance(null);
    setReviewComplianceLoading(true);
    fetch(`${API_BASE}/timesheets/${entryId}/allocation-compliance`, { headers })
      .then(async (res) => {
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(data?.detail || 'Could not load allocation compliance.');
        return data as ComplianceReport;
      })
      .then((data) => {
        if (cancelled) return;
        setReviewCompliance(data);
        setReviewComplianceOpen(data.overall_status === 'warning' || data.overall_status === 'violation');
      })
      .catch((err) => {
        if (cancelled) return;
        setReviewCompliance(null);
        setApprovalError(err instanceof Error ? err.message : 'Could not load allocation compliance.');
      })
      .finally(() => {
        if (!cancelled) setReviewComplianceLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [headers, reviewTimesheet, user]);

  const decideLeave = async (requestId: string, decision: 'approve' | 'reject', reviewerNotes: string | null = null) => {
    setReviewingId(requestId);
    setApprovalError(null);
    try {
      const res = await fetch(`${API_BASE}/leaves/approvals/${requestId}/decision`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ decision, reviewer_notes: reviewerNotes || null }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || `Could not ${decision} leave request.`);
      setLeaveApprovalRows(data.approvals || []);
      if (decision === 'reject') setRejectionIntent(null);
    } catch (err) {
      setApprovalError(err instanceof Error ? err.message : `Could not ${decision} leave request.`);
    } finally {
      setReviewingId(null);
    }
  };

  const decideTimesheet = async (approval: TimesheetApprovalItem, decision: 'approve' | 'reject', reviewerNotes: string | null = null) => {
    const approvalKey = `${approval.employee_id}-${approval.week_start}`;
    setReviewingId(approvalKey);
    setApprovalError(null);
    try {
      const res = await fetch(`${API_BASE}/timesheets/approvals/${approval.employee_id}/${approval.week_start}/decision`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ decision, reviewer_notes: reviewerNotes || null }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || `Could not ${decision} timesheet.`);
      setTimesheetApprovalRows(data.approvals || []);
      setReviewTimesheet(null);
      if (decision === 'reject') setRejectionIntent(null);
    } catch (err) {
      setApprovalError(err instanceof Error ? err.message : `Could not ${decision} timesheet.`);
    } finally {
      setReviewingId(null);
    }
  };

  const decideRequest = async (request: RequestApprovalItem, decision: 'approve' | 'reject', reason: string | null = null) => {
    setReviewingId(request.id);
    setApprovalError(null);
    try {
      const res = await fetch(`${API_BASE}/requests/${request.id}/${decision}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(decision === 'approve' ? { notes: null } : { reason: reason?.trim() || 'Rejected by manager.' }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || `Could not ${decision} request.`);
      setRequestApprovalRows((current) => current.filter((row) => row.id !== request.id));
      if (decision === 'reject') setRejectionIntent(null);
    } catch (err) {
      setApprovalError(err instanceof Error ? err.message : `Could not ${decision} request.`);
    } finally {
      setReviewingId(null);
    }
  };

  const openLeaveRejection = (approval: LeaveRequestItem) => {
    setRejectionIntent({
      kind: 'leave',
      id: approval.id,
      title: `Leave - ${approval.leave_type}`,
      subtitle: `${approval.employee_name} · ${formatDate(approval.start_date)} - ${formatDate(approval.end_date)}`,
    });
  };

  const openTimesheetRejection = (approval: TimesheetApprovalItem) => {
    setRejectionIntent({
      kind: 'timesheet',
      approval,
      title: 'Timesheet',
      subtitle: `${approval.employee_name} · ${formatDate(approval.week_start)} - ${formatDate(approval.week_end)}`,
    });
  };

  const openRequestRejection = (approval: RequestApprovalItem) => {
    setRejectionIntent({
      kind: 'request',
      request: approval,
      title: approval.request_type_label || approval.title,
      subtitle: `${approval.employee_name} · ${requestApprovalDates(approval)}`,
    });
  };

  const confirmRejection = (reason: string) => {
    if (!rejectionIntent) return;
    if (rejectionIntent.kind === 'leave') {
      void decideLeave(rejectionIntent.id, 'reject', reason);
    } else if (rejectionIntent.kind === 'timesheet') {
      void decideTimesheet(rejectionIntent.approval, 'reject', reason);
    } else {
      void decideRequest(rejectionIntent.request, 'reject', reason);
    }
  };

  const totalApprovalRows = leaveApprovalRows.length + timesheetApprovalRows.length + requestApprovalRows.length;
  const reviewWeekDates = useMemo(() => {
    if (!reviewTimesheet) return [];
    const start = new Date(`${reviewTimesheet.week_start}T00:00:00`);
    return Array.from({ length: 7 }, (_, index) => addDays(start, index));
  }, [reviewTimesheet]);
  const reviewEntriesForDate = (dateKey: string) => reviewTimesheet?.entries.filter((entry) => entry.work_date === dateKey) || [];
  const reviewLeaveForDate = (dateKey: string) => reviewTimesheet?.leave_days.find((leave) => leave.date === dateKey);
  const reviewEntryHours = (dateKey: string, code?: string) => reviewEntriesForDate(dateKey)
    .filter((entry) => !code || entry.entry_code === code)
    .reduce((sum, entry) => sum + entry.hours, 0);

  if (!canReviewApprovals(user?.role)) {
    return <Navigate to="/employee" replace />;
  }

  return (
    <PageShell title="Approvals" description="Review leave, attendance, and timesheet approvals assigned to you.">
      {approvalError && (
        <div className="mb-5 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {approvalError}
        </div>
      )}
      <Card className="overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
            <tr>
              <th className="px-5 py-3 font-bold">Employee</th>
              <th className="px-5 py-3 font-bold">Request</th>
              <th className="px-5 py-3 font-bold">Dates</th>
              <th className="px-5 py-3 font-bold">Status</th>
              <th className="px-5 py-3 text-right font-bold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {loadingApprovals ? (
              <tr><td colSpan={5} className="px-5 py-8 text-center text-gray-500">Loading approvals...</td></tr>
            ) : totalApprovalRows === 0 ? (
              <tr><td colSpan={5} className="px-5 py-8 text-center text-gray-500">No pending approvals.</td></tr>
            ) : (
              <>
                {leaveApprovalRows.map((approval) => (
                  <tr key={`leave-${approval.id}`} className="text-[var(--color-brand-navy)]">
                    <td className="px-5 py-4 font-semibold">{approval.employee_name}</td>
                    <td className="px-5 py-4">
                      <div className="font-semibold">Leave - {approval.leave_type}</div>
                      <div className="text-xs text-gray-500">{approval.reason}</div>
                    </td>
                    <td className="px-5 py-4">{formatDate(approval.start_date)} - {formatDate(approval.end_date)} <span className="text-gray-400">({approval.total_days}d)</span></td>
                    <td className="px-5 py-4"><Badge variant="warning">pending</Badge></td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="soft" disabled={reviewingId === approval.id} onClick={() => decideLeave(approval.id, 'approve')}>Approve</Button>
                        <Button size="sm" variant="ghost" disabled={reviewingId === approval.id} onClick={() => openLeaveRejection(approval)}>Reject</Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {requestApprovalRows.map((approval) => (
                  <tr key={`request-${approval.id}`} className="text-[var(--color-brand-navy)]">
                    <td className="px-5 py-4 font-semibold">{approval.employee_name}</td>
                    <td className="px-5 py-4">
                      <div className="font-semibold">{approval.request_type_label || approval.title}</div>
                      <div className="text-xs text-gray-500">
                        {approval.ticket_number || 'Request'}
                        {requestApprovalMeta(approval) ? ` · ${requestApprovalMeta(approval)}` : ''}
                      </div>
                    </td>
                    <td className="px-5 py-4">{requestApprovalDates(approval)}</td>
                    <td className="px-5 py-4"><Badge variant="warning">pending</Badge></td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="soft" disabled={reviewingId === approval.id} onClick={() => decideRequest(approval, 'approve')}>Approve</Button>
                        <Button size="sm" variant="ghost" disabled={reviewingId === approval.id} onClick={() => openRequestRejection(approval)}>Reject</Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {timesheetApprovalRows.map((approval) => {
                  const approvalKey = `${approval.employee_id}-${approval.week_start}`;
                  return (
                    <tr key={`timesheet-${approvalKey}`} className="text-[var(--color-brand-navy)]">
                      <td className="px-5 py-4 font-semibold">{approval.employee_name}</td>
                      <td className="px-5 py-4">
                        <div className="font-semibold">Timesheet</div>
                        <div className="text-xs text-gray-500">
                          Working {approval.working_hours}h, Break {approval.break_hours}h, Leave {approval.leave_hours}h
                          {approval.overtime_hours > 0 ? `, Overtime ${approval.overtime_hours}h` : ''}
                        </div>
                      </td>
                      <td className="px-5 py-4">{formatDate(approval.week_start)} - {formatDate(approval.week_end)}</td>
                      <td className="px-5 py-4"><Badge variant="warning">submitted</Badge></td>
                      <td className="px-5 py-4">
                        <div className="flex justify-end gap-2">
                          <Button size="sm" variant="soft" onClick={() => setReviewTimesheet(approval)}>Review</Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </>
            )}
          </tbody>
        </table>
      </Card>

      {reviewTimesheet && createPortal((
        <div className="animate-modal-backdrop fixed inset-0 z-[120] flex items-center justify-center overflow-hidden bg-[var(--color-brand-navy)]/68 p-4 backdrop-blur-sm sm:p-6 lg:p-8">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="timesheet-review-title"
            className="animate-modal-pop relative flex max-h-[calc(100vh-2rem)] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-white/80 bg-[var(--color-brand-surface)] shadow-[0_32px_110px_rgba(0,0,0,0.42),0_10px_36px_rgba(17,24,39,0.22),0_0_0_1px_rgba(255,255,255,0.65)] ring-1 ring-black/10 sm:max-h-[calc(100vh-3rem)] lg:max-h-[calc(100vh-4rem)]"
          >
            <div className="h-1 shrink-0 bg-gradient-to-r from-olive via-sage to-status-info" />
            <div className="flex shrink-0 items-start justify-between gap-4 border-b border-[var(--color-border)] bg-white px-5 py-4 shadow-[0_1px_0_rgba(17,24,39,0.03)] sm:px-6">
              <div>
                <div id="timesheet-review-title" className="text-lg font-bold text-[var(--color-brand-navy)]">Timesheet Review</div>
                <div className="mt-1 text-sm text-gray-500">
                  {reviewTimesheet.employee_name} • {formatDate(reviewTimesheet.week_start)} - {formatDate(reviewTimesheet.week_end)}
                </div>
              </div>
              <button
                onClick={() => setReviewTimesheet(null)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-transparent text-gray-400 transition-colors hover:border-[var(--color-border)] hover:bg-hover-bg hover:text-[var(--color-brand-navy)]"
                title="Close"
              >
                <X size={17} />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto bg-[var(--color-brand-canvas)] px-5 py-4 sm:px-6">
              <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
                {[
                  ['Logged', `${reviewTimesheet.total_hours}h`],
                  ['Working', `${reviewTimesheet.working_hours}h`],
                  ['Break', `${reviewTimesheet.break_hours}h`],
                  ['Leave', `${reviewTimesheet.leave_hours}h`],
                  ['Overtime', `${reviewTimesheet.overtime_hours}h`],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-[var(--color-border)] bg-white px-3 py-2.5 shadow-[0_1px_2px_rgba(17,24,39,0.04)]">
                    <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{label}</div>
                    <div className={cn('mt-1 text-lg font-bold text-[var(--color-brand-navy)]', label === 'Overtime' && reviewTimesheet.overtime_hours > 0 && 'text-status-warning')}>{value}</div>
                  </div>
                ))}
              </div>

              <div className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-white shadow-[0_8px_22px_rgba(17,24,39,0.06)]">
                <table className="w-full min-w-[860px] text-left text-sm">
                  <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
                    <tr>
                      <th className="px-4 py-3 font-bold">Day</th>
                      <th className="px-4 py-3 font-bold">Work</th>
                      <th className="px-4 py-3 font-bold">Break</th>
                      <th className="px-4 py-3 font-bold">Leave</th>
                      <th className="px-4 py-3 font-bold">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)] bg-white">
                    {reviewWeekDates.map((dateValue) => {
                      const dateKey = toDateInput(dateValue);
                      const leave = reviewLeaveForDate(dateKey);
                      const isWeekend = isWeekendDate(dateValue);
                      const workHours = reviewEntriesForDate(dateKey)
                        .filter((entry) => entry.entry_code !== 'BRK')
                        .reduce((sum, entry) => sum + entry.hours, 0);
                      const breakHours = reviewEntryHours(dateKey, 'BRK');
                      return (
                        <tr key={dateKey}>
                          <td className="px-4 py-3 font-semibold text-[var(--color-brand-navy)]">
                            {dateValue.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                          </td>
                          <td className="px-4 py-3 font-bold">{workHours}h</td>
                          <td className="px-4 py-3">{breakHours}h</td>
                          <td className="px-4 py-3">
                            {leave ? <Badge variant={leave.status === 'approved' ? 'success' : 'warning'}>{leave.hours}h {leave.leave_type}</Badge> : '0h'}
                          </td>
                          <td className="px-4 py-3 text-gray-500">
                            {reviewEntriesForDate(dateKey).length === 0 ? (
                              <span>{isWeekend && !leave ? 'Non-working day / Weekend' : 'No time blocks'}</span>
                            ) : (
                              <div className="space-y-1">
                                {reviewEntriesForDate(dateKey).map((entry) => (
                                  <div key={entry.id}>
                                    <span className="font-semibold text-[var(--color-brand-navy)]">{entry.project_name}</span>
                                    <span className="text-gray-400"> • {entry.entry_code} • {entry.start_time?.slice(0, 5)}-{entry.end_time?.slice(0, 5)} • {entry.hours}h</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="mt-4">
                <AllocationCompliancePanel
                  report={reviewCompliance}
                  loading={reviewComplianceLoading}
                  open={reviewComplianceOpen}
                  onToggle={() => setReviewComplianceOpen((current) => !current)}
                />
              </div>

              {reviewTimesheet.overtime_hours > 0 && (
                <div className="mt-4 rounded-lg border border-status-warning/20 bg-status-warning/10 px-4 py-3 text-sm text-status-warning">
                  This timesheet includes {reviewTimesheet.overtime_hours}h overtime. Approval will also approve the overtime log.
                </div>
              )}
            </div>

            <div className="flex shrink-0 justify-end gap-2 border-t border-[var(--color-border)] bg-white px-5 py-4 shadow-[0_-1px_0_rgba(17,24,39,0.02)] sm:px-6">
              <Button variant="ghost" disabled={reviewingId === `${reviewTimesheet.employee_id}-${reviewTimesheet.week_start}`} onClick={() => openTimesheetRejection(reviewTimesheet)}>
                Reject
              </Button>
              <Button disabled={reviewingId === `${reviewTimesheet.employee_id}-${reviewTimesheet.week_start}`} onClick={() => decideTimesheet(reviewTimesheet, 'approve')}>
                Approve Timesheet
              </Button>
            </div>
          </div>
        </div>
      ), document.body)}
      {rejectionIntent && (
        <RejectionReasonModal
          intent={rejectionIntent}
          submitting={Boolean(reviewingId)}
          onClose={() => {
            if (reviewingId) return;
            setRejectionIntent(null);
          }}
          onConfirm={confirmRejection}
        />
      )}
    </PageShell>
  );
}

function TimeEntryDetailsPanel({
  activeCell,
  project,
  blocks,
  totalHours,
  saving,
  hasTimeBlocks,
  onClose,
  onAddBlock,
  onUpdateBlock,
  onUpdateBlockStart,
  onRemoveBlock,
  onSaveDraft,
}: {
  activeCell: { projectKey: string; date: string } | null;
  project: GridTimesheetProject | null;
  blocks: TimesheetRow[];
  totalHours: number;
  saving: 'draft' | 'submit' | null;
  hasTimeBlocks: boolean;
  onClose: () => void;
  onAddBlock: () => void;
  onUpdateBlock: (rowId: string, updates: Partial<TimesheetRow>) => void;
  onUpdateBlockStart: (block: TimesheetRow, startTime: string) => void;
  onRemoveBlock: (rowId: string) => void;
  onSaveDraft: () => void;
}) {
  const selectedDateLabel = activeCell
    ? new Date(`${activeCell.date}T00:00:00`).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
    : '';

  return (
    <aside className="overflow-hidden rounded-2xl border border-[#ece5d8] bg-white shadow-[0_3px_10px_rgba(60,40,10,.025)] xl:sticky xl:top-5">
      <div className="flex items-start justify-between border-b border-[#ece5d8] px-5 py-4"><div><h2 className="text-[17px] font-bold">Time Entry</h2><p className="mt-1 text-xs text-[#8a8371]">{activeCell ? 'Edit the selected day.' : 'Select a work-item day cell.'}</p></div>{activeCell && <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-[#a99e8a] hover:bg-[#fbf5ea]" aria-label="Close time entry"><X size={15} /></button>}</div>
      {activeCell && project ? <>
        <div className="max-h-[calc(100vh-240px)] overflow-y-auto p-5">
          <div className="mb-5 rounded-xl border border-[#ead8bd] bg-[#fff7ef] px-4 py-3"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="truncate text-sm font-bold">{project.name}</div><div className="mt-1 text-xs text-[#8a8371]">{selectedDateLabel}</div></div><span className="whitespace-nowrap rounded-full bg-[#fbeee1] px-2.5 py-1 text-[10px] font-bold text-[#b8611f]">{formatNumber(totalHours)}h total</span></div></div>
          <div className="mb-3 text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">Time Blocks</div>
          <div className="space-y-3">{blocks.map((block, index) => <div key={block.id} className="rounded-xl border border-[#ece5d8] bg-[#fffdf9] p-4">
            <div className="mb-3 flex items-center justify-between"><span className="text-xs font-bold">Block {index + 1}</span><button type="button" onClick={() => onRemoveBlock(block.id)} className="text-[#a99e8a] hover:text-[#d64545]" aria-label={`Delete block ${index + 1}`}><Trash2 size={14} /></button></div>
            <div className="grid grid-cols-2 gap-3"><label><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-[.07em] text-[#a99e8a]">From</span><input value={block.startTime} onChange={(event) => onUpdateBlockStart(block, event.target.value)} type="time" className="h-11 w-full rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-3 text-sm font-semibold outline-none focus:border-[#d97a34]" /></label><label><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-[.07em] text-[#a99e8a]">To</span><input value={block.endTime} onChange={(event) => onUpdateBlock(block.id, { endTime: event.target.value })} type="time" className="h-11 w-full rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-3 text-sm font-semibold outline-none focus:border-[#d97a34]" /></label></div>
            <div className="mt-3 flex items-center justify-between border-t border-dashed border-[#e6dccb] pt-3 text-sm"><span className="text-[#8a8371]">Duration</span><strong className="text-lg text-[#d97a34]">{formatNumber(timeBlockHours(block))}h</strong></div>
            <label className="mt-3 block"><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-[.07em] text-[#a99e8a]">Notes</span><textarea value={block.notes} onChange={(event) => onUpdateBlock(block.id, { notes: event.target.value })} rows={2} placeholder="What did you work on?" className="w-full resize-none rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-3 py-2 text-sm outline-none focus:border-[#d97a34]" /></label>
          </div>)}</div>
          <button type="button" onClick={onAddBlock} className="mt-4 w-full rounded-xl border border-dashed border-[#d9c5a6] px-4 py-3 text-xs font-bold text-[#9b611d] hover:border-[#d97a34] hover:bg-[#fff7ef]"><Plus size={14} className="mr-1 inline" /> Add another block</button>
        </div>
        <div className="border-t border-[#ece5d8] p-4"><Button className="w-full bg-[#1f2430] hover:bg-[#303747]" disabled={!!saving || !hasTimeBlocks} onClick={onSaveDraft}>{saving === 'draft' ? 'Saving…' : 'Save Entry'}</Button></div>
      </> : <div className="px-6 py-14 text-center"><Clock3 size={28} className="mx-auto text-[#d8cbb5]" /><div className="mt-3 text-sm font-bold">Pick a day cell</div><p className="mt-1 text-xs leading-5 text-[#8a8371]">Select an editable weekday cell to add or update its time blocks.</p></div>}
    </aside>
  );

}

export function TimesheetsPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const initialWeekStart = searchParams.get('week_start') || toDateInput(startOfLocalWeek());
  const [weekStart, setWeekStart] = useState(initialWeekStart);
  const [codes, setCodes] = useState<TimesheetCode[]>([]);
  const [projects, setProjects] = useState<TimesheetProject[]>([]);
  const [requiresTimesheet, setRequiresTimesheet] = useState(true);
  const [rows, setRows] = useState<TimesheetRow[]>([]);
  const [selectedProjectKeys, setSelectedProjectKeys] = useState<string[]>([]);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [taskDraft, setTaskDraft] = useState({
    projectKey: '',
    entryCode: 'PRJ',
    description: '',
    startDate: weekStart,
    endDate: toDateInput(addDays(new Date(`${weekStart}T00:00:00`), 6)),
  });
  const [taskModalError, setTaskModalError] = useState<string | null>(null);
  const [activeCell, setActiveCell] = useState<{ projectKey: string; date: string } | null>(null);
  const [currentWeek, setCurrentWeek] = useState<TimesheetWeek | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<'draft' | 'submit' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitCompliance, setSubmitCompliance] = useState<ComplianceReport | null>(null);
  const [submitComplianceOpen, setSubmitComplianceOpen] = useState(true);
  const [complianceCheckMessage, setComplianceCheckMessage] = useState<string | null>(null);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const weekDates = useMemo(() => {
    const start = new Date(`${weekStart}T00:00:00`);
    return Array.from({ length: 7 }, (_, index) => addDays(start, index));
  }, [weekStart]);

  const actualProjects = projects.filter((project) => project.id && !project.disabled);
  const selectedWeekSubmitted = currentWeek?.status === 'submitted';
  const selectedWeekApproved = currentWeek?.status === 'approved';
  const selectedWeekRejected = currentWeek?.status === 'rejected';
  const selectedWeekLocked = selectedWeekSubmitted || selectedWeekApproved;
  const availableProjectOptions = useMemo(() => {
    const preferred = [
      ...actualProjects,
      ...projects.filter((project) => !project.disabled && ['POC', 'TRN', 'MTG', 'ADM'].includes(project.code)),
    ];
    const unique = new Map<string, TimesheetProject>();
    preferred.forEach((project) => unique.set(project.id || project.code, project));
    return Array.from(unique.values());
  }, [actualProjects, projects]);
  const internalActivityOptions = useMemo(
    () => availableProjectOptions.filter((project) => !project.id),
    [availableProjectOptions]
  );
  const leaveActivityOptions = useMemo(
    () => projects.filter((project) => project.group === 'LEAVE ACTIVITIES'),
    [projects]
  );
  const selectedTaskProject = useMemo(
    () => availableProjectOptions.find((item) => (item.id || item.code) === taskDraft.projectKey) || null,
    [availableProjectOptions, taskDraft.projectKey]
  );
  const taskActivityCodeOptions = useMemo(() => {
    if (!selectedTaskProject) return [];
    const expectedCode = selectedTaskProject.id ? 'PRJ' : selectedTaskProject.code;
    const matchingCodes = codes.filter((code) => code.code === expectedCode);
    if (matchingCodes.length) return matchingCodes;
    return [{
      code: expectedCode,
      label: selectedTaskProject.id ? 'Project work' : selectedTaskProject.name,
      requires_project: Boolean(selectedTaskProject.id),
    }];
  }, [codes, selectedTaskProject]);
  const formatWorkItemOption = (project: TimesheetProject) => {
    if (project.disabled) return project.name;
    if (project.id && typeof project.allocation_percentage === 'number') {
      return `${project.name} (${project.allocation_percentage}%)`;
    }
    if (project.id) return project.name;
    return `${project.name} (${project.code})`;
  };
  const gridProjects = useMemo(
    () => {
      const counts = new Map<string, number>();
      return selectedProjectKeys
        .map((key) => {
          const baseKey = baseTimesheetProjectKey(key);
          const project = availableProjectOptions.find((item) => (item.id || item.code) === baseKey);
          if (!project) return null;
          const count = counts.get(baseKey) || 0;
          counts.set(baseKey, count + 1);
          return {
            ...project,
            gridKey: key,
            baseKey,
            duplicateLabel: count > 0 ? `Copy ${count + 1}` : undefined,
          };
        })
        .filter(Boolean) as GridTimesheetProject[];
    },
    [availableProjectOptions, selectedProjectKeys]
  );

  const loadTimesheet = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const [optionsRes, weekRes] = await Promise.all([
        fetch(`${API_BASE}/timesheets/me/options?week_start=${weekStart}`, { headers }),
        fetch(`${API_BASE}/timesheets/me/week?week_start=${weekStart}`, { headers }),
      ]);
      if (!optionsRes.ok) throw new Error('Could not load timesheet options.');
      if (!weekRes.ok) throw new Error('Could not load this week\'s timesheet.');

      const options = await optionsRes.json();
      const week: TimesheetWeek = await weekRes.json();
      setCodes(options.entry_codes || []);
      setProjects(options.projects || []);
      setRequiresTimesheet(options.requires_timesheet !== false);
      setCurrentWeek(week);

      const loadedRows = rowsFromTimesheet(week, options.projects || []);
      if (loadedRows.length) {
        setRows(loadedRows);
        setSelectedProjectKeys(Array.from(new Set(loadedRows.map((row) => row.projectKey))));
        setActiveCell(null);
      } else {
        setRows([]);
        setSelectedProjectKeys([]);
        setActiveCell(null);
      }
      const selectableOptions = (options.projects || []).filter((project: TimesheetProject) => !project.disabled);
      const firstOption = selectableOptions.find((project: TimesheetProject) => project.id) || selectableOptions[0];
      setTaskDraft((current) => ({
        ...current,
        projectKey: firstOption ? (firstOption.id || firstOption.code) : '',
        entryCode: firstOption?.id ? 'PRJ' : firstOption?.code || 'TRN',
        startDate: weekStart,
        endDate: toDateInput(addDays(new Date(`${weekStart}T00:00:00`), 6)),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load timesheet.');
    } finally {
      setLoading(false);
    }
  }, [headers, user, weekStart]);

  useEffect(() => {
    loadTimesheet();
  }, [loadTimesheet]);

  useEffect(() => {
    const requestedWeek = searchParams.get('week_start');
    if (requestedWeek && requestedWeek !== weekStart) {
      setWeekStart(requestedWeek);
    }
  }, [searchParams, weekStart]);

  const selectedProject = activeCell
    ? gridProjects.find((project) => project.gridKey === activeCell.projectKey) || null
    : null;
  const activeBlocks = activeCell
    ? rows.filter((row) => row.projectKey === activeCell.projectKey && row.workDate === activeCell.date)
    : [];
  const leaveByDate = useMemo(() => {
    const map = new Map<string, TimesheetLeaveDay>();
    (currentWeek?.leave_days || []).forEach((item) => map.set(item.date, item));
    return map;
  }, [currentWeek?.leave_days]);
  const closeTimeBlockEditor = () => {
    setActiveCell(null);
  };

  const openCell = (project: GridTimesheetProject, date: string) => {
    if (isWeekendDate(date)) return;
    if (leaveByDate.has(date)) return;
    const code = project.id ? 'PRJ' : project.code;
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    setRows((current) => current.some((row) => row.projectKey === project.gridKey && row.workDate === date)
      ? current
      : [...current, makeTimesheetRow(project, code, date, project.gridKey)]);
    setActiveCell({ projectKey: project.gridKey, date });
  };

  const addBlock = (project: GridTimesheetProject | null = selectedProject, date = activeCell?.date || weekStart) => {
    if (!project) return;
    if (isWeekendDate(date)) {
      setError('Timesheet entries cannot be added on Saturday or Sunday.');
      return;
    }
    if (leaveByDate.has(date)) {
      setError('Timesheet entries cannot be added on pending or approved leave dates.');
      return;
    }
    const code = project.id ? 'PRJ' : project.code;
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    setRows((current) => [...current, makeTimesheetRow(project, code, date, project.gridKey)]);
    setActiveCell({ projectKey: project.gridKey, date });
  };

  const addProjectRow = () => {
    const project = availableProjectOptions.find((item) => (item.id || item.code) === taskDraft.projectKey);
    if (!project) return;
    const key = project.id || project.code;
    setTaskModalError(null);
    const firstOpenDate = weekDates
      .map(toDateInput)
      .find((dateKey) => dateKey >= taskDraft.startDate && dateKey <= taskDraft.endDate && !leaveByDate.has(dateKey) && !isWeekendDate(dateKey));
    if (!firstOpenDate) {
      setTaskModalError('Select a date range with at least one working day that is not already covered by leave.');
      return;
    }
    setSelectedProjectKeys((current) => current.includes(key) ? current : [...current, key]);
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    setError(null);
    setRows((current) => current.some((row) => row.projectKey === key && row.workDate === firstOpenDate)
      ? current
      : [...current, makeTimesheetRow(project, project.id ? 'PRJ' : project.code, firstOpenDate, key)]);
    setActiveCell({ projectKey: key, date: firstOpenDate });
    setTaskModalOpen(false);
  };

  const openTaskModal = () => {
    setTaskModalError(null);
    setTaskModalOpen(true);
  };

  const closeTaskModal = () => {
    setTaskModalError(null);
    setTaskModalOpen(false);
  };

  const removeProjectRow = (project: GridTimesheetProject) => {
    const key = project.gridKey;
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    setSelectedProjectKeys((current) => current.filter((item) => item !== key));
    setRows((current) => current.filter((row) => row.projectKey !== key));
    setActiveCell((current) => current?.projectKey === key ? null : current);
  };

  const duplicateProjectRow = (project: GridTimesheetProject) => {
    const duplicateKey = makeDuplicateTimesheetKey(project.baseKey, selectedProjectKeys);
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    setSelectedProjectKeys((current) => [...current, duplicateKey]);
    const firstOpenDate = weekDates.map(toDateInput).find((dateKey) => !leaveByDate.has(dateKey) && !isWeekendDate(dateKey));
    setRows((current) => {
      const copiedRows = current
        .filter((row) => row.projectKey === project.gridKey)
        .map((row) => ({
          ...row,
          id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          projectKey: duplicateKey,
        }));
      return [
        ...current,
        ...(copiedRows.length || !firstOpenDate
          ? copiedRows
          : [makeTimesheetRow(project, project.id ? 'PRJ' : project.code, firstOpenDate, duplicateKey)]),
      ];
    });
    if (firstOpenDate) {
      setActiveCell({ projectKey: duplicateKey, date: firstOpenDate });
    }
  };

  const updateBlock = (rowId: string, updates: Partial<TimesheetRow>) => {
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    setRows((current) => current.map((row) => row.id === rowId ? { ...row, ...updates } : row));
  };

  const updateBlockStart = (block: TimesheetRow, startTime: string) => {
    const currentHours = timeBlockHours(block) || 8;
    updateBlock(block.id, {
      startTime,
      endTime: endTimeFromHours(startTime, currentHours),
    });
  };

  const removeBlock = (rowId: string) => {
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    setRows((current) => current.filter((item) => item.id !== rowId));
  };

  const cellTotal = (project: GridTimesheetProject, date: string) => rows
    .filter((row) => !leaveByDate.has(row.workDate))
    .filter((row) => row.projectKey === project.gridKey && row.workDate === date)
    .reduce((sum, row) => sum + timeBlockHours(row), 0);

  const dayTotal = (date: string) => rows
    .filter((row) => !leaveByDate.has(row.workDate))
    .filter((row) => row.workDate === date)
    .reduce((sum, row) => sum + timeBlockHours(row), 0);

  const projectTotal = (project: GridTimesheetProject) => rows
    .filter((row) => !leaveByDate.has(row.workDate))
    .filter((row) => row.projectKey === project.gridKey)
    .reduce((sum, row) => sum + timeBlockHours(row), 0);

  const buildPayload = () => ({
    week_start: weekStart,
    time_zone: timeZone,
    entries: rows.flatMap((row) => {
      if (isWeekendDate(row.workDate)) return [];
      if (leaveByDate.has(row.workDate)) return [];
      const baseKey = baseTimesheetProjectKey(row.projectKey);
      const project = projects.find((item) => item.id === baseKey || item.code === baseKey);
      const hours = timeBlockHours(row);
      return hours > 0 ? [{
        work_date: row.workDate,
        entry_code: row.entryCode,
        project_id: project?.id || null,
        project_name: row.projectName,
        start_time: row.startTime,
        end_time: row.endTime,
        notes: row.notes || null,
      }] : [];
    }),
  });

  const applyWeekResponse = (week: TimesheetWeek) => {
    setCurrentWeek(week);
    const nextRows = rowsFromTimesheet(week, projects);
    setRows(nextRows);
    setSelectedProjectKeys(Array.from(new Set(nextRows.map((row) => row.projectKey))));
    setActiveCell(null);
  };

  const postDraftTimesheet = async () => {
    const res = await fetch(`${API_BASE}/timesheets/me/week`, {
      method: 'POST',
      headers,
      body: JSON.stringify(buildPayload()),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.detail || 'Could not save timesheet.');
    return data as TimesheetWeek;
  };

  const submitTimesheetToBackend = async () => {
    const res = await fetch(`${API_BASE}/timesheets/me/week/submit`, {
      method: 'POST',
      headers,
      body: JSON.stringify(buildPayload()),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.detail || 'Could not submit timesheet.');
    applyWeekResponse(data as TimesheetWeek);
    setSubmitCompliance(null);
    setSuccess('Timesheet submitted for approval.');
  };

  const saveTimesheet = async (mode: 'draft' | 'submit') => {
    setSaving(mode);
    setError(null);
    setSuccess(null);
    setComplianceCheckMessage(null);
    if (mode === 'draft') {
      setSubmitCompliance(null);
    }
    try {
      if (mode === 'draft') {
        const draft = await postDraftTimesheet();
        applyWeekResponse(draft);
        setSuccess('Timesheet draft saved.');
        return;
      }

      const draft = await postDraftTimesheet();
      applyWeekResponse(draft);
      const timesheetId = draft.entries[0]?.id;
      if (!timesheetId) {
        throw new Error('Add at least one timesheet entry before submitting.');
      }
      try {
        const complianceRes = await fetch(`${API_BASE}/timesheets/${timesheetId}/allocation-compliance`, { headers });
        const complianceData = await complianceRes.json().catch(() => null);
        if (!complianceRes.ok) throw new Error(complianceData?.detail || 'Allocation compliance could not be checked.');
        const report = complianceData as ComplianceReport;
        if (report.overall_status === 'warning' || report.overall_status === 'violation') {
          setSubmitCompliance(report);
          setSubmitComplianceOpen(true);
          setSuccess(null);
          return;
        }
      } catch {
        setComplianceCheckMessage('Allocation compliance could not be checked. You may still submit, but the issue will be logged.');
      }
      await submitTimesheetToBackend();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save timesheet.');
    } finally {
      setSaving(null);
    }
  };

  const submitAfterComplianceWarning = async () => {
    setSaving('submit');
    setError(null);
    setSuccess(null);
    setComplianceCheckMessage(null);
    try {
      await submitTimesheetToBackend();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit timesheet.');
    } finally {
      setSaving(null);
    }
  };

  const recallTimesheet = async () => {
    setSaving('draft');
    setError(null);
    setSuccess(null);
    try {
      const params = new URLSearchParams({ week_start: weekStart, time_zone: timeZone });
      const res = await fetch(`${API_BASE}/timesheets/me/week/recall?${params.toString()}`, {
        method: 'POST',
        headers,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not recall timesheet.');
      setCurrentWeek(data);
      setRows(rowsFromTimesheet(data, projects));
      setSelectedProjectKeys(Array.from(new Set(rowsFromTimesheet(data, projects).map((row) => row.projectKey))));
      setSuccess('Timesheet recalled. You can edit and submit it again.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not recall timesheet.');
    } finally {
      setSaving(null);
    }
  };

  const copyPreviousWeek = async () => {
    setSaving('draft');
    setError(null);
    setSuccess(null);
    try {
      const body = JSON.stringify({
        source_week_start: toDateInput(addDays(new Date(`${weekStart}T00:00:00`), -7)),
        target_week_start: weekStart,
        time_zone: timeZone,
      });
      const res = await fetch(`${API_BASE}/timesheets/me/week/copy`, {
        method: 'POST',
        headers,
        body,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not copy previous week.');
      setCurrentWeek(data);
      const copiedRows = rowsFromTimesheet(data, projects);
      setRows(copiedRows);
      setSelectedProjectKeys(Array.from(new Set(copiedRows.map((row) => row.projectKey))));
      setSuccess('Previous week copied into this draft.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not copy previous week.');
    } finally {
      setSaving(null);
    }
  };

  const deleteTimesheet = async () => {
    const confirmed = window.confirm('Delete this week timesheet entries? This is useful for testing but cannot be undone.');
    if (!confirmed) return;
    setSaving('draft');
    setError(null);
    setSuccess(null);
    try {
      const params = new URLSearchParams({ week_start: weekStart, time_zone: timeZone });
      const res = await fetch(`${API_BASE}/timesheets/me/week?${params.toString()}`, {
        method: 'DELETE',
        headers,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not delete timesheet.');
      setCurrentWeek(data);
      setRows([]);
      setSelectedProjectKeys([]);
      setActiveCell(null);
      setSuccess('Timesheet entries deleted for this week.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete timesheet.');
    } finally {
      setSaving(null);
    }
  };

  const hasTimeBlocks = rows.some((row) => timeBlockHours(row) > 0);

  const jumpToWeek = (dateValue: string) => {
    setWeekStart(toDateInput(startOfLocalWeek(new Date(`${dateValue}T00:00:00`))));
  };

  const loggedHours = rows.filter((row) => !leaveByDate.has(row.workDate)).reduce((sum, row) => sum + timeBlockHours(row), 0);
  const targetHours = currentWeek?.weekly_limit_hours || 40;
  const regularHours = Math.min(targetHours, loggedHours);
  const overtimeHours = Math.max(0, loggedHours - targetHours);
  const remainingHours = Math.max(0, targetHours - loggedHours);
  const projectColors = ['#d97a34', '#4b5673', '#5b8c5a', '#e0a23a', '#8a6a3a', '#778199'];
  const projectBreakdown = gridProjects.map((project, index) => ({
    project,
    hours: projectTotal(project),
    color: projectColors[index % projectColors.length],
  }));
  const maxProjectHours = Math.max(1, ...projectBreakdown.map((item) => item.hours));
  const dailyDistribution = weekDates.map((dateValue) => {
    const dateKey = toDateInput(dateValue);
    const segments = projectBreakdown.map((item) => ({ ...item, hours: cellTotal(item.project, dateKey) })).filter((item) => item.hours > 0);
    return { dateValue, dateKey, total: segments.reduce((sum, segment) => sum + segment.hours, 0), segments };
  });
  const maxDailyHours = Math.max(8, ...dailyDistribution.map((day) => day.total));
  const statusText = !currentWeek?.status || currentWeek.status === 'not_started' ? 'draft' : currentWeek.status;
  const statusTone = statusText === 'approved' ? 'bg-[#e5f3e5] text-[#3f7d3f]' : statusText === 'submitted' ? 'bg-[#fff1d8] text-[#a86a11]' : statusText === 'rejected' ? 'bg-[#fcecec] text-[#d64545]' : 'bg-[#fbeee1] text-[#b8611f]';

  return (
    <div className="-mx-[var(--layout-main-padding-x)] -my-[var(--layout-main-padding-y)] min-h-screen bg-[#f7f3ec] px-[var(--layout-main-padding-x)] py-[var(--layout-main-padding-y)] text-[#1f2430] animate-fade-up">
      <header className="mb-5 flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
        <div><h1 className="text-2xl font-bold tracking-tight">Timesheet</h1><p className="mt-1 text-sm text-[#8a8371]">Log weekly project hours and submit for approval.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex h-10 items-center overflow-hidden rounded-[10px] border border-[#e4daca] bg-white">
            <button type="button" disabled={!!saving} onClick={() => setWeekStart(toDateInput(addDays(new Date(`${weekStart}T00:00:00`), -7)))} className="h-full px-3 text-[#8a8371] hover:bg-[#fbf5ea] disabled:opacity-50" aria-label="Previous week">‹</button>
            <label className="flex h-full items-center border-x border-[#eee5d7] px-3"><input type="date" value={weekStart} onChange={(event) => jumpToWeek(event.target.value)} className="w-0 opacity-0" aria-label="Select week" /><span className="whitespace-nowrap text-sm font-bold">{weekLabel(weekStart)}</span></label>
            <button type="button" disabled={!!saving} onClick={() => setWeekStart(toDateInput(addDays(new Date(`${weekStart}T00:00:00`), 7)))} className="h-full px-3 text-[#8a8371] hover:bg-[#fbf5ea] disabled:opacity-50" aria-label="Next week">›</button>
          </div>
          <Button variant="soft" disabled={!!saving} onClick={() => setWeekStart(toDateInput(startOfLocalWeek()))}>This Week</Button>
          <Button variant="ghost" icon={<RefreshCw size={15} />} disabled={!!saving || selectedWeekLocked} onClick={copyPreviousWeek}>Copy Previous</Button>
        </div>
      </header>

      {error && <div className="mb-4 rounded-xl border border-[#d64545]/20 bg-[#fcecec] px-4 py-3 text-sm text-[#d64545]">{error}</div>}
      {success && <div className="mb-4 rounded-xl border border-[#5b8c5a]/20 bg-[#e5f3e5] px-4 py-3 text-sm text-[#3f7d3f]">{success}</div>}
      {complianceCheckMessage && <div className="mb-4 rounded-xl border border-[#e0a23a]/25 bg-[#fff1d8] px-4 py-3 text-sm text-[#a86a11]">{complianceCheckMessage}</div>}
      {submitCompliance && <div className="mb-4"><AllocationCompliancePanel report={submitCompliance} open={submitComplianceOpen} onToggle={() => setSubmitComplianceOpen((current) => !current)} action={<><Button variant="ghost" disabled={!!saving} onClick={() => { setSubmitCompliance(null); setSuccess('Review your time blocks, then submit again when ready.'); }}>Go Back and Review</Button><Button disabled={!!saving} onClick={submitAfterComplianceWarning} icon={<CheckCircle2 size={15} />}>{saving === 'submit' ? 'Submitting' : 'Submit Anyway'}</Button></>} /></div>}
      {!!currentWeek?.warnings?.length && !selectedWeekApproved && <div className="mb-4 rounded-xl border border-[#e0a23a]/25 bg-[#fff1d8] px-4 py-3 text-sm text-[#a86a11]">{currentWeek.warnings.map((warning) => <div key={warning}>{warning}</div>)}</div>}
      {!requiresTimesheet && <div className="mb-4 rounded-xl border border-[#e0a23a]/25 bg-[#fff1d8] px-4 py-3 text-sm text-[#a86a11]">Timesheet submission may not be required for your workforce type. You can still save hours if your manager asks for it.</div>}
      {selectedWeekSubmitted && <div className="mb-4 rounded-xl border border-[#ece5d8] bg-white px-4 py-3 text-sm text-[#8a8371]">This timesheet is awaiting approval from {currentWeek?.submitted_to || 'your manager'}. Recall it if changes are required.</div>}
      {selectedWeekApproved && <div className="mb-4 rounded-xl border border-[#5b8c5a]/20 bg-[#e5f3e5] px-4 py-3 text-sm text-[#3f7d3f]">Approved{currentWeek?.reviewed_by ? ` by ${currentWeek.reviewed_by}` : ''}{currentWeek?.reviewed_at ? ` on ${formatDateTime(currentWeek.reviewed_at)}` : ''}. This week is locked.</div>}
      {selectedWeekRejected && <div className="mb-4 rounded-xl border border-[#d64545]/20 bg-[#fcecec] px-4 py-3 text-sm text-[#d64545]">Rejected{currentWeek?.reviewed_by ? ` by ${currentWeek.reviewed_by}` : ''}. {currentWeek?.reviewer_notes || 'Update the entries and submit again.'}</div>}

      {taskModalOpen && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/35 p-4 backdrop-blur-sm">
        <div className="w-full max-w-xl overflow-hidden rounded-2xl border border-[#ece5d8] bg-white shadow-[0_24px_70px_rgba(31,36,48,.22)]">
          <div className="flex items-start justify-between border-b border-[#ece5d8] px-6 py-5"><div><h2 className="text-lg font-bold">Add Task</h2><p className="mt-1 text-xs text-[#8a8371]">Add a work item to {weekLabel(weekStart)}.</p></div><button type="button" onClick={closeTaskModal} className="rounded-lg p-2 text-[#8a8371] hover:bg-[#fbf5ea]" aria-label="Close add task"><X size={17} /></button></div>
          <div className="space-y-5 px-6 py-5">
            {taskModalError && <div className="rounded-lg border border-[#d64545]/20 bg-[#fcecec] px-3 py-2 text-sm text-[#d64545]">{taskModalError}</div>}
            <label className="block"><span className="mb-2 block text-xs font-bold">Work Item</span><select value={taskDraft.projectKey} onChange={(event) => { setTaskModalError(null); const selected = availableProjectOptions.find((item) => (item.id || item.code) === event.target.value); setTaskDraft((current) => ({ ...current, projectKey: event.target.value, entryCode: selected?.id ? 'PRJ' : selected?.code || current.entryCode })); }} className="h-11 w-full rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-3 text-sm font-semibold outline-none focus:border-[#d97a34]"><optgroup label="PROJECTS">{actualProjects.length ? actualProjects.map((project) => <option key={project.id || project.code} value={project.id || project.code}>{formatWorkItemOption(project)}</option>) : <option disabled value="__no_projects">No active project assignments</option>}</optgroup><optgroup label="INTERNAL ACTIVITIES">{internalActivityOptions.map((project) => <option key={project.code} value={project.code}>{formatWorkItemOption(project)}</option>)}</optgroup><optgroup label="LEAVE ACTIVITIES">{leaveActivityOptions.map((project) => <option key={project.code} value={project.code} disabled={project.disabled}>{formatWorkItemOption(project)}</option>)}</optgroup></select></label>
            <div><div className="mb-2 text-xs font-bold">Activity</div><div className="flex flex-wrap gap-2">{taskActivityCodeOptions.map((code) => <button key={code.code} type="button" onClick={() => setTaskDraft((current) => ({ ...current, entryCode: code.code }))} className={cn('rounded-full border px-3 py-2 text-xs font-bold transition', taskDraft.entryCode === code.code ? 'border-[#d97a34] bg-[#fbeee1] text-[#b8611f]' : 'border-[#e4daca] bg-[#faf8f3] text-[#8a8371] hover:border-[#d97a34]/50')}>{code.label}</button>)}</div><p className="mt-2 text-[11px] text-[#a99e8a]">Code {taskDraft.entryCode} is derived from the selected work item.</p></div>
            <label className="block"><span className="mb-2 block text-xs font-bold">Description <span className="font-normal text-[#a99e8a]">(optional)</span></span><textarea value={taskDraft.description} onChange={(event) => setTaskDraft((current) => ({ ...current, description: event.target.value }))} rows={3} placeholder="What will you work on?" className="w-full resize-none rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-3 py-3 text-sm outline-none focus:border-[#d97a34]" /></label>
          </div>
          <div className="flex justify-end gap-2 border-t border-[#ece5d8] px-6 py-4"><Button variant="ghost" onClick={closeTaskModal}>Cancel</Button><Button disabled={!taskDraft.projectKey} icon={<Plus size={15} />} onClick={addProjectRow}>Add Task</Button></div>
        </div>
      </div>}

      <section className="mb-5 flex flex-col gap-4 rounded-2xl border border-[#eadbc5] bg-[#fbf5ea] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3"><span className="text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">Status</span><span className={cn('rounded-full px-3 py-1 text-xs font-bold capitalize', statusTone)}>● {statusText.replace('_', ' ')}</span></div>
        <div className="flex flex-wrap gap-6 text-sm"><span className="text-[#8a8371]">Logged <strong className="ml-1 text-lg text-[#1f2430]">{formatNumber(loggedHours)}h</strong></span><span className="text-[#8a8371]">Target <strong className="ml-1 text-lg text-[#1f2430]">{formatNumber(targetHours)}h</strong></span><span className="text-[#8a8371]">Approver <strong className="ml-1 text-[#1f2430]">{currentWeek?.submitted_to || 'Not assigned'}</strong></span></div>
      </section>

      <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[{ label: 'Logged', value: `${formatNumber(loggedHours)}h`, detail: 'this week', color: '#d97a34' }, { label: 'Regular', value: `${formatNumber(regularHours)}h`, detail: 'within target', color: '#5b8c5a' }, { label: 'Overtime', value: `${formatNumber(overtimeHours)}h`, detail: overtimeHours ? 'above target' : '—', color: overtimeHours ? '#e0a23a' : '#c9bea9' }, { label: 'Remaining', value: `${formatNumber(remainingHours)}h`, detail: `to ${formatNumber(targetHours)}h target`, color: '#e0a23a' }].map((item) => <div key={item.label} className="rounded-2xl border border-[#ece5d8] bg-white p-5 shadow-[0_3px_10px_rgba(60,40,10,.025)]" style={{ borderTop: `3px solid ${item.color}` }}><div className="text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">{item.label}</div><div className="mt-2 flex items-baseline gap-2"><strong className="text-[27px] tracking-[-.04em]">{item.value}</strong><span className="text-xs text-[#8a8371]">{item.detail}</span></div></div>)}
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px] xl:items-start">
        <div className="space-y-5">
          <section className="overflow-hidden rounded-2xl border border-[#ece5d8] bg-white shadow-[0_3px_10px_rgba(60,40,10,.025)]">
            <div className="flex items-center justify-between border-b border-[#ece5d8] px-5 py-4"><h2 className="text-[17px] font-bold">Work Items</h2>{!selectedWeekLocked && <Button size="sm" icon={<Plus size={14} />} disabled={!availableProjectOptions.length} onClick={openTaskModal}>Add Task</Button>}</div>
            <div className="overflow-x-auto p-4"><div className="min-w-[1000px]">
              <div className="grid grid-cols-[150px_repeat(7,minmax(0,1fr))_56px] gap-1 rounded-xl bg-[#faf8f3] px-2 py-3 text-[10px] font-bold uppercase tracking-[.06em] text-[#b09f82]"><div className="px-2">Work Item</div>{weekDates.map((dateValue) => <div key={dateValue.toISOString()} className={cn('text-center', isWeekendDate(dateValue) && 'opacity-55')}>{dateValue.toLocaleDateString('en-US', { weekday: 'short' })}<div className="mt-0.5 normal-case">{dateValue.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</div></div>)}<div className="text-center">Total</div></div>
              {loading ? <div className="py-10 text-center text-sm text-[#8a8371]">Loading timesheet…</div> : !gridProjects.length ? <div className="py-12 text-center"><div className="text-sm font-bold">Start by adding a work item</div><p className="mt-1 text-sm text-[#8a8371]">Choose an assigned project or internal activity, then select a day.</p><Button className="mt-4" icon={<Plus size={15} />} disabled={selectedWeekLocked || !availableProjectOptions.length} onClick={openTaskModal}>Add Task</Button></div> : gridProjects.map((project, projectIndex) => <div key={project.gridKey} className="grid grid-cols-[150px_repeat(7,minmax(0,1fr))_56px] items-center gap-1 border-b border-[#eee7dc] px-2 py-3 last:border-0">
                <div className="flex min-w-0 items-center gap-2 px-2"><span className="h-10 w-1.5 shrink-0 rounded-full" style={{ background: projectColors[projectIndex % projectColors.length] }} /><div className="min-w-0 flex-1"><div className="truncate text-sm font-bold">{project.name}</div><div className="truncate text-[10px] text-[#a99e8a]">{project.code} · {project.id ? 'Project work' : codes.find((code) => code.code === project.code)?.label || project.code}</div></div><div className="flex flex-col"><button type="button" disabled={selectedWeekLocked} onClick={() => duplicateProjectRow(project)} className="text-[#a99e8a] hover:text-[#d97a34] disabled:opacity-30" aria-label={`Duplicate ${project.name}`}><Copy size={12} /></button><button type="button" disabled={selectedWeekLocked} onClick={() => removeProjectRow(project)} className="mt-1 text-[#a99e8a] hover:text-[#d64545] disabled:opacity-30" aria-label={`Remove ${project.name}`}><X size={12} /></button></div></div>
                {weekDates.map((dateValue) => { const dateKey = toDateInput(dateValue); const total = cellTotal(project, dateKey); const leave = leaveByDate.get(dateKey); const weekend = isWeekendDate(dateValue); const blocks = rows.filter((row) => row.projectKey === project.gridKey && row.workDate === dateKey); const selected = activeCell?.projectKey === project.gridKey && activeCell.date === dateKey; return <div key={dateKey} className={cn('px-0.5', weekend && 'opacity-55')}><button type="button" disabled={selectedWeekLocked || !!leave || weekend} onClick={() => openCell(project, dateKey)} className={cn('flex h-14 w-full flex-col items-center justify-center rounded-[10px] border text-sm font-bold transition', weekend ? 'cursor-not-allowed border-[#ece5d8] bg-[#f3efe8] text-[#c7b99f]' : leave ? 'cursor-not-allowed border-[#d8dbe5] bg-[#edeef5] px-1 text-[10px] text-[#4b5673]' : selected ? 'border-2 border-[#d97a34] bg-[#fff7ef] text-[#b8611f] shadow-[0_3px_10px_rgba(217,122,52,.12)]' : total > 0 ? 'border-[#e7dccb] bg-white text-[#1f2430] hover:border-[#d97a34]/50' : 'border-[#ece5d8] bg-[#faf8f3] text-[#c2b59f] hover:border-[#d97a34]/40')}>{leave ? `${leave.hours}h leave` : `${formatNumber(total)}h`}{selected && total > 0 && <span className="mt-0.5 text-[9px] font-semibold text-[#d97a34]">{blocks.length} block{blocks.length === 1 ? '' : 's'}</span>}</button></div>; })}
                <div className="text-center text-sm font-bold text-[#d97a34]">{formatNumber(projectTotal(project))}h</div>
              </div>)}
              {!loading && <div className="grid grid-cols-[150px_repeat(7,minmax(0,1fr))_56px] items-center gap-1 px-2 py-4"><div className="px-2 text-[10px] font-bold uppercase tracking-[.06em] text-[#a99e8a]">Daily Total</div>{weekDates.map((dateValue) => { const dateKey = toDateInput(dateValue); return <div key={dateKey} className={cn('text-center text-sm font-bold', isWeekendDate(dateValue) ? 'text-[#c7b99f]' : 'text-[#1f2430]')}>{formatNumber(dayTotal(dateKey))}h</div>; })}<div className="text-center text-sm font-bold text-[#d97a34]">{formatNumber(loggedHours)}h</div></div>}
            </div></div>
          </section>

          <section className="rounded-2xl border border-[#ece5d8] bg-white p-5 shadow-[0_3px_10px_rgba(60,40,10,.025)] sm:p-6"><h2 className="mb-5 text-[17px] font-bold">Week Breakdown</h2><div className="grid gap-8 lg:grid-cols-2">
            <div><div className="mb-4 text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">By Project</div><div className="space-y-4">{projectBreakdown.length ? projectBreakdown.map((item) => <div key={item.project.gridKey}><div className="mb-2 flex items-center justify-between gap-3 text-sm"><span className="flex min-w-0 items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: item.color }} /><span className="truncate">{item.project.name}</span></span><strong>{formatNumber(item.hours)}h</strong></div><div className="h-2 overflow-hidden rounded-full bg-[#eee8dd]"><div className="h-full rounded-full" style={{ width: `${(item.hours / maxProjectHours) * 100}%`, background: item.color }} /></div></div>) : <div className="text-sm text-[#8a8371]">Add work items to see the breakdown.</div>}</div></div>
            <div><div className="mb-4 text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">Daily Distribution</div><div className="flex h-32 items-end gap-2 border-b border-[#e6dccb]">{dailyDistribution.map((day) => <div key={day.dateKey} className="flex h-full min-w-0 flex-1 flex-col justify-end"><div className="flex w-full flex-col-reverse overflow-hidden rounded-t-lg" style={{ height: `${Math.max(4, (day.total / maxDailyHours) * 100)}%` }}>{day.segments.map((segment) => <div key={segment.project.gridKey} style={{ height: `${day.total ? (segment.hours / day.total) * 100 : 0}%`, background: segment.color }} title={`${segment.project.name}: ${segment.hours}h`} />)}</div><div className="mt-1.5 text-center text-[10px] text-[#a99e8a]">{day.dateValue.toLocaleDateString('en-US', { weekday: 'narrow' })}</div></div>)}</div><div className="mt-4 flex flex-wrap gap-x-4 gap-y-2">{projectBreakdown.map((item) => <span key={item.project.gridKey} className="flex items-center gap-1.5 text-[10px] text-[#8a8371]"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: item.color }} />{item.project.name}</span>)}</div></div>
          </div></section>
        </div>

        <TimeEntryDetailsPanel activeCell={activeCell} project={selectedProject} blocks={activeBlocks} totalHours={activeBlocks.reduce((sum, block) => sum + timeBlockHours(block), 0)} saving={saving} hasTimeBlocks={hasTimeBlocks} onClose={closeTimeBlockEditor} onAddBlock={() => addBlock(selectedProject, activeCell?.date || weekStart)} onUpdateBlock={updateBlock} onUpdateBlockStart={updateBlockStart} onRemoveBlock={removeBlock} onSaveDraft={() => saveTimesheet('draft')} />
      </div>

      <footer className="mt-5 flex flex-col gap-4 rounded-2xl border border-[#ece5d8] bg-white px-5 py-4 shadow-[0_3px_10px_rgba(60,40,10,.025)] sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-[#8a8371]">You&apos;ve logged <strong className="text-[#1f2430]">{formatNumber(loggedHours)} of {formatNumber(targetHours)}h</strong> this week. <span className={remainingHours ? 'text-[#b8611f]' : 'text-[#5b8c5a]'}>{remainingHours ? `${formatNumber(remainingHours)}h remaining before target.` : 'Weekly target reached.'}</span></div>
        <div className="flex gap-2">{selectedWeekSubmitted ? <Button variant="ghost" disabled={!!saving} onClick={recallTimesheet} icon={<RefreshCw size={15} />}>{saving === 'draft' ? 'Recalling…' : 'Recall Submission'}</Button> : selectedWeekApproved ? <span className="rounded-full bg-[#e5f3e5] px-4 py-2 text-xs font-bold text-[#3f7d3f]">Approved</span> : <><Button variant="ghost" disabled={!!saving || !hasTimeBlocks} onClick={() => saveTimesheet('draft')}>Save Draft</Button><Button disabled={!!saving || !hasTimeBlocks} onClick={() => saveTimesheet('submit')} icon={<CheckCircle2 size={15} />}>{saving === 'submit' ? 'Submitting…' : 'Submit for Approval'}</Button></>}</div>
      </footer>
    </div>
  );

}

export function CheckInOutPage() {
  const { today, history, joiningDate, loading, historyLoading, actionLoading, error, checkIn, checkOut, loadHistory } = useAttendance();
  const [clockNow, setClockNow] = useState(new Date());
  const todayInput = toDateInput(new Date());
  const defaultFrom = toDateInput(addDays(new Date(`${todayInput}T00:00:00`), -29));
  const [dateFrom, setDateFrom] = useState(defaultFrom);
  const [dateTo, setDateTo] = useState(todayInput);
  const [filterError, setFilterError] = useState<string | null>(null);
  const isCheckedIn = !!today?.is_checked_in;
  const isCheckedOut = !!today?.check_out;
  const canCheckInToday = !loading && !isCheckedIn && !isCheckedOut;
  const checkInDate = parseApiDateTime(today?.check_in);
  const liveWorkedHours = isCheckedIn && checkInDate
    ? Math.max(0, (clockNow.getTime() - checkInDate.getTime()) / 3_600_000)
    : Number(today?.total_hours || 0);
  const sessionHours = isCheckedIn ? formatElapsed(today?.check_in, clockNow) : formatHours(today?.total_hours ?? null);
  const ringPercent = Math.min(100, Math.max(0, (liveWorkedHours / 8) * 100));
  const expectedOut = checkInDate ? new Date(checkInDate.getTime() + 8 * 3_600_000) : null;
  const todayStatus = (today?.status || (isCheckedIn || isCheckedOut ? 'present' : 'absent')).replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  const historyRows = history.map((row) => ({
    date: formatDate(row.date),
    checkIn: formatTime(row.check_in),
    checkOut: row.check_out ? formatTime(row.check_out) : row.is_checked_in ? 'In progress' : 'Not recorded',
    hours: formatHours(row.total_hours),
    status: row.status.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
  }));
  const monday = new Date();
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  monday.setHours(0, 0, 0, 0);
  const weekDays = Array.from({ length: 5 }, (_, index) => {
    const day = addDays(monday, index);
    const dateKey = toDateInput(day);
    const record = history.find((item) => item.date === dateKey) || (today?.date === dateKey ? today : null);
    const hours = dateKey === today?.date && isCheckedIn ? liveWorkedHours : Number(record?.total_hours || 0);
    return { label: day.toLocaleDateString('en-US', { weekday: 'narrow' }), dateKey, record, hours };
  });
  const daysPresent = weekDays.filter(({ record }) => record && !['absent', 'leave', 'on_leave'].includes(record.status.toLowerCase())).length;
  const weekHours = weekDays.reduce((sum, day) => sum + day.hours, 0);
  const weekCheckIns = weekDays.map(({ record }) => parseApiDateTime(record?.check_in)).filter((value): value is Date => Boolean(value));
  const averageCheckInMinutes = weekCheckIns.length
    ? Math.round(weekCheckIns.reduce((sum, value) => sum + value.getHours() * 60 + value.getMinutes(), 0) / weekCheckIns.length)
    : null;
  const averageCheckInLabel = averageCheckInMinutes === null
    ? '—'
    : new Date(2000, 0, 1, Math.floor(averageCheckInMinutes / 60), averageCheckInMinutes % 60).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

  useEffect(() => {
    if (!joiningDate) return;
    const allowedDefault = joiningDate > defaultFrom ? joiningDate : defaultFrom;
    setDateFrom((current) => current < joiningDate ? allowedDefault : current);
  }, [defaultFrom, joiningDate]);

  const applyAttendanceFilter = () => {
    if (!dateFrom || !dateTo) {
      setFilterError('Select both a From date and a To date.');
      return;
    }
    if (joiningDate && dateFrom < joiningDate) {
      setFilterError(`From date cannot be before your joining date (${formatDate(joiningDate)}).`);
      return;
    }
    if (dateTo > todayInput) {
      setFilterError('To date cannot be in the future.');
      return;
    }
    if (dateFrom > dateTo) {
      setFilterError('From date must be on or before To date.');
      return;
    }
    setFilterError(null);
    loadHistory(dateFrom, dateTo);
  };

  useEffect(() => {
    if (!isCheckedIn) return;
    const intervalId = window.setInterval(() => setClockNow(new Date()), 30000);
    return () => window.clearInterval(intervalId);
  }, [isCheckedIn]);

  const attendancePillClass = (status: string) => {
    const normalized = status.toLowerCase();
    if (normalized === 'present') return 'bg-[#e5f3e5] text-[#3f7d3f]';
    if (normalized === 'late') return 'bg-[#fbeee1] text-[#b8611f]';
    if (normalized.includes('leave')) return 'bg-[#edeef5] text-[#4b5673]';
    if (normalized === 'absent') return 'bg-[#fcecec] text-[#d64545]';
    return 'bg-[#f1eee7] text-[#8a8371]';
  };

  return (
    <PageShell
      title="Check In / Out"
      description="Track today's attendance and working hours."
      className="-mx-[var(--layout-main-padding-x)] -my-[var(--layout-main-padding-y)] min-h-screen bg-[#f7f3ec] px-[var(--layout-main-padding-x)] py-[var(--layout-main-padding-y)]"
    >
      {error && <div className="mb-5 rounded-xl border border-[#d64545]/20 bg-[#fcecec] px-4 py-3 text-sm text-[#d64545]">{error}</div>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)] xl:items-start">
        <div className="space-y-5">
          <section className="rounded-[18px] border border-[#ece5d8] bg-white p-5 shadow-[0_3px_10px_rgba(60,40,10,.025)] sm:p-7">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center">
              <div className="relative flex h-[166px] w-[166px] shrink-0 items-center justify-center rounded-full" style={{ background: `conic-gradient(#d97a34 ${ringPercent}%, #eee8dd ${ringPercent}% 100%)` }}>
                <div className="flex h-[130px] w-[130px] flex-col items-center justify-center rounded-full bg-white text-center shadow-[inset_0_0_0_1px_rgba(236,229,216,.75)]">
                  <span className="text-[10px] font-bold uppercase tracking-[.1em] text-[#a99e8a]">Worked</span>
                  <strong className="mt-1 text-[27px] tracking-[-.04em] text-[#1f2430]">{loading ? '…' : sessionHours}</strong>
                  <span className="mt-0.5 text-xs text-[#8a8371]">of 8h</span>
                </div>
              </div>

              <div className="min-w-0 flex-1">
                <div className={cn('flex items-center gap-2 text-xs font-bold uppercase tracking-[.07em]', isCheckedIn ? 'text-[#3f7d3f]' : 'text-[#8a8371]')}>
                  <span className={cn('h-3 w-3 rounded-full', isCheckedIn ? 'animate-pulse bg-[#43c979] ring-4 ring-[#e5f3e5]' : 'bg-[#b8b3a9] ring-4 ring-[#f1eee7]')} />
                  {loading ? 'Loading' : isCheckedIn ? 'Checked In' : isCheckedOut ? 'Checked Out' : 'Not Checked In'}
                </div>
                <div className="mt-3 text-sm text-[#8a8371]">
                  {today?.check_in ? <>Since <strong className="text-[#1f2430]">{formatTime(today.check_in)}</strong> · {formatDate(today.date)}</> : <>Ready for {formatDate(today?.date || todayInput)}</>}
                </div>
                <div className="mt-5">
                  {isCheckedIn ? <Button onClick={checkOut} disabled={!!actionLoading} className="border-[#d97a34] bg-[#d97a34] px-6 shadow-[0_8px_18px_rgba(217,122,52,.2)] hover:bg-[#c9611f]" icon={<LogIn size={16} />}>{actionLoading === 'check-out' ? 'Checking Out…' : 'Check Out'}</Button> : canCheckInToday ? <Button onClick={checkIn} disabled={!!actionLoading} className="border-[#d97a34] bg-[#d97a34] px-6 shadow-[0_8px_18px_rgba(217,122,52,.2)] hover:bg-[#c9611f]" icon={<LogIn size={16} />}>{actionLoading === 'check-in' ? 'Checking In…' : 'Check In'}</Button> : isCheckedOut ? <span className="inline-flex rounded-full bg-[#e5f3e5] px-4 py-2 text-xs font-bold text-[#3f7d3f]">Today&apos;s attendance is complete</span> : null}
                </div>
              </div>
            </div>

            <div className="mt-7 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-[#ece5d8] bg-[#fffdf9] px-5 py-4"><div className="text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">Check In</div><div className="mt-1.5 text-[19px] font-bold">{today?.check_in ? formatTime(today.check_in) : '—'}</div></div>
              <div className="rounded-xl border border-[#ece5d8] bg-[#fffdf9] px-5 py-4"><div className="text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">Expected Out</div><div className="mt-1.5 text-[19px] font-bold">{expectedOut ? expectedOut.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) : '—'}</div></div>
              <div className="rounded-xl border border-[#ece5d8] bg-[#fffdf9] px-5 py-4"><div className="text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">Status</div><div className={cn('mt-1.5 text-[19px] font-bold', todayStatus === 'Late' ? 'text-[#b8611f]' : todayStatus === 'Present' ? 'text-[#3f7d3f]' : 'text-[#4b5673]')}>{todayStatus}</div></div>
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border border-[#ece5d8] bg-white shadow-[0_3px_10px_rgba(60,40,10,.025)]" aria-labelledby="attendance-history-heading">
            <div className="flex flex-col gap-4 border-b border-[#ece5d8] px-5 py-5 sm:px-7 lg:flex-row lg:items-end lg:justify-between">
              <div><h2 id="attendance-history-heading" className="text-[17px] font-bold">Attendance History</h2>{joiningDate && <p className="mt-1 text-xs text-[#8a8371]">Available from your joining date: {formatDate(joiningDate)}</p>}</div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <label><span className="mb-1 block text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">From</span><input type="date" value={dateFrom} min={joiningDate || undefined} max={dateTo || todayInput} onChange={(event) => { setDateFrom(event.target.value); setFilterError(null); }} className="h-10 rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-3 text-sm outline-none focus:border-[#d97a34]" /></label>
                <label><span className="mb-1 block text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">To</span><input type="date" value={dateTo} min={dateFrom || joiningDate || undefined} max={todayInput} onChange={(event) => { setDateTo(event.target.value); setFilterError(null); }} className="h-10 rounded-[10px] border border-[#e4daca] bg-[#faf8f3] px-3 text-sm outline-none focus:border-[#d97a34]" /></label>
                <Button onClick={applyAttendanceFilter} disabled={historyLoading || loading} className="h-10">{historyLoading ? 'Loading…' : 'Apply'}</Button>
              </div>
            </div>
            {filterError && <div className="mx-5 mt-4 rounded-lg border border-[#d64545]/20 bg-[#fcecec] px-4 py-3 text-sm text-[#d64545] sm:mx-7">{filterError}</div>}
            {historyLoading ? <div className="px-7 py-10 text-center text-sm text-[#8a8371]">Loading attendance history…</div> : historyRows.length ? <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead className="bg-[#faf8f3] text-[10px] font-bold uppercase tracking-[.08em] text-[#a99e8a]"><tr><th className="px-7 py-3">Date</th><th className="px-5 py-3">Check In</th><th className="px-5 py-3">Check Out</th><th className="px-5 py-3">Hours</th><th className="px-5 py-3">Status</th></tr></thead><tbody className="divide-y divide-[#eee7dc]">{historyRows.map((row) => <tr key={row.date}><td className="px-7 py-4 font-bold">{row.date}</td><td className="px-5 py-4 text-[#8a8371]">{row.checkIn}</td><td className="px-5 py-4 text-[#8a8371]">{row.checkOut}</td><td className="px-5 py-4 text-[#8a8371]">{row.hours}</td><td className="px-5 py-4"><span className={cn('inline-flex rounded-full px-3 py-1 text-[11px] font-bold', attendancePillClass(row.status))}>{row.status}</span></td></tr>)}</tbody></table></div> : <div className="m-5 rounded-xl border border-dashed border-[#ddd1bc] px-5 py-9 text-center text-sm text-[#8a8371] sm:m-7">No attendance records found for this date range.</div>}
          </section>
        </div>

        <div className="space-y-5">
          <section className="rounded-2xl border border-[#ece5d8] bg-white p-5 shadow-[0_3px_10px_rgba(60,40,10,.025)] sm:p-7">
            <div className="mb-6 flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#fbeee1] text-[#d97a34]"><CalendarClock size={18} /></span><h2 className="text-[17px] font-bold">Today&apos;s Timeline</h2></div>
            <div className="relative ml-1 space-y-0">
              <div className="absolute bottom-6 left-[6px] top-3 w-0.5 bg-[#e3d8c6]" />
              <div className="relative flex gap-4 pb-7"><span className={cn('relative z-10 mt-1 h-3.5 w-3.5 shrink-0 rounded-full ring-4 ring-white', today?.check_in ? 'bg-[#d97a34]' : 'border-2 border-[#d8cbb5] bg-white')} /><div><div className="text-sm font-bold">Checked in</div><div className="mt-0.5 text-xs text-[#8a8371]">{today?.check_in ? formatTime(today.check_in) : 'Not recorded'}</div></div></div>
              <div className="relative flex gap-4"><span className={cn('relative z-10 mt-1 h-3.5 w-3.5 shrink-0 rounded-full ring-4 ring-white', today?.check_out ? 'bg-[#d97a34]' : 'border-2 border-[#d8cbb5] bg-white')} /><div><div className={cn('text-sm font-bold', today?.check_out ? 'text-[#1f2430]' : 'text-[#8a8371]')}>Check out</div><div className="mt-0.5 text-xs text-[#a99e8a]">{today?.check_out ? formatTime(today.check_out) : isCheckedIn ? 'Pending — still working' : 'Not recorded'}</div></div></div>
            </div>
          </section>

          <section className="rounded-2xl border border-[#eadbc5] bg-[#fbf5ea] p-5 shadow-[0_3px_10px_rgba(60,40,10,.02)] sm:p-7">
            <h2 className="mb-5 text-[17px] font-bold">This Week</h2>
            <div className="space-y-4 text-sm"><div className="flex justify-between"><span className="text-[#8a6a3a]">Days present</span><strong>{daysPresent} / 5</strong></div><div className="flex justify-between"><span className="text-[#8a6a3a]">Total hours</span><strong>{formatHours(weekHours)}</strong></div><div className="flex justify-between"><span className="text-[#8a6a3a]">Avg. check-in</span><strong>{averageCheckInLabel}</strong></div></div>
            <div className="mt-5 border-t border-[#e2d3bc] pt-4"><div className="grid grid-cols-5 gap-2">{weekDays.map((day) => <div key={day.dateKey} className="text-center"><div className="flex h-12 items-center justify-center rounded-lg bg-[#d97a34] text-[10px] font-bold text-white" style={{ opacity: day.hours > 0 ? Math.max(.45, Math.min(1, day.hours / 8)) : .14 }}>{day.hours > 0 ? `${Math.round(day.hours * 10) / 10}h` : '—'}</div><div className="mt-1.5 text-[11px] text-[#a78254]">{day.label}</div></div>)}</div></div>
          </section>
        </div>
      </div>
    </PageShell>
  );

}

export function EmployeeRequestsPage() {
  return (
    <PageShell title="Requests" description="Raise work-from-home, overtime, shift change, and reimbursement requests.">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {['Work From Home', 'Short Permission', 'Overtime', 'Expense Reimbursement'].map((request) => (
          <Card key={request} className="p-5">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-olive/10 text-olive">
              <Send size={18} />
            </div>
            <div className="text-sm font-bold text-[var(--color-brand-navy)]">{request}</div>
            <div className="mt-1 text-xs text-gray-500">Dummy request workflow</div>
          </Card>
        ))}
      </div>
    </PageShell>
  );
}

export function EmployeeDocumentsPage() {
  return (
    <PageShell title="Documents" description="Access payslips, policy documents, certificates, and personal files.">
      <SimpleTable
        headers={['Document', 'Category', 'Updated', 'Action']}
        rows={[
          ['May 2026 Payslip', 'Payroll', 'Jun 1, 2026', <Button size="sm" variant="ghost" icon={<Download size={14} />}>Download</Button>],
          ['Employee Handbook', 'Policy', 'May 12, 2026', <Button size="sm" variant="ghost" icon={<Download size={14} />}>Download</Button>],
          ['ID Proof', 'Personal', 'Apr 26, 2026', <Button size="sm" variant="soft" icon={<Upload size={14} />}>Update</Button>],
        ]}
      />
    </PageShell>
  );
}

export function CompanyHandbookPage() {
  const leavePolicies = [
    {
      name: 'Casual Leave',
      code: 'CL',
      balance: '12 days / year',
      availability: 'Planned personal time off',
      rules: 'Can be requested for future dates. Approval is required before the leave is confirmed.',
      expiry: 'Carry forward up to 5 days',
      badge: 'Planned',
    },
    {
      name: 'Sick Leave',
      code: 'SL',
      balance: '10 days / year',
      availability: 'Illness or medical recovery',
      rules: 'Can be requested across available dates. Approval is required before the leave is confirmed.',
      expiry: 'Expires at year end',
      badge: 'Health',
    },
    {
      name: 'Earned Leave',
      code: 'EL',
      balance: '15 days / year',
      availability: 'Longer planned time off',
      rules: 'Can be requested for future dates. Best used for vacations or planned breaks.',
      expiry: 'Carry forward up to 10 days',
      badge: 'Paid',
    },
    {
      name: 'Paternity Leave',
      code: 'PL',
      balance: '15 days / eligible employee',
      availability: 'Applicable based on employee profile',
      rules: 'Can be requested for future dates. Eligibility is controlled by HR profile configuration.',
      expiry: 'Expires at year end',
      badge: 'Eligible',
    },
    {
      name: 'Maternity Leave',
      code: 'ML',
      balance: 'Policy based',
      availability: 'Shown only when applicable',
      rules: 'Displayed only for eligible employees. HR controls eligibility and policy limits.',
      expiry: 'Policy based',
      badge: 'Profile based',
    },
    {
      name: 'Bereavement Leave',
      code: 'BL',
      balance: '5 days / year',
      availability: 'Loss of an immediate family member',
      rules: 'Allowed for current or recent dates. Future dates show a warning because they are uncommon.',
      expiry: 'Expires at year end',
      badge: 'Sensitive',
    },
    {
      name: 'Compensatory Off',
      code: 'CO',
      balance: 'Earned by policy',
      availability: 'Time off against approved extra work',
      rules: 'Can be requested for future dates when balance is available.',
      expiry: 'Expires at year end',
      badge: 'Comp off',
    },
    {
      name: 'Loss of Pay',
      code: 'LOP',
      balance: 'On request',
      availability: 'When paid balance is unavailable',
      rules: 'Manager/HR approval is required. This leave may affect payroll.',
      expiry: 'No balance expiry',
      badge: 'Unpaid',
    },
  ];

  const holidayPolicies = [
    {
      title: 'Public Holidays',
      description: 'Region-specific official holidays such as Republic Day, Independence Day, Thanksgiving, or Christmas.',
      detail: 'These holidays are excluded from working-day calculations when they apply to your region.',
    },
    {
      title: 'Company Holidays',
      description: 'Company-wide holidays such as foundation day or organization-wide closures.',
      detail: 'These are treated as non-working days for all applicable employees.',
    },
    {
      title: 'Floating Holidays',
      description: 'Employee-selectable holidays from a predefined regional list.',
      detail: 'You must choose the holiday from the Apply Leave page. The selected date is locked to that holiday.',
    },
    {
      title: 'Optional Holidays',
      description: 'Regional optional holidays that employees may choose based on preference or observance.',
      detail: 'Availability depends on region and whether the holiday has already been requested or used.',
    },
  ];

  return (
    <PageShell title="Company Handbook" description="View company policies, guidelines, and employee resources.">
      <div className="space-y-4">
          <Card className="overflow-hidden">
            <CardHeader title="Holiday Handbook" icon={<BookOpen size={17} />} />
            <div className="grid gap-4 px-5 py-5 lg:grid-cols-[1.4fr_1fr]">
              <div>
                <h2 className="text-xl font-bold text-[var(--color-brand-navy)]">Leave and holiday policy guide</h2>
                <p className="mt-2 text-sm leading-6 text-gray-500">
                  Use this handbook to understand which leave type to apply, how holidays affect working days,
                  and what requires manager or HR approval. Your visible leave types may vary based on your profile,
                  gender, work location, role, and company policy.
                </p>
              </div>
              <div className="rounded-xl border border-accent/15 bg-accent-light p-4">
                <div className="flex items-center gap-2 text-sm font-bold text-accent-dark">
                  <CalendarCheck size={16} />
                  Important
                </div>
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  Public and company holidays are not counted as working days. Floating and optional holidays must be
                  selected from the approved holiday list, and the backend validates region, date, and duplicate usage.
                </p>
              </div>
            </div>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader title="Leave Types" icon={<WalletCards size={17} />} />
            <div className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-4">
              {leavePolicies.map((policy) => (
                <div key={policy.code} className="rounded-xl border border-[var(--color-border)] bg-white p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-bold text-[var(--color-brand-navy)]">{policy.name}</div>
                      <div className="mt-1 text-xs font-semibold uppercase tracking-wide text-gray-400">{policy.code}</div>
                    </div>
                    <Badge variant="neutral">{policy.badge}</Badge>
                  </div>
                  <div className="mt-4 space-y-3 text-sm">
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Balance</div>
                      <div className="mt-1 font-semibold text-[var(--color-brand-navy)]">{policy.balance}</div>
                    </div>
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Use For</div>
                      <div className="mt-1 text-gray-600">{policy.availability}</div>
                    </div>
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Rules</div>
                      <div className="mt-1 leading-5 text-gray-600">{policy.rules}</div>
                    </div>
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Expiry</div>
                      <div className="mt-1 text-gray-600">{policy.expiry}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader title="Holiday Types" icon={<CalendarCheck size={17} />} />
            <div className="grid gap-3 p-5 md:grid-cols-2">
              {holidayPolicies.map((holiday) => (
                <div key={holiday.title} className="rounded-xl border border-[var(--color-border)] bg-white p-4">
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light text-accent">
                    <CalendarCheck size={18} />
                  </div>
                  <div className="text-sm font-bold text-[var(--color-brand-navy)]">{holiday.title}</div>
                  <p className="mt-2 text-sm leading-6 text-gray-600">{holiday.description}</p>
                  <p className="mt-2 text-xs leading-5 text-gray-500">{holiday.detail}</p>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="p-4">
              <div className="flex items-center gap-2 text-sm font-bold text-[var(--color-brand-navy)]">
                <Briefcase size={16} className="text-accent" />
                Region Rules
              </div>
              <p className="mt-2 text-sm leading-6 text-gray-500">
                Holidays are shown based on work location. Global holidays apply to everyone; India, UAE, and US
                holidays apply only to employees mapped to those regions.
              </p>
            </Card>
            <Card className="p-4">
              <div className="flex items-center gap-2 text-sm font-bold text-[var(--color-brand-navy)]">
                <Clock3 size={16} className="text-accent" />
                Working Days
              </div>
              <p className="mt-2 text-sm leading-6 text-gray-500">
                Weekend days and applicable public/company holidays are excluded from working-day calculations on
                leave requests.
              </p>
            </Card>
            <Card className="p-4">
              <div className="flex items-center gap-2 text-sm font-bold text-[var(--color-brand-navy)]">
                <CheckCircle2 size={16} className="text-accent" />
                Approvals
              </div>
              <p className="mt-2 text-sm leading-6 text-gray-500">
                Submitted leave requests go to the reporting manager or HR approval queue. Balances update after
                approval and remain visible in your leave history.
              </p>
            </Card>
          </div>
      </div>
    </PageShell>
  );
}

export function HolidaysPage() {
  const { user } = useAuth();
  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  return (
    <PageShell title="Holiday Calendar" description="View company holidays and optional holiday options.">
      <HolidayCalendarContent headers={headers} />
    </PageShell>
  );
}

export function EmployeeNotificationsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<NotificationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const loadNotifications = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/notifications?limit=100`, { headers });
      const data = await res.json().catch(() => null);
      setItems(data?.notifications || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [headers, user]);

  useEffect(() => {
    loadNotifications();
  }, [loadNotifications]);

  const markRead = async (id: string) => {
    await fetch(`${API_BASE}/notifications/${id}/read`, { method: 'PUT', headers }).catch(() => undefined);
    setItems((current) => current.map((item) => item.id === id ? { ...item, is_read: true } : item));
  };

  const markAllRead = async () => {
    await fetch(`${API_BASE}/notifications/mark-all-read`, { method: 'PUT', headers }).catch(() => undefined);
    setItems((current) => current.map((item) => ({ ...item, is_read: true })));
  };

  const unreadCount = items.filter((item) => !item.is_read).length;

  return (
    <PageShell title="Notifications" description="See HR alerts, approval updates, and reminders.">
      <Card className="overflow-hidden">
        <CardHeader
          title="Latest Updates"
          icon={<Bell size={17} />}
          badge={`${unreadCount} unread`}
          badgeColor={unreadCount > 0 ? 'olive' : 'neutral'}
          action={unreadCount > 0 ? (
            <Button size="sm" variant="soft" onClick={markAllRead}>Mark all as read</Button>
          ) : undefined}
        />
        {loading ? (
          <div className="px-5 py-8 text-center text-sm text-gray-500">Loading notifications...</div>
        ) : items.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-olive/10 text-olive">
              <Bell size={22} />
            </div>
            <div className="text-sm font-bold text-[var(--color-brand-navy)]">No notifications yet</div>
            <div className="mt-1 text-xs text-gray-500">Approval updates and HR alerts will appear here.</div>
          </div>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {items.map((item) => (
              <div key={item.id} className={cn('grid gap-3 px-5 py-4 md:grid-cols-[1fr_150px_120px]', !item.is_read && 'bg-olive/5')}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="truncate text-sm font-bold text-[var(--color-brand-navy)]">{item.title}</div>
                    {!item.is_read && <span className="h-2 w-2 shrink-0 rounded-full bg-olive" />}
                  </div>
                  <div className="mt-1 text-sm text-gray-500">{item.message || 'New update'}</div>
                  <div className="mt-1 text-xs text-gray-400">{formatDateTime(item.created_at)}</div>
                </div>
                <div className="flex items-center md:justify-center">
                  <Badge variant={item.is_read ? 'neutral' : 'olive'}>{item.is_read ? 'read' : 'unread'}</Badge>
                </div>
                <div className="flex items-center md:justify-end">
                  {!item.is_read ? (
                    <Button size="sm" variant="ghost" onClick={() => markRead(item.id)}>Mark read</Button>
                  ) : (
                    <span className="text-xs font-semibold text-gray-400">No action</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </PageShell>
  );
}

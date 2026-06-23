import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Bell,
  Briefcase,
  BookOpen,
  CalendarCheck, CalendarClock, CalendarPlus, CheckCircle2, ClipboardCheck,
  Clock3, Download, FileText, LogIn, Pencil, Plus,
  RefreshCw, Send, Trash2, Upload, WalletCards, X,
} from 'lucide-react';
import { Badge, Button, Card, CardHeader } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const attendanceCache: Record<string, {
  today: AttendanceRecord | null;
  history: AttendanceRecord[];
}> = {};

const dashboardCache: Record<string, {
  leaveSummary: LeaveSummary | null;
  timesheetSummary: TimesheetSummary | null;
  timesheetHistory: TimesheetWeek[];
  leaveApprovalRows: LeaveRequestItem[];
  timesheetApprovalRows: TimesheetApprovalItem[];
  activeProjects: DashboardAllocation[];
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
  manager_name: string | null;
  allocation_percentage: number;
  allocation_role: string;
  status: string;
  start_date: string;
  end_date: string | null;
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
  reason: string;
  status: string;
  reporting_manager?: string | null;
  pending_with?: string | null;
  reviewed_by?: string | null;
  reviewer_notes?: string | null;
}

interface LeaveSummary {
  reporting_manager?: string | null;
  balances: LeaveBalanceItem[];
  requests: LeaveRequestItem[];
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

const recentActivity = [
  { title: 'Sick leave approved', meta: 'May 21, 2026', status: 'Approved' },
  { title: 'Timesheet submitted', meta: 'Week 22', status: 'Pending' },
  { title: 'WFH request created', meta: 'June 6, 2026', status: 'Review' },
];

const attendanceRows = [
  { date: 'Jun 3, 2026', checkIn: '09:18 AM', checkOut: 'In progress', hours: '4h 22m', status: 'Present' },
  { date: 'Jun 2, 2026', checkIn: '09:31 AM', checkOut: '06:18 PM', hours: '8h 47m', status: 'Late' },
  { date: 'Jun 1, 2026', checkIn: '09:08 AM', checkOut: '06:05 PM', hours: '8h 57m', status: 'Present' },
];

function useAttendance() {
  const { user } = useAuth();
  const cacheKey = user?.id || user?.email || '';
  const cachedAttendance = cacheKey ? attendanceCache[cacheKey] : undefined;
  const [today, setToday] = useState<AttendanceRecord | null>(cachedAttendance?.today ?? null);
  const [history, setHistory] = useState<AttendanceRecord[]>(cachedAttendance?.history ?? []);
  const [loading, setLoading] = useState(!cachedAttendance);
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
      const [todayRes, historyRes] = await Promise.all([
        fetch(`${API_BASE}/attendance/me/today`, { headers }),
        fetch(`${API_BASE}/attendance/me/history`, { headers }),
      ]);
      if (!todayRes.ok) throw new Error('Could not load today\'s attendance.');
      if (!historyRes.ok) throw new Error('Could not load attendance history.');
      const todayData = await todayRes.json();
      const historyData = await historyRes.json();
      setToday(todayData);
      setHistory(historyData);
      if (cacheKey) {
        attendanceCache[cacheKey] = { today: todayData, history: historyData };
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load attendance.');
    } finally {
      setLoading(false);
    }
  }, [cacheKey, headers, user]);

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
    loading,
    actionLoading,
    error,
    checkIn: () => runAction('check-in'),
    checkOut: () => runAction('check-out'),
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

function makeTimesheetRow(project?: TimesheetProject, code = 'PRJ', workDate = toDateInput(new Date())): TimesheetRow {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    workDate,
    entryCode: code,
    projectKey: project?.id || project?.code || code,
    projectName: project?.name || (code === 'POC' ? 'Proof of Concept' : code === 'BRK' ? 'Break / Non-working' : 'Project work'),
    startTime: code === 'BRK' ? '12:00' : '09:00',
    endTime: code === 'BRK' ? '13:00' : '17:00',
    notes: '',
  };
}

function rowsFromTimesheet(week: TimesheetWeek, projects: TimesheetProject[]) {
  if (!week.entries.length) return [];
  return week.entries.map((entry) => {
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

function timeBlockHours(row: TimesheetRow) {
  if (!row.startTime || !row.endTime || row.endTime <= row.startTime) return 0;
  const [startHour, startMinute] = row.startTime.split(':').map(Number);
  const [endHour, endMinute] = row.endTime.split(':').map(Number);
  return Math.round((((endHour * 60 + endMinute) - (startHour * 60 + startMinute)) / 60) * 100) / 100;
}

function PageShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="animate-fade-up">
      <div className={description ? 'mb-5' : 'mb-3'}>
        <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">{title}</h1>
        {description && <p className="text-sm text-gray-500">{description}</p>}
      </div>
      {children}
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
      className={cn('p-5', onClick && 'cursor-pointer transition-all hover:-translate-y-0.5 hover:border-olive/30 hover:shadow-card-lg')}
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
          <div className="mt-2 text-2xl font-bold text-[#2F3437]">{value}</div>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-olive/10 text-olive">
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
      <div className="rounded-lg border border-[#DDE3EA] bg-white px-4 py-3 text-sm text-gray-500">
        Checking allocation compliance...
      </div>
    );
  }
  if (!report) return null;

  const isIssue = report.overall_status === 'warning' || report.overall_status === 'violation';
  return (
    <div className={cn(
      'rounded-lg border bg-white shadow-[0_6px_18px_rgba(17,24,39,0.05)]',
      isIssue ? 'border-status-warning/30' : 'border-[#DDE3EA]'
    )}>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-bold text-[#2F3437]">Allocation Compliance</span>
            <Badge variant={complianceBadgeVariant(report.overall_status)}>
              {complianceStatusLabel(report.overall_status)}
            </Badge>
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Expected week: {formatNumber(report.expected_weekly_hours)}h. Compliant within {formatNumber(report.compliant_threshold)}h, warning above {formatNumber(report.compliant_threshold)}h, violation above {formatNumber(report.warning_threshold)}h.
            {report.used_default_hours ? ' Default weekly hours were used.' : ''}
          </div>
        </div>
        {onToggle && <span className="text-xs font-semibold text-olive">{open ? 'Hide' : 'Show'}</span>}
      </button>
      {open && (
        <div className="border-t border-[#E5E7EB] px-4 py-3">
          {report.no_allocations_found ? (
            <div className="rounded-lg border border-[#E5E7EB] bg-warm-bg px-4 py-3 text-sm text-gray-600">
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
                <tbody className="divide-y divide-[#E5E7EB]">
                  {report.project_rows.map((row) => (
                    <tr key={`${row.project_id || row.project_name}-${row.allocation_percentage}`}>
                      <td className="px-3 py-2 font-semibold text-[#2F3437]">{row.project_name}</td>
                      <td className="px-3 py-2 text-right text-gray-500">{row.allocation_percentage}%</td>
                      <td className="px-3 py-2 text-right">{formatNumber(row.expected_hours)}h</td>
                      <td className="px-3 py-2 text-right">{formatNumber(row.actual_hours)}h</td>
                      <td className={cn('px-3 py-2 text-right font-semibold', row.status !== 'compliant' && 'text-status-warning')}>{signedHours(row.variance_hours)}</td>
                      <td className="px-3 py-2 text-right"><Badge variant={complianceBadgeVariant(row.status)}>{row.status}</Badge></td>
                    </tr>
                  ))}
                  <tr className="bg-warm-bg/60">
                    <td className="px-3 py-2 font-bold text-[#2F3437]">Unallocated hours</td>
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
  const statusVariantName: 'success' | 'error' | 'warning' | 'neutral' = summary?.status === 'approved'
    ? 'success'
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
      className="cursor-pointer p-5 transition-all hover:-translate-y-0.5 hover:border-olive/30 hover:shadow-card-lg"
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
                <span className="truncate text-[#2F3437]">{value}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-olive/10 text-olive">
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
        <tbody className="divide-y divide-[#E5E7EB]">
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="text-[#2F3437]">
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
      user.id ? fetch(`${API_BASE}/allocations/employee/${user.id}/active`, { headers }).then((res) => res.ok ? res.json() : null) : Promise.resolve(null),
    ]).then(([leaveData, timesheetSummaryData, timesheetHistoryData, approvalsData, timesheetApprovalsData, activeProjectsData]) => {
      const existingCache = dashboardCacheKey ? dashboardCache[dashboardCacheKey] : undefined;
      const nextLeaveSummary = leaveData || existingCache?.leaveSummary || null;
      const nextTimesheetSummary = timesheetSummaryData || existingCache?.timesheetSummary || null;
      const nextTimesheetHistory = timesheetHistoryData || existingCache?.timesheetHistory || [];
      const nextApprovalRows = approvalsData?.approvals || existingCache?.leaveApprovalRows || [];
      const nextTimesheetApprovalRows = timesheetApprovalsData?.approvals || existingCache?.timesheetApprovalRows || [];
      const nextActiveProjects = activeProjectsData || existingCache?.activeProjects || [];
      if (leaveData) setLeaveSummary(leaveData);
      if (timesheetSummaryData) setTimesheetSummary(timesheetSummaryData);
      if (timesheetHistoryData) setTimesheetHistory(timesheetHistoryData);
      if (approvalsData?.approvals) setApprovalRows(approvalsData.approvals);
      if (timesheetApprovalsData?.approvals) setTimesheetApprovalRows(timesheetApprovalsData.approvals);
      if (activeProjectsData) setActiveProjects(activeProjectsData);
      if (dashboardCacheKey) {
        dashboardCache[dashboardCacheKey] = {
          leaveSummary: nextLeaveSummary,
          timesheetSummary: nextTimesheetSummary,
          timesheetHistory: nextTimesheetHistory,
          leaveApprovalRows: nextApprovalRows,
          timesheetApprovalRows: nextTimesheetApprovalRows,
          activeProjects: nextActiveProjects,
        };
      }
    }).catch(() => {
      // Keep dashboard usable even if one summary endpoint is temporarily unavailable.
    });
  }, [dashboardCacheKey, headers, user]);

  const availableLeaveDays = useMemo(() => {
    const total = (leaveSummary?.balances || []).reduce((sum, leave) => (
      typeof leave.available === 'number' ? sum + leave.available : sum
    ), 0);
    return formatNumber(total);
  }, [leaveSummary?.balances]);

  const pendingOwnRequests = (leaveSummary?.requests || []).filter((request) => request.status === 'pending').length;
  const pendingTimesheet = timesheetSummary?.status === 'submitted' || timesheetSummary?.status === 'approved' ? 0 : 1;
  const pendingActions = pendingOwnRequests + pendingTimesheet + approvalRows.length + timesheetApprovalRows.length;
  const timesheetCardWeekStart = timesheetSummary?.week_start || toDateInput(startOfLocalWeek());
  const openTimesheetSummary = () => navigate(`/employee/timesheets?week_start=${encodeURIComponent(timesheetCardWeekStart)}`);
  const timesheetActivityRows = timesheetHistory
    .filter((week) => week.status && week.status !== 'not_started')
    .sort((a, b) => {
      const weekEndCompare = new Date(`${b.week_end}T00:00:00`).getTime() - new Date(`${a.week_end}T00:00:00`).getTime();
      if (weekEndCompare !== 0) return weekEndCompare;
      const bUpdated = b.reviewed_at || b.entries.map((entry) => entry.id).join('');
      const aUpdated = a.reviewed_at || a.entries.map((entry) => entry.id).join('');
      return bUpdated.localeCompare(aUpdated);
    })
    .slice(0, 3)
    .map((week) => ({
      title: `Timesheet ${statusLabel(week.status)}`,
      meta: `Week: ${weekLabel(week.week_start)}`,
      status: week.status,
      key: `timesheet-${week.week_start}-${week.status}`,
    }));
  const dashboardActivity = [
    ...(leaveSummary?.requests || []).slice(0, 3).map((request) => ({
      title: `${request.leave_type} ${request.status}`,
      meta: request.status === 'pending'
        ? `Pending with ${request.pending_with || request.reporting_manager || 'manager'}`
        : `${formatDate(request.start_date)} - ${formatDate(request.end_date)}`,
      status: request.status,
      key: `leave-${request.id}`,
    })),
    ...timesheetActivityRows,
  ].slice(0, 4);

  return (
    <PageShell title="My Dashboard" description="Your daily attendance, leave, and action summary.">
      {error && (
        <div className="mb-5 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Today" value={loading ? 'Loading...' : attendanceLabel(today)} icon={<LogIn size={21} />} />
        <MetricCard label="Available Leave" value={leaveSummary ? `${availableLeaveDays} days` : 'Loading...'} icon={<WalletCards size={21} />} />
        <TimesheetSummaryCard summary={timesheetSummary} loading={!timesheetSummary} onClick={openTimesheetSummary} />
        <MetricCard label="Pending Actions" value={`${pendingActions}`} icon={<ClipboardCheck size={21} />} />
      </div>
      {activeProjects.length > 0 && (
        <Card className="mt-5 p-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold text-[#2F3437]">
              <Briefcase size={17} className="text-accent" />
              My Projects
            </div>
            <Button size="sm" variant="ghost" onClick={() => navigate('/projects')}>View Projects</Button>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {activeProjects.slice(0, 3).map((allocation) => (
              <div key={allocation.id} className="rounded-xl border border-[#E5E7EB] bg-warm-bg px-4 py-3">
                <div className="truncate text-sm font-bold text-[#2F3437]">{allocation.project_name || allocation.project_id || 'Assigned project'}</div>
                <div className="mt-1 text-xs text-gray-500">{allocation.allocation_role} · {allocation.allocation_percentage}%</div>
                <div className="mt-2 text-[11px] font-semibold text-gray-400">Manager: {allocation.manager_name || 'Not assigned'}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader title="Recent Activity" icon={<CalendarClock size={17} />} />
          <div className="divide-y divide-[#E5E7EB]">
            {(dashboardActivity.length ? dashboardActivity : recentActivity).map((item) => {
              const rowKey = (item as { key?: string }).key || item.title;
              return (
                <div key={rowKey} className="flex items-center justify-between px-5 py-4">
                  <div>
                    <div className="text-sm font-semibold text-[#2F3437]">{item.title}</div>
                    <div className="text-xs text-gray-500">{item.meta}</div>
                  </div>
                  <Badge variant={item.status === 'approved' || item.status === 'Approved' || item.status === 'submitted' ? 'success' : item.status === 'rejected' ? 'error' : 'warning'}>{item.status}</Badge>
                </div>
              );
            })}
          </div>
        </Card>
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="text-sm font-bold text-[#2F3437]">Quick Actions</div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Button onClick={() => navigate('/employee/apply-leave')} icon={<CalendarPlus size={15} />}>Apply Leave</Button>
            <Button onClick={() => navigate('/employee/timesheets')} variant="soft" icon={<Clock3 size={15} />}>Submit Timesheet</Button>
            <Button onClick={() => navigate('/employee/apply-leave?quick=sick-today')} variant="ghost" icon={<CalendarPlus size={15} />}>Report Sick Today</Button>
            {isCheckedIn ? (
              <Button onClick={checkOut} disabled={!!actionLoading} variant="ghost" icon={<LogIn size={15} />}>
                {actionLoading === 'check-out' ? 'Checking Out' : 'Check Out'}
              </Button>
            ) : (
              <Button onClick={checkIn} disabled={!!actionLoading || !!today?.check_out} variant="ghost" icon={<LogIn size={15} />}>
                {actionLoading === 'check-in' ? 'Checking In' : 'Check In'}
              </Button>
            )}
            <Button onClick={() => navigate('/employee/requests')} variant="ghost" icon={<Send size={15} />}>New Request</Button>
          </div>
        </Card>
      </div>
    </PageShell>
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
      setLeaveForm((current) => ({
        ...current,
        leaveTypeId: current.leaveTypeId || data.balances?.[0]?.leave_type_id || '',
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
    setLeaveForm((current) => ({ ...current, [key]: value }));
  };

  const saveLeaveRequest = async (action: 'draft' | 'submit') => {
    setSavingLeave(action);
    setLeaveError(null);
    setLeaveSuccess(null);
    try {
      if (!leaveForm.leaveTypeId || !leaveForm.fromDate || !leaveForm.toDate || !leaveForm.reason.trim()) {
        throw new Error('Select leave type, dates, and enter a reason before saving.');
      }
      if (leavePolicyMessage && selectedPolicy?.allow_future_dates === false) {
        throw new Error(leavePolicyMessage);
      }
      if (minAllowedDate && leaveForm.fromDate < minAllowedDate) {
        throw new Error(`${selectedLeaveType?.type || 'This leave type'} can only be applied up to ${selectedPolicy?.past_date_limit_days} days in the past.`);
      }
      const res = await fetch(`${API_BASE}/leaves/me/requests${editingLeaveId ? `/${editingLeaveId}` : ''}`, {
        method: editingLeaveId ? 'PUT' : 'POST',
        headers,
        body: JSON.stringify({
          leave_type_id: leaveForm.leaveTypeId,
          start_date: leaveForm.fromDate,
          end_date: leaveForm.toDate,
          reason: leaveForm.reason.trim(),
          action,
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not save leave request.');
      setLeaveSummary(data);
      setReportingManager(data.reporting_manager || 'Not assigned');
      setEditingLeaveId(null);
      setLeaveForm((current) => ({
        leaveTypeId: data.balances?.[0]?.leave_type_id || current.leaveTypeId,
        fromDate: '',
        toDate: '',
        reason: '',
      }));
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
  const selectedPolicy = selectedLeaveType?.date_policy;
  const todayInput = toDateInput(new Date());
  const minAllowedDate = selectedPolicy?.past_date_limit_days != null
    ? toDateInput(addDays(new Date(`${todayInput}T00:00:00`), -selectedPolicy.past_date_limit_days))
    : undefined;
  const maxAllowedDate = selectedPolicy?.allow_future_dates === false ? todayInput : undefined;
  const selectedHasFutureDate = [leaveForm.fromDate, leaveForm.toDate].some((value) => value && value > todayInput);
  const leavePolicyMessage = selectedLeaveType && selectedPolicy?.allow_future_dates === false && selectedHasFutureDate
    ? `${selectedLeaveType.type} cannot be applied for future dates.`
    : selectedLeaveType && selectedPolicy?.future_date_warning && selectedHasFutureDate
      ? selectedPolicy.future_date_warning
      : null;

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
      leaveTypeId: leaveBalances[0]?.leave_type_id || current.leaveTypeId,
      fromDate: '',
      toDate: '',
      reason: '',
    }));
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
    setLeaveError(null);
    setLeaveSuccess('Draft loaded. Make your changes and save or submit.');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const deleteLeaveDraft = async (request: LeaveRequestItem) => {
    if (request.status !== 'draft') return;
    const confirmed = window.confirm('Delete this draft leave request?');
    if (!confirmed) return;
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
          leaveTypeId: data.balances?.[0]?.leave_type_id || current.leaveTypeId,
          fromDate: '',
          toDate: '',
          reason: '',
        }));
      }
      setLeaveSuccess('Draft leave request deleted.');
    } catch (err) {
      setLeaveError(err instanceof Error ? err.message : 'Could not delete draft leave request.');
    } finally {
      setSavingLeave(null);
    }
  };

  return (
    <PageShell title="Apply Leave">
      {leaveError && (
        <div className="mb-3 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {leaveError}
        </div>
      )}
      {leaveSuccess && (
        <div className="mb-3 rounded-lg border border-status-success/20 bg-status-success/10 px-4 py-3 text-sm text-status-success">
          {leaveSuccess}
        </div>
      )}
      <Card className="p-4">
        {editingLeaveId && (
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-olive/20 bg-olive/5 px-3 py-2 text-sm text-olive-dark">
            <span className="font-semibold">Editing saved draft</span>
            <button onClick={cancelLeaveEdit} className="text-xs font-bold text-olive hover:underline">Cancel edit</button>
          </div>
        )}
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">Leave Type</span>
            <select
              value={leaveForm.leaveTypeId}
              onChange={(event) => {
                updateLeaveForm('leaveTypeId', event.target.value);
                setLeaveError(null);
              }}
              className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm text-[#2F3437] outline-none focus:border-olive"
            >
              {leaveBalances.map((leave) => (
                <option key={leave.leave_type_id} value={leave.leave_type_id}>{leave.type}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">From Date</span>
            <input
              type="date"
              value={leaveForm.fromDate}
              min={minAllowedDate}
              max={maxAllowedDate}
              onChange={(event) => updateLeaveForm('fromDate', event.target.value)}
              className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm text-[#2F3437] outline-none focus:border-olive"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">To Date</span>
            <input
              type="date"
              value={leaveForm.toDate}
              min={leaveForm.fromDate || minAllowedDate}
              max={maxAllowedDate}
              onChange={(event) => updateLeaveForm('toDate', event.target.value)}
              className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm text-[#2F3437] outline-none focus:border-olive"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">Reporting Manager</span>
            <input
              value={reportingManager}
              readOnly
              className="w-full rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2 text-sm text-gray-500 outline-none"
            />
          </label>

          <label className="block md:col-span-2 xl:col-span-3">
            <div className="mb-1.5 flex items-center justify-between gap-3">
              <span className="block text-[13px] font-semibold text-[#2F3437]">Reason</span>
              <span className="text-xs text-gray-400">{leaveForm.reason.length}/200</span>
            </div>
            <textarea
              value={leaveForm.reason}
              onChange={(event) => updateLeaveForm('reason', event.target.value)}
              placeholder="Add reason here"
              rows={2}
              maxLength={200}
              className="w-full resize-none rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm text-[#2F3437] outline-none focus:border-olive"
            />
            {leavePolicyMessage && (
              <div className={cn(
                'mt-1 text-xs font-semibold',
                selectedPolicy?.allow_future_dates === false ? 'text-status-error' : 'text-status-warning'
              )}>
                {leavePolicyMessage}
              </div>
            )}
            {selectedLeaveType?.code?.toUpperCase() === 'SL' && minAllowedDate && (
              <div className="mt-1 text-xs text-gray-500">
                Sick Leave can be reported for today or up to {selectedPolicy?.past_date_limit_days} days in the past.
              </div>
            )}
          </label>
          <div className="flex items-end justify-end gap-2">
            <Button variant="ghost" disabled={!!savingLeave || loadingLeave} onClick={() => saveLeaveRequest('draft')}>
              {savingLeave === 'draft' ? 'Saving' : 'Save Draft'}
            </Button>
            <Button icon={<Send size={15} />} disabled={!!savingLeave || loadingLeave} onClick={() => saveLeaveRequest('submit')}>
              {savingLeave === 'submit' ? 'Submitting' : editingLeaveId ? 'Submit Draft' : 'Submit Request'}
            </Button>
          </div>
        </div>
      </Card>

      <div className="mt-3">
        <div className="mb-2 flex items-center gap-2 text-base font-bold text-[#2F3437]">
          <WalletCards size={18} className="text-olive" />
          Leave Balance
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {loadingLeave ? (
            <Card className="p-3 text-sm text-gray-500">Loading leave balances...</Card>
          ) : leaveBalances.map((leave) => (
            <Card key={leave.leave_type_id} className="p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-bold text-[#2F3437]">{leave.type}</div>
                  <div className="mt-1.5 text-xs text-gray-500">
                    Used <span className="font-bold text-[#2F3437]">{leave.used}</span>
                    <span className="mx-2 text-gray-300">|</span>
                    Pending <span className="font-bold text-[#2F3437]">{leave.pending}</span>
                  </div>
                  <div className="mt-1 text-[11px] font-medium text-gray-400">{leave.expiry_label}</div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-olive">{leave.available}</div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Available</div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
      <Card className="mt-3 overflow-hidden">
        <CardHeader title="My Leave Requests" icon={<ClipboardCheck size={17} />} />
        {leaveRequests.length === 0 ? (
          <div className="px-5 py-5 text-sm text-gray-500">No leave requests yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[980px]">
              <div className="grid grid-cols-[1.25fr_1fr_1.2fr_110px_150px] gap-4 border-y border-[#E5E7EB] bg-warm-bg px-5 py-3 text-[11px] font-bold uppercase tracking-wide text-gray-400">
                <div>Leave</div>
                <div>Progress</div>
                <div>Reason</div>
                <div className="text-center">Status</div>
                <div className="text-center">Actions</div>
              </div>
          <div className="divide-y divide-[#E5E7EB]">
            {leaveRequests.slice(0, 5).map((request) => (
              <div key={request.id} className="grid grid-cols-[1.25fr_1fr_1.2fr_110px_150px] items-center gap-4 px-5 py-3 text-sm">
                <div className="min-w-0">
                  <div className="font-semibold text-[#2F3437]">{request.leave_type}</div>
                  <div className="text-xs text-gray-500">{formatDate(request.start_date)} - {formatDate(request.end_date)} • {request.total_days} day{request.total_days === 1 ? '' : 's'}</div>
                </div>
                <div className="text-gray-500">
                  {request.status === 'pending' ? `Pending with ${request.pending_with || reportingManager}` : request.reviewed_by ? `Reviewed by ${request.reviewed_by}` : 'Saved draft'}
                </div>
                <div className="truncate text-gray-500">{request.reason}</div>
                <div className="flex min-h-9 items-center justify-center">
                  <Badge variant={request.status === 'approved' ? 'success' : request.status === 'rejected' ? 'error' : request.status === 'pending' ? 'warning' : 'neutral'}>
                    {request.status}
                  </Badge>
                </div>
                <div className="flex min-h-9 items-center justify-center gap-2">
                  {request.status === 'draft' ? (
                    <>
                      <button
                        onClick={() => editLeaveDraft(request)}
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-olive/15 bg-olive/10 text-olive transition-colors hover:bg-olive hover:text-white"
                        title="Edit draft"
                        aria-label="Edit draft leave request"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        disabled={!!savingLeave}
                        onClick={() => deleteLeaveDraft(request)}
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#E5E7EB] bg-white text-gray-400 transition-colors hover:border-status-error/30 hover:bg-status-error/10 hover:text-status-error disabled:cursor-not-allowed disabled:opacity-50"
                        title="Delete draft"
                        aria-label="Delete draft leave request"
                      >
                        <Trash2 size={14} />
                      </button>
                    </>
                  ) : (
                    <span className="h-8 w-8" aria-hidden="true" />
                  )}
                </div>
              </div>
            ))}
          </div>
            </div>
          </div>
        )}
      </Card>
    </PageShell>
  );
}

export function LeaveApprovalsPage() {
  const { user } = useAuth();
  const [leaveApprovalRows, setLeaveApprovalRows] = useState<LeaveRequestItem[]>([]);
  const [timesheetApprovalRows, setTimesheetApprovalRows] = useState<TimesheetApprovalItem[]>([]);
  const [loadingApprovals, setLoadingApprovals] = useState(true);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewTimesheet, setReviewTimesheet] = useState<TimesheetApprovalItem | null>(null);
  const [reviewCompliance, setReviewCompliance] = useState<ComplianceReport | null>(null);
  const [reviewComplianceLoading, setReviewComplianceLoading] = useState(false);
  const [reviewComplianceOpen, setReviewComplianceOpen] = useState(false);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const loadApprovals = useCallback(async () => {
    if (!user) return;
    setLoadingApprovals(true);
    setApprovalError(null);
    try {
      const [leaveRes, timesheetRes] = await Promise.all([
        fetch(`${API_BASE}/leaves/approvals`, { headers }),
        fetch(`${API_BASE}/timesheets/approvals`, { headers }),
      ]);
      const leaveData = await leaveRes.json().catch(() => null);
      const timesheetData = await timesheetRes.json().catch(() => null);
      if (!leaveRes.ok) throw new Error(leaveData?.detail || 'Could not load leave approvals.');
      if (!timesheetRes.ok) throw new Error(timesheetData?.detail || 'Could not load timesheet approvals.');
      setLeaveApprovalRows(leaveData.approvals || []);
      setTimesheetApprovalRows(timesheetData.approvals || []);
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

  const decideLeave = async (requestId: string, decision: 'approve' | 'reject') => {
    const reviewerNotes = decision === 'reject' ? window.prompt('Add a rejection reason for the employee:') : null;
    if (decision === 'reject' && reviewerNotes === null) return;
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
    } catch (err) {
      setApprovalError(err instanceof Error ? err.message : `Could not ${decision} leave request.`);
    } finally {
      setReviewingId(null);
    }
  };

  const decideTimesheet = async (approval: TimesheetApprovalItem, decision: 'approve' | 'reject') => {
    const reviewerNotes = decision === 'reject' ? window.prompt('Add a rejection reason for the employee:') : null;
    if (decision === 'reject' && reviewerNotes === null) return;
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
    } catch (err) {
      setApprovalError(err instanceof Error ? err.message : `Could not ${decision} timesheet.`);
    } finally {
      setReviewingId(null);
    }
  };

  const totalApprovalRows = leaveApprovalRows.length + timesheetApprovalRows.length;
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
          <tbody className="divide-y divide-[#E5E7EB]">
            {loadingApprovals ? (
              <tr><td colSpan={5} className="px-5 py-8 text-center text-gray-500">Loading approvals...</td></tr>
            ) : totalApprovalRows === 0 ? (
              <tr><td colSpan={5} className="px-5 py-8 text-center text-gray-500">No pending approvals.</td></tr>
            ) : (
              <>
                {leaveApprovalRows.map((approval) => (
                  <tr key={`leave-${approval.id}`} className="text-[#2F3437]">
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
                        <Button size="sm" variant="ghost" disabled={reviewingId === approval.id} onClick={() => decideLeave(approval.id, 'reject')}>Reject</Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {timesheetApprovalRows.map((approval) => {
                  const approvalKey = `${approval.employee_id}-${approval.week_start}`;
                  return (
                    <tr key={`timesheet-${approvalKey}`} className="text-[#2F3437]">
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
        <div className="animate-modal-backdrop fixed inset-0 z-[120] flex items-center justify-center overflow-hidden bg-[#111827]/68 p-4 backdrop-blur-sm sm:p-6 lg:p-8">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="timesheet-review-title"
            className="animate-modal-pop relative flex max-h-[calc(100vh-2rem)] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-white/80 bg-[#FEFEFC] shadow-[0_32px_110px_rgba(0,0,0,0.42),0_10px_36px_rgba(17,24,39,0.22),0_0_0_1px_rgba(255,255,255,0.65)] ring-1 ring-black/10 sm:max-h-[calc(100vh-3rem)] lg:max-h-[calc(100vh-4rem)]"
          >
            <div className="h-1 shrink-0 bg-gradient-to-r from-olive via-sage to-status-info" />
            <div className="flex shrink-0 items-start justify-between gap-4 border-b border-[#DDE3EA] bg-white px-5 py-4 shadow-[0_1px_0_rgba(17,24,39,0.03)] sm:px-6">
              <div>
                <div id="timesheet-review-title" className="text-lg font-bold text-[#2F3437]">Timesheet Review</div>
                <div className="mt-1 text-sm text-gray-500">
                  {reviewTimesheet.employee_name} • {formatDate(reviewTimesheet.week_start)} - {formatDate(reviewTimesheet.week_end)}
                </div>
              </div>
              <button
                onClick={() => setReviewTimesheet(null)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-transparent text-gray-400 transition-colors hover:border-[#DDE3EA] hover:bg-hover-bg hover:text-[#2F3437]"
                title="Close"
              >
                <X size={17} />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto bg-[#F8F9F6] px-5 py-4 sm:px-6">
              <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
                {[
                  ['Logged', `${reviewTimesheet.total_hours}h`],
                  ['Working', `${reviewTimesheet.working_hours}h`],
                  ['Break', `${reviewTimesheet.break_hours}h`],
                  ['Leave', `${reviewTimesheet.leave_hours}h`],
                  ['Overtime', `${reviewTimesheet.overtime_hours}h`],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-[#E1E6DE] bg-white px-3 py-2.5 shadow-[0_1px_2px_rgba(17,24,39,0.04)]">
                    <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{label}</div>
                    <div className={cn('mt-1 text-lg font-bold text-[#2F3437]', label === 'Overtime' && reviewTimesheet.overtime_hours > 0 && 'text-status-warning')}>{value}</div>
                  </div>
                ))}
              </div>

              <div className="overflow-x-auto rounded-lg border border-[#DDE3EA] bg-white shadow-[0_8px_22px_rgba(17,24,39,0.06)]">
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
                  <tbody className="divide-y divide-[#E5E7EB] bg-white">
                    {reviewWeekDates.map((dateValue) => {
                      const dateKey = toDateInput(dateValue);
                      const leave = reviewLeaveForDate(dateKey);
                      const workHours = reviewEntriesForDate(dateKey)
                        .filter((entry) => entry.entry_code !== 'BRK')
                        .reduce((sum, entry) => sum + entry.hours, 0);
                      const breakHours = reviewEntryHours(dateKey, 'BRK');
                      return (
                        <tr key={dateKey}>
                          <td className="px-4 py-3 font-semibold text-[#2F3437]">
                            {dateValue.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                          </td>
                          <td className="px-4 py-3 font-bold">{workHours}h</td>
                          <td className="px-4 py-3">{breakHours}h</td>
                          <td className="px-4 py-3">
                            {leave ? <Badge variant={leave.status === 'approved' ? 'success' : 'warning'}>{leave.hours}h {leave.leave_type}</Badge> : '0h'}
                          </td>
                          <td className="px-4 py-3 text-gray-500">
                            {reviewEntriesForDate(dateKey).length === 0 ? (
                              <span>No time blocks</span>
                            ) : (
                              <div className="space-y-1">
                                {reviewEntriesForDate(dateKey).map((entry) => (
                                  <div key={entry.id}>
                                    <span className="font-semibold text-[#2F3437]">{entry.project_name}</span>
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

            <div className="flex shrink-0 justify-end gap-2 border-t border-[#DDE3EA] bg-white px-5 py-4 shadow-[0_-1px_0_rgba(17,24,39,0.02)] sm:px-6">
              <Button variant="ghost" disabled={reviewingId === `${reviewTimesheet.employee_id}-${reviewTimesheet.week_start}`} onClick={() => decideTimesheet(reviewTimesheet, 'reject')}>
                Reject
              </Button>
              <Button disabled={reviewingId === `${reviewTimesheet.employee_id}-${reviewTimesheet.week_start}`} onClick={() => decideTimesheet(reviewTimesheet, 'approve')}>
                Approve Timesheet
              </Button>
            </div>
          </div>
        </div>
      ), document.body)}
    </PageShell>
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

  const actualProjects = projects.filter((project) => project.id);
  const selectedWeekSubmitted = currentWeek?.status === 'submitted';
  const selectedWeekApproved = currentWeek?.status === 'approved';
  const selectedWeekRejected = currentWeek?.status === 'rejected';
  const selectedWeekLocked = selectedWeekSubmitted || selectedWeekApproved;
  const availableProjectOptions = useMemo(() => {
    const preferred = [
      ...actualProjects,
      ...projects.filter((project) => ['POC', 'BRK', 'TRN', 'MTG', 'ADM'].includes(project.code)),
    ];
    const unique = new Map<string, TimesheetProject>();
    preferred.forEach((project) => unique.set(project.id || project.code, project));
    return Array.from(unique.values());
  }, [actualProjects, projects]);
  const gridProjects = useMemo(
    () => selectedProjectKeys
      .map((key) => availableProjectOptions.find((project) => (project.id || project.code) === key))
      .filter(Boolean) as TimesheetProject[],
    [availableProjectOptions, selectedProjectKeys]
  );

  const loadTimesheet = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const [optionsRes, weekRes] = await Promise.all([
        fetch(`${API_BASE}/timesheets/me/options`, { headers }),
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
      const firstOption = (options.projects || []).find((project: TimesheetProject) => project.id) || (options.projects || [])[0];
      setTaskDraft((current) => ({
        ...current,
        projectKey: firstOption ? (firstOption.id || firstOption.code) : '',
        entryCode: firstOption?.id ? 'PRJ' : firstOption?.code || 'POC',
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
    ? projects.find((project) => project.id === activeCell.projectKey || project.code === activeCell.projectKey)
    : null;
  const leaveByDate = useMemo(() => {
    const map = new Map<string, TimesheetLeaveDay>();
    (currentWeek?.leave_days || []).forEach((item) => map.set(item.date, item));
    return map;
  }, [currentWeek?.leave_days]);
  const activeBlocks = activeCell
    ? rows.filter((row) => row.projectKey === activeCell.projectKey && row.workDate === activeCell.date)
    : [];

  const openCell = (project: TimesheetProject, date: string) => {
    if (isWeekendDate(date)) return;
    if (leaveByDate.has(date)) return;
    setActiveCell({ projectKey: project.id || project.code, date });
  };

  const addBlock = (project = selectedProject, date = activeCell?.date || weekStart) => {
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
    setRows((current) => [...current, makeTimesheetRow(project, code, date)]);
    setActiveCell({ projectKey: project.id || project.code, date });
  };

  const addProjectRow = () => {
    const project = availableProjectOptions.find((item) => (item.id || item.code) === taskDraft.projectKey);
    if (!project) return;
    const key = project.id || project.code;
    setSelectedProjectKeys((current) => current.includes(key) ? current : [...current, key]);
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    const firstOpenDate = weekDates
      .map(toDateInput)
      .find((dateKey) => dateKey >= taskDraft.startDate && dateKey <= taskDraft.endDate && !leaveByDate.has(dateKey) && !isWeekendDate(dateKey));
    if (!firstOpenDate) {
      setError('Select a weekday date range. Timesheets cannot be entered on Saturday or Sunday.');
      return;
    }
    setActiveCell({ projectKey: key, date: firstOpenDate });
    setTaskModalOpen(false);
  };

  const removeProjectRow = (project: TimesheetProject) => {
    const key = project.id || project.code;
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    setSelectedProjectKeys((current) => current.filter((item) => item !== key));
    setRows((current) => current.filter((row) => row.projectKey !== key));
    setActiveCell((current) => current?.projectKey === key ? null : current);
  };

  const updateBlock = (rowId: string, updates: Partial<TimesheetRow>) => {
    setSubmitCompliance(null);
    setComplianceCheckMessage(null);
    setRows((current) => current.map((row) => row.id === rowId ? { ...row, ...updates } : row));
  };

  const cellTotal = (project: TimesheetProject, date: string) => rows
    .filter((row) => !leaveByDate.has(row.workDate))
    .filter((row) => row.projectKey === (project.id || project.code) && row.workDate === date)
    .reduce((sum, row) => sum + timeBlockHours(row), 0);

  const dayTotal = (date: string) => rows
    .filter((row) => !leaveByDate.has(row.workDate))
    .filter((row) => row.workDate === date)
    .reduce((sum, row) => sum + timeBlockHours(row), 0);

  const projectTotal = (project: TimesheetProject) => rows
    .filter((row) => !leaveByDate.has(row.workDate))
    .filter((row) => row.projectKey === (project.id || project.code))
    .reduce((sum, row) => sum + timeBlockHours(row), 0);

  const buildPayload = () => ({
    week_start: weekStart,
    time_zone: timeZone,
    entries: rows.flatMap((row) => {
      if (isWeekendDate(row.workDate)) return [];
      if (leaveByDate.has(row.workDate)) return [];
      const project = projects.find((item) => item.id === row.projectKey || item.code === row.projectKey);
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

  const summaryItems = [
    { label: 'Logged', value: `${rows.filter((row) => !leaveByDate.has(row.workDate)).reduce((sum, row) => sum + timeBlockHours(row), 0)}h` },
    { label: 'Working', value: `${currentWeek?.working_hours || 0}h` },
    { label: 'Break', value: `${currentWeek?.break_hours || 0}h` },
    { label: 'Leave', value: `${currentWeek?.leave_hours || 0}h` },
    { label: 'Overtime', value: `${currentWeek?.overtime_hours || 0}h`, warning: !!currentWeek?.overtime_hours },
  ];

  return (
    <PageShell title="Timesheets" description="Fill weekly project hours and submit them for approval.">
      {error && (
        <div className="mb-5 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-5 rounded-lg border border-status-success/20 bg-status-success/10 px-4 py-3 text-sm text-status-success">
          {success}
        </div>
      )}
      {complianceCheckMessage && (
        <div className="mb-5 rounded-lg border border-status-warning/20 bg-status-warning/10 px-4 py-3 text-sm text-status-warning">
          {complianceCheckMessage}
        </div>
      )}
      {submitCompliance && (
        <div className="mb-5">
          <AllocationCompliancePanel
            report={submitCompliance}
            open={submitComplianceOpen}
            onToggle={() => setSubmitComplianceOpen((current) => !current)}
            action={(
              <>
                <Button
                  variant="ghost"
                  disabled={!!saving}
                  onClick={() => {
                    setSubmitCompliance(null);
                    setSuccess('Review your time blocks, then submit again when ready.');
                  }}
                >
                  Go Back and Review
                </Button>
                <Button disabled={!!saving} onClick={submitAfterComplianceWarning} icon={<CheckCircle2 size={15} />}>
                  {saving === 'submit' ? 'Submitting' : 'Submit Anyway'}
                </Button>
              </>
            )}
          />
        </div>
      )}
      {!!currentWeek?.warnings?.length && !selectedWeekApproved && (
        <div className="mb-5 rounded-lg border border-status-warning/20 bg-status-warning/10 px-4 py-3 text-sm text-status-warning">
          {currentWeek.warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      )}
      {!requiresTimesheet && (
        <div className="mb-5 rounded-lg border border-status-warning/20 bg-status-warning/10 px-4 py-3 text-sm text-status-warning">
          Timesheet submission may not be required for your workforce type. You can still save hours if your manager asks for it.
        </div>
      )}
      {selectedWeekSubmitted && (
        <div className="mb-5 rounded-lg border border-[#E5E7EB] bg-white px-4 py-3 text-sm text-gray-500">
          This timesheet is submitted to {currentWeek?.submitted_to || 'your manager'} and awaiting approval. Recall the submission if you need to make changes.
        </div>
      )}
      {selectedWeekApproved && (
        <div className="mb-5 rounded-lg border border-status-success/20 bg-status-success/10 px-4 py-3 text-sm text-status-success">
          This timesheet was approved{currentWeek?.reviewed_by ? ` by ${currentWeek.reviewed_by}` : ''}{currentWeek?.reviewed_at ? ` on ${formatDateTime(currentWeek.reviewed_at)}` : ''}. {currentWeek?.overtime_hours ? `${currentWeek.overtime_hours}h overtime is approved with this timesheet. ` : ''}It is now locked.
        </div>
      )}
      {selectedWeekRejected && (
        <div className="mb-5 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          This timesheet was rejected{currentWeek?.reviewed_by ? ` by ${currentWeek.reviewed_by}` : ''}. {currentWeek?.reviewer_notes || 'Update the entries and submit it again.'}
        </div>
      )}

      {taskModalOpen && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/35 px-4">
          <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-[#E5E7EB] bg-warm-card shadow-card-lg">
            <div className="flex items-center justify-between border-b border-[#E5E7EB] px-6 py-4">
              <div>
                <div className="text-lg font-bold text-[#2F3437]">Add Task</div>
                <div className="text-xs text-gray-500">Create a work item for this week. Hours are saved only after Save Draft or Submit.</div>
              </div>
              <button
                onClick={() => setTaskModalOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 hover:bg-hover-bg hover:text-[#2F3437]"
                title="Close"
              >
                <X size={17} />
              </button>
            </div>
            <div className="grid gap-5 px-6 py-5 md:grid-cols-2">
              <label className="space-y-1.5 md:col-span-2">
                <span className="text-xs font-semibold text-gray-500">Work Item</span>
                <select
                  value={taskDraft.projectKey}
                  onChange={(event) => {
                    const selected = availableProjectOptions.find((item) => (item.id || item.code) === event.target.value);
                    setTaskDraft((current) => ({
                      ...current,
                      projectKey: event.target.value,
                      entryCode: selected?.id ? 'PRJ' : selected?.code || current.entryCode,
                    }));
                  }}
                  className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2.5 text-sm font-semibold outline-none focus:border-olive"
                >
                  {availableProjectOptions.map((project) => (
                    <option key={project.id || project.code} value={project.id || project.code}>
                      {project.name} ({project.code})
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-semibold text-gray-500">Activity Code</span>
                <select
                  value={taskDraft.entryCode}
                  onChange={(event) => {
                    const generic = availableProjectOptions.find((item) => item.code === event.target.value && !item.id);
                    setTaskDraft((current) => ({
                      ...current,
                      entryCode: event.target.value,
                      projectKey: event.target.value === 'PRJ' ? current.projectKey : generic?.code || current.projectKey,
                    }));
                  }}
                  className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2.5 text-sm font-semibold outline-none focus:border-olive"
                >
                  {codes.map((code) => <option key={code.code} value={code.code}>{code.code} - {code.label}</option>)}
                </select>
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-semibold text-gray-500">Date Range</span>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="date"
                    value={taskDraft.startDate}
                    onChange={(event) => setTaskDraft((current) => ({ ...current, startDate: event.target.value }))}
                    className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2.5 text-sm outline-none focus:border-olive"
                  />
                  <input
                    type="date"
                    value={taskDraft.endDate}
                    onChange={(event) => setTaskDraft((current) => ({ ...current, endDate: event.target.value }))}
                    className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2.5 text-sm outline-none focus:border-olive"
                  />
                </div>
              </label>

              <label className="space-y-1.5 md:col-span-2">
                <span className="text-xs font-semibold text-gray-500">Description</span>
                <textarea
                  value={taskDraft.description}
                  onChange={(event) => setTaskDraft((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Example: Coding and self unit testing"
                  rows={3}
                  className="w-full resize-none rounded-lg border border-[#E5E7EB] bg-white px-3 py-2.5 text-sm outline-none focus:border-olive"
                />
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-[#E5E7EB] px-6 py-4">
              <Button variant="ghost" onClick={() => setTaskModalOpen(false)}>Cancel</Button>
              <Button disabled={!taskDraft.projectKey} icon={<Plus size={15} />} onClick={addProjectRow}>Add Task</Button>
            </div>
          </div>
        </div>
      )}

      <Card className="mb-5 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm font-bold text-[#2F3437]">Week of {weekLabel(weekStart)}</div>
            <div className="mt-1 text-xs text-gray-500">Local timezone: {timeZone}</div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex h-9 items-center gap-2 rounded-btn border border-[#E5E7EB] bg-white px-3">
              <span className="text-[12px] font-bold uppercase tracking-wide text-gray-400">Week</span>
              <input
                type="date"
                value={weekStart}
                onChange={(event) => jumpToWeek(event.target.value)}
                className="bg-transparent text-[13px] font-semibold text-[#2F3437] outline-none"
              />
            </label>
            <Button variant="soft" onClick={() => setWeekStart(toDateInput(startOfLocalWeek()))}>This Week</Button>
            <Button variant="soft" icon={<RefreshCw size={15} />} disabled={!!saving || selectedWeekLocked} onClick={copyPreviousWeek}>
              Copy Previous
            </Button>
            <Button variant="ghost" icon={<Trash2 size={15} />} disabled={!!saving || selectedWeekLocked} onClick={deleteTimesheet}>
              Reset Week
            </Button>
          </div>
        </div>
      </Card>

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
        {summaryItems.map((item) => (
          <Card key={item.label} className="p-4">
            <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{item.label}</div>
            <div className={cn('mt-1 text-xl font-bold', item.warning ? 'text-status-warning' : 'text-[#2F3437]')}>{item.value}</div>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        {gridProjects.length > 0 && !selectedWeekLocked && (
          <div className="flex justify-end border-b border-[#E5E7EB] px-5 py-3">
            <Button size="sm" variant="ghost" icon={<Plus size={14} />} disabled={availableProjectOptions.length === 0} onClick={() => setTaskModalOpen(true)}>
              Add Another Task
            </Button>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1040px] text-left text-sm">
            <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
              <tr>
                <th className="px-5 py-3 font-bold">Work Item</th>
                {weekDates.map((dateValue) => {
                  const isWeekend = isWeekendDate(dateValue);
                  return (
                    <th
                      key={dateValue.toISOString()}
                      className={cn('px-3 py-3 text-center font-bold', isWeekend && 'bg-gray-100 text-gray-400')}
                    >
                      {dateValue.toLocaleDateString('en-US', { weekday: 'short' })}
                      <div className={cn('font-semibold normal-case text-gray-400', isWeekend && 'text-gray-300')}>
                        {dateValue.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </div>
                    </th>
                  );
                })}
                <th className="px-4 py-3 text-center font-bold">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              {loading ? (
                <tr><td colSpan={9} className="px-5 py-8 text-center text-gray-500">Loading timesheet...</td></tr>
              ) : gridProjects.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-5 py-10 text-center">
                    <div className="text-sm font-bold text-[#2F3437]">Start by adding a work item</div>
                    <div className="mx-auto mt-1 max-w-md text-sm text-gray-500">
                      Choose a project, POC, break, training, or meeting item. Then click a day cell to add exact start and end times.
                    </div>
                    <Button className="mt-5" icon={<Plus size={15} />} disabled={selectedWeekLocked || availableProjectOptions.length === 0} onClick={() => setTaskModalOpen(true)}>
                      Add Task
                    </Button>
                  </td>
                </tr>
              ) : gridProjects.map((project) => (
                <tr key={project.id || project.code}>
                  <td className="px-5 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate font-semibold text-[#2F3437]">{project.name}</div>
                        <div className="text-xs text-gray-400">{project.code}</div>
                      </div>
                      <button
                        disabled={selectedWeekLocked}
                        onClick={() => removeProjectRow(project)}
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-hover-bg hover:text-status-error disabled:opacity-40"
                        title="Remove row"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                  {weekDates.map((dateValue) => {
                    const dateKey = toDateInput(dateValue);
                    const total = cellTotal(project, dateKey);
                    const leave = leaveByDate.get(dateKey);
                    const isActive = activeCell?.projectKey === (project.id || project.code) && activeCell.date === dateKey;
                    const isWeekend = isWeekendDate(dateValue);
                    return (
                      <td key={dateKey} className={cn('px-3 py-3', isWeekend && 'bg-gray-50')}>
                        <button
                          disabled={selectedWeekLocked || !!leave || isWeekend}
                          onClick={() => openCell(project, dateKey)}
                          title={isWeekend ? 'Weekend entries are not allowed' : undefined}
                          className={cn(
                            'relative flex h-14 w-full flex-col items-center justify-center rounded-lg border px-2 text-center text-sm font-bold leading-tight transition-all',
                            leave && 'h-16 text-xs',
                            isWeekend
                              ? 'cursor-not-allowed border-[#E5E7EB] bg-gray-50 text-gray-300'
                              : leave
                              ? 'cursor-not-allowed border-status-warning/20 bg-status-warning/10 text-status-warning'
                              : isActive
                              ? 'border-olive bg-olive/10 text-olive ring-2 ring-olive/10'
                              : total > 0
                                ? 'border-olive/20 bg-olive/5 text-[#2F3437] hover:border-olive/50'
                                : 'border-[#E5E7EB] bg-white text-gray-300 hover:border-olive/30 hover:text-olive',
                            isWeekend && !leave && total === 0 && !isActive && 'bg-gray-50 text-gray-300 hover:bg-white'
                          )}
                        >
                          {isWeekend && total === 0 ? 'Weekend' : leave ? `${leave.status === 'approved' ? 'Approved' : 'Pending'} Leave` : total > 0 ? `${total}h` : '0h'}
                          {leave && <div className="mt-0.5 whitespace-nowrap text-[10px] font-semibold leading-tight">{leave.hours}h {leave.leave_type}</div>}
                          {!leave && total > 0 && <div className="mt-0.5 text-[10px] font-semibold text-gray-400">{rows.filter((row) => row.projectKey === (project.id || project.code) && row.workDate === dateKey).length} block{rows.filter((row) => row.projectKey === (project.id || project.code) && row.workDate === dateKey).length === 1 ? '' : 's'}</div>}
                        </button>
                      </td>
                    );
                  })}
                  <td className="px-4 py-3 text-center font-bold text-[#2F3437]">{projectTotal(project)}h</td>
                </tr>
              ))}
              {!loading && (
                <tr className="bg-warm-bg/80">
                  <td className="px-5 py-4 text-xs font-bold uppercase tracking-wide text-gray-400">Daily Total</td>
                  {weekDates.map((dateValue) => {
                    const dateKey = toDateInput(dateValue);
                    const isWeekend = isWeekendDate(dateValue);
                    const leave = leaveByDate.get(dateKey);
                    const workedHours = dayTotal(dateKey);
                    return (
                      <td key={dateKey} className={cn('px-3 py-4 text-center text-sm font-bold text-[#2F3437]', isWeekend && 'bg-gray-100 text-gray-400')}>
                        {leave ? (
                          <div className="leading-tight">
                            <div className="text-status-warning">{leave.hours}h leave</div>
                            <div className="mt-0.5 text-[10px] font-semibold text-gray-400">{workedHours}h work</div>
                          </div>
                        ) : `${workedHours}h`}
                      </td>
                    );
                  })}
                  <td className="px-4 py-4 text-center text-sm font-bold text-olive">{rows.filter((row) => !leaveByDate.has(row.workDate)).reduce((sum, row) => sum + timeBlockHours(row), 0)}h</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {activeCell && selectedProject && !selectedWeekLocked && (
        <Card className="mt-5 overflow-hidden">
          <CardHeader
            title={`${selectedProject.name} - ${formatDate(activeCell.date)}`}
            icon={<Clock3 size={17} />}
            action={<Button size="sm" icon={<Plus size={14} />} onClick={() => addBlock()}>Add Time Block</Button>}
          />
          <div className="divide-y divide-[#E5E7EB]">
            {activeBlocks.length === 0 ? (
              <div className="px-5 py-8 text-center text-sm text-gray-500">No time blocks yet. Add one to start logging time.</div>
            ) : activeBlocks.map((block) => (
              <div key={block.id} className="grid grid-cols-1 gap-3 px-5 py-4 lg:grid-cols-[110px_130px_130px_minmax(180px,1fr)_48px] lg:items-center">
                <select
                  value={block.entryCode}
                  onChange={(event) => updateBlock(block.id, { entryCode: event.target.value })}
                  className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm font-semibold outline-none focus:border-olive"
                >
                  {codes.map((code) => <option key={code.code} value={code.code}>{code.code}</option>)}
                </select>
                <input
                  value={block.startTime}
                  onChange={(event) => updateBlock(block.id, { startTime: event.target.value })}
                  type="time"
                  className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                />
                <input
                  value={block.endTime}
                  onChange={(event) => updateBlock(block.id, { endTime: event.target.value })}
                  type="time"
                  className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                />
                <input
                  value={block.notes}
                  onChange={(event) => updateBlock(block.id, { notes: event.target.value })}
                  placeholder={`${timeBlockHours(block)}h calculated - optional note`}
                  className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                />
                <button
                  onClick={() => {
                    setSubmitCompliance(null);
                    setComplianceCheckMessage(null);
                    setRows((current) => current.filter((item) => item.id !== block.id));
                  }}
                  className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-hover-bg hover:text-status-error"
                  title="Remove block"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-gray-500">
          Logged: <span className="font-bold text-[#2F3437]">{rows.filter((row) => !leaveByDate.has(row.workDate)).reduce((sum, row) => sum + timeBlockHours(row), 0)}h</span>
          {currentWeek && <span className="ml-3">Working: <span className="font-bold text-[#2F3437]">{currentWeek.working_hours}h</span></span>}
          {currentWeek && <span className="ml-3">Break: <span className="font-bold text-[#2F3437]">{currentWeek.break_hours}h</span></span>}
          {currentWeek && <span className="ml-3">Leave: <span className="font-bold text-[#2F3437]">{currentWeek.leave_hours}h</span></span>}
          {currentWeek && <span className="ml-3">Regular: <span className="font-bold text-[#2F3437]">{currentWeek.regular_hours}h</span></span>}
          {!!currentWeek?.overtime_hours && <span className="ml-3">Overtime: <span className="font-bold text-status-warning">{currentWeek.overtime_hours}h</span></span>}
          {currentWeek?.submitted_to && currentWeek.status === 'submitted' && (
            <span className="ml-3">Sent to: <span className="font-bold text-[#2F3437]">{currentWeek.submitted_to}</span></span>
          )}
          {currentWeek?.reviewed_by && ['approved', 'rejected'].includes(currentWeek.status) && (
            <span className="ml-3">Reviewed by: <span className="font-bold text-[#2F3437]">{currentWeek.reviewed_by}</span></span>
          )}
          {currentWeek?.status && (
            <span className="ml-3">Status: <Badge variant={currentWeek.status === 'approved' ? 'success' : currentWeek.status === 'submitted' ? 'warning' : currentWeek.status === 'rejected' ? 'error' : 'neutral'}>
              {currentWeek.status.replace('_', ' ')}
            </Badge></span>
          )}
        </div>
        <div className="flex gap-2">
          {selectedWeekSubmitted ? (
            <Button variant="ghost" disabled={!!saving} onClick={recallTimesheet} icon={<RefreshCw size={15} />}>
              {saving === 'draft' ? 'Recalling' : 'Recall Submission'}
            </Button>
          ) : selectedWeekApproved ? (
            <Badge variant="success">approved</Badge>
          ) : (
            <>
              <Button variant="ghost" disabled={!!saving || !hasTimeBlocks} onClick={() => saveTimesheet('draft')}>Save Draft</Button>
              <Button disabled={!!saving || !hasTimeBlocks} onClick={() => saveTimesheet('submit')} icon={<CheckCircle2 size={15} />}>
                {saving === 'submit' ? 'Submitting' : 'Submit Timesheet'}
              </Button>
            </>
          )}
        </div>
      </div>
    </PageShell>
  );
}

export function CheckInOutPage() {
  const { today, history, loading, actionLoading, error, checkIn, checkOut } = useAttendance();
  const [clockNow, setClockNow] = useState(new Date());
  const isCheckedIn = !!today?.is_checked_in;
  const isCheckedOut = !!today?.check_out;
  const canCheckInToday = !loading && !isCheckedIn && !isCheckedOut;
  const sessionHours = isCheckedIn ? formatElapsed(today?.check_in, clockNow) : formatHours(today?.total_hours ?? null);
  const statusLabel = loading
    ? 'Loading attendance'
    : isCheckedIn
      ? 'Currently checked in'
      : isCheckedOut
        ? 'Checked out for today'
        : 'Ready to check in';
  const statusDescription = isCheckedIn
    ? 'Your work session is active. Check out when you are done for the day.'
    : isCheckedOut
      ? 'You have completed today’s attendance. A new check-in will be available tomorrow.'
      : 'Start your day by checking in. Your working time starts from that moment.';
  const recentAttendance = history.filter((item) => item.date !== today?.date).slice(0, 3);

  useEffect(() => {
    if (!isCheckedIn) return;
    const intervalId = window.setInterval(() => setClockNow(new Date()), 30000);
    return () => window.clearInterval(intervalId);
  }, [isCheckedIn]);

  return (
    <PageShell title="Check In / Out" description="Track today's attendance and break time.">
      {error && (
        <div className="mb-5 max-w-3xl rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}
      <div className="grid max-w-6xl gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <Card className="relative overflow-hidden p-6 sm:p-7">
          <div className="absolute right-6 top-6 h-24 w-24 rounded-full bg-olive/10 blur-2xl" />
          <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                {isCheckedIn && <span className="absolute inset-0 rounded-2xl bg-olive/20 animate-ping" />}
                <div className={cn(
                  'relative flex h-20 w-20 items-center justify-center rounded-2xl border text-olive',
                  isCheckedIn ? 'border-olive/20 bg-olive/10' : isCheckedOut ? 'border-[#E5E7EB] bg-hover-bg text-olive-dark' : 'border-[#E5E7EB] bg-white'
                )}>
                  {isCheckedOut ? <CheckCircle2 size={34} /> : <Clock3 size={34} />}
                </div>
              </div>
              <div>
                <div className="text-sm font-bold uppercase tracking-wide text-gray-400">{statusLabel}</div>
                <div className="mt-1 text-5xl font-bold tracking-tight text-[#2F3437]">{loading ? '...' : sessionHours}</div>
                <div className="mt-2 max-w-xl text-sm text-gray-500">{statusDescription}</div>
              </div>
            </div>

            <div className="flex shrink-0 flex-wrap gap-2 lg:flex-col">
              {isCheckedIn ? (
                <Button onClick={checkOut} disabled={!!actionLoading} icon={<LogIn size={15} />}>
                  {actionLoading === 'check-out' ? 'Checking Out' : 'Check Out'}
                </Button>
              ) : (
                <Button onClick={checkIn} disabled={!!actionLoading || !canCheckInToday} icon={<LogIn size={15} />}>
                  {actionLoading === 'check-in' ? 'Checking In' : 'Check In'}
                </Button>
              )}
              <Button variant="ghost" disabled>Breaks coming soon</Button>
            </div>
          </div>

          <div className="relative mt-7 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-[#E5E7EB] bg-white px-4 py-3">
              <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Check In</div>
              <div className="mt-1 text-lg font-bold text-[#2F3437]">{formatTime(today?.check_in)}</div>
            </div>
            <div className="rounded-lg border border-[#E5E7EB] bg-white px-4 py-3">
              <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Check Out</div>
              <div className="mt-1 text-lg font-bold text-[#2F3437]">{today?.check_out ? formatTime(today.check_out) : isCheckedIn ? 'In progress' : 'Not recorded'}</div>
            </div>
            <div className="rounded-lg border border-[#E5E7EB] bg-white px-4 py-3">
              <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Status</div>
              <div className="mt-1"><Badge variant={isCheckedIn ? 'success' : isCheckedOut ? 'neutral' : 'warning'}>{today?.status?.replace(/_/g, ' ') || 'not checked in'}</Badge></div>
            </div>
          </div>

          {isCheckedOut && (
            <div className="relative mt-4 rounded-lg border border-olive/15 bg-olive/5 px-4 py-3 text-sm text-olive-dark">
              You cannot check in again after checking out for the day. This prevents duplicate attendance sessions for the same date.
            </div>
          )}
        </Card>

        <div className="grid gap-5">
          <Card className="p-5">
            <CardHeader title="Today Timeline" icon={<CalendarClock size={17} />} />
            <div className="mt-4 space-y-4">
              {[
                { label: 'Checked in', value: formatTime(today?.check_in), active: !!today?.check_in },
                { label: 'Checked out', value: today?.check_out ? formatTime(today.check_out) : isCheckedIn ? 'Waiting' : 'Not recorded', active: !!today?.check_out },
              ].map((item, index) => (
                <div key={item.label} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <div className={cn('h-3 w-3 rounded-full', item.active ? 'bg-olive' : 'bg-[#DDE3EA]')} />
                    {index === 0 && <div className="mt-1 h-10 w-px bg-[#E5E7EB]" />}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-[#2F3437]">{item.label}</div>
                    <div className="text-sm text-gray-500">{item.value}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <CardHeader title="Recent Days" icon={<CalendarCheck size={17} />} />
            <div className="mt-3 divide-y divide-[#E5E7EB]">
              {recentAttendance.length ? recentAttendance.map((item) => (
                <div key={item.id || item.date} className="flex items-center justify-between gap-3 py-3 text-sm">
                  <div>
                    <div className="font-semibold text-[#2F3437]">{formatDate(item.date)}</div>
                    <div className="text-xs text-gray-500">{formatTime(item.check_in)} - {item.check_out ? formatTime(item.check_out) : 'In progress'}</div>
                  </div>
                  <div className="font-bold text-[#2F3437]">{formatHours(item.total_hours)}</div>
                </div>
              )) : (
                <div className="py-6 text-sm text-gray-500">No recent attendance yet.</div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </PageShell>
  );
}

export function AttendanceHistoryPage() {
  const { history, loading, error } = useAttendance();
  const rows = history.length
    ? history.map((row) => ({
      date: formatDate(row.date),
      checkIn: formatTime(row.check_in),
      checkOut: row.check_out ? formatTime(row.check_out) : row.is_checked_in ? 'In progress' : 'Not recorded',
      hours: formatHours(row.total_hours),
      status: row.status.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
    }))
    : attendanceRows;

  return (
    <PageShell title="Attendance History" description="Review daily check-ins, check-outs, and status.">
      {error && (
        <div className="mb-5 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}
      {loading && <div className="mb-4 text-sm text-gray-500">Loading attendance history...</div>}
      <SimpleTable
        headers={['Date', 'Check In', 'Check Out', 'Hours', 'Status']}
        rows={rows.map((row) => [
          <span className="font-semibold">{row.date}</span>,
          row.checkIn,
          row.checkOut,
          row.hours,
          <Badge variant={row.status === 'Late' ? 'warning' : 'success'}>{row.status}</Badge>,
        ])}
      />
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
            <div className="text-sm font-bold text-[#2F3437]">{request}</div>
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
  return (
    <PageShell title="Company Handbook" description="View company policies, guidelines, and employee resources.">
      <Card className="flex min-h-[360px] items-center justify-center p-8">
        <div className="max-w-md text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-olive/10 text-olive">
            <BookOpen size={26} />
          </div>
          <h2 className="text-lg font-bold text-[#2F3437]">Company Handbook Coming Soon</h2>
          <p className="mt-2 text-sm leading-6 text-gray-500">
            Policies, guidelines, and employee resources will be available here.
          </p>
        </div>
      </Card>
    </PageShell>
  );
}

export function HolidaysPage() {
  return (
    <PageShell title="Holidays" description="View company holidays and optional holiday options.">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[
          ['Independence Day', 'Jul 4, 2026', 'Company Holiday'],
          ['Labor Day', 'Sep 7, 2026', 'Company Holiday'],
          ['Optional Holiday', 'Use anytime', '1 available'],
        ].map(([name, date, type]) => (
          <Card key={name} className="p-5">
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-olive/10 text-olive">
              <CalendarCheck size={18} />
            </div>
            <div className="text-sm font-bold text-[#2F3437]">{name}</div>
            <div className="mt-1 text-xs text-gray-500">{date}</div>
            <div className="mt-4"><Badge variant="info">{type}</Badge></div>
          </Card>
        ))}
      </div>
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
            <div className="text-sm font-bold text-[#2F3437]">No notifications yet</div>
            <div className="mt-1 text-xs text-gray-500">Approval updates and HR alerts will appear here.</div>
          </div>
        ) : (
          <div className="divide-y divide-[#E5E7EB]">
            {items.map((item) => (
              <div key={item.id} className={cn('grid gap-3 px-5 py-4 md:grid-cols-[1fr_150px_120px]', !item.is_read && 'bg-olive/5')}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="truncate text-sm font-bold text-[#2F3437]">{item.title}</div>
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

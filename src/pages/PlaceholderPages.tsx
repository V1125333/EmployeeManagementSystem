import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import {
  AlertTriangle, BarChart3, BriefcaseBusiness, Building2, CalendarCheck, CalendarClock, CheckCircle2, Clock3,
  ChevronLeft, ChevronRight, Download, FileText, Pencil, Plus, RefreshCw, Search, ShieldCheck,
  Trash2, UserCheck, Users, UserX, X,
} from 'lucide-react';
import { Avatar, Badge, Button, Card, CardHeader } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

interface PlaceholderProps {
  title: string;
  description: string;
}

function PlaceholderPage({ title, description }: PlaceholderProps) {
  return (
    <div className="animate-fade-up">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-[var(--color-brand-navy)] tracking-tight mb-1">
          {title}
        </h1>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
      <Card className="flex items-center justify-center py-32">
        <div className="text-center">
          <div className="text-4xl mb-3">🚀</div>
          <div className="text-lg font-semibold text-[var(--color-brand-navy)] mb-1">
            Coming Soon
          </div>
          <div className="text-sm text-gray-500">
            This page is under development
          </div>
        </div>
      </Card>
    </div>
  );
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface AdminEmployeeOption { id: string; name: string; email: string; department: string; role: string }
interface OverviewCounts {
  pending_leave_requests: number;
  today_present: number;
  absent: number;
  late_arrivals: number;
  wfh: number;
  checked_out: number;
  pending_attendance_corrections: number;
  pending_timesheet_approvals: number;
}
interface LeaveRequestRow { id: string; employee_name: string; leave_type: string; start_date: string; end_date: string; total_days: number; reason?: string | null; status: string; reviewed_by?: string | null }
interface LeaveBalanceRow { id: string; employee_id: string; employee_name: string; leave_type: string; year: number; total_days: number; used_days: number; pending_days: number; available_days: number; carry_forward_days: number; updated_by?: string | null; updated_at?: string | null }
interface AttendanceRow { id: string; employee_id: string; employee_name: string; date: string; check_in?: string | null; check_out?: string | null; total_hours: number; status: string; source: string; remarks?: string | null }
interface CorrectionRow { id: string; employee_name: string; attendance_date?: string | null; original_check_in?: string | null; original_check_out?: string | null; requested_check_in?: string | null; requested_check_out?: string | null; reason: string; status: string }
interface TimesheetAdminRow { employee_id: string; employee_name: string; week_start: string; week_end: string; status: string; working_hours: number; break_hours: number; total_hours: number; overtime_hours: number; submitted_at?: string | null; entries: Array<{ date: string; code: string; project: string; start_time?: string | null; end_time?: string | null; hours: number; notes?: string | null }> }
interface PolicyRow { id: string; name: string; code: string; default_days: number; paid: boolean; carry_forward: boolean; max_carry_forward: number; active: boolean }
interface AttendancePolicyRow { name: string; value: string }
interface TimeOffData {
  overview: OverviewCounts;
  employees: AdminEmployeeOption[];
  leave_requests: LeaveRequestRow[];
  leave_balances: LeaveBalanceRow[];
  attendance_logs: AttendanceRow[];
  corrections: CorrectionRow[];
  timesheets: TimesheetAdminRow[];
  policies: PolicyRow[];
  attendance_policies: AttendancePolicyRow[];
}

interface EmployeeBalanceGroup {
  employee_id: string;
  employee_name: string;
  department: string;
  balances: LeaveBalanceRow[];
  total_available: number;
}

const timeOffTabs = [
  { key: 'overview', label: 'Overview' },
  { key: 'leave', label: 'Leave Requests' },
  { key: 'balances', label: 'Leave Balances' },
  { key: 'attendance', label: 'Attendance Logs' },
  { key: 'corrections', label: 'Corrections' },
  { key: 'timesheets', label: 'Timesheets' },
  { key: 'reports', label: 'Reports' },
  { key: 'policies', label: 'Policies' },
];

function metricCards(overview?: OverviewCounts) {
  const o = overview || {
    pending_leave_requests: 0, today_present: 0, absent: 0, late_arrivals: 0, wfh: 0, checked_out: 0,
    pending_attendance_corrections: 0, pending_timesheet_approvals: 0,
  };
  return [
    { label: 'Pending Leave Requests', value: o.pending_leave_requests, meta: 'needs review', icon: <CalendarClock size={18} /> },
    { label: 'Today Present', value: o.today_present, meta: 'today', icon: <UserCheck size={18} /> },
    { label: 'Absent', value: o.absent, meta: 'today', icon: <UserX size={18} /> },
    { label: 'Late Arrivals', value: o.late_arrivals, meta: 'today', icon: <Clock3 size={18} /> },
    { label: 'WFH', value: o.wfh, meta: 'today', icon: <ShieldCheck size={18} /> },
    { label: 'Checked Out', value: o.checked_out, meta: 'today', icon: <CheckCircle2 size={18} /> },
    { label: 'Pending Attendance Corrections', value: o.pending_attendance_corrections, meta: 'needs review', icon: <Pencil size={18} /> },
    { label: 'Pending Timesheet Approvals', value: o.pending_timesheet_approvals, meta: 'needs review', icon: <FileText size={18} /> },
  ];
}

function formatDate(value?: string | null) {
  return value ? new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '-';
}

function formatDateTime(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function localDateInput(value = new Date()) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function statusVariant(status?: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'olive' {
  if (status === 'approved' || status === 'present' || status === 'checked_out') return 'success';
  if (status === 'pending' || status === 'submitted' || status === 'late') return 'warning';
  if (status === 'rejected' || status === 'absent') return 'error';
  if (status === 'wfh') return 'info';
  return 'neutral';
}

function formatBalanceNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function compactLeaveName(value: string) {
  return value.replace(/\s+Leave$/i, '');
}

function buildBalanceGroups(rows: LeaveBalanceRow[], employees: AdminEmployeeOption[]): EmployeeBalanceGroup[] {
  const employeesById = new Map(employees.map((employee) => [employee.id, employee]));
  const groups = new Map<string, EmployeeBalanceGroup>();

  rows.forEach((row) => {
    const employee = employeesById.get(row.employee_id);
    const groupKey = row.employee_id || row.employee_name;
    if (!groups.has(groupKey)) {
      groups.set(groupKey, {
        employee_id: groupKey,
        employee_name: employee?.name || row.employee_name,
        department: employee?.department || 'Unassigned',
        balances: [],
        total_available: 0,
      });
    }
    const group = groups.get(groupKey);
    if (!group) return;
    group.balances.push(row);
    group.total_available += Number(row.available_days || 0);
  });

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      balances: group.balances.sort((a, b) => a.leave_type.localeCompare(b.leave_type)),
    }))
    .sort((a, b) => a.employee_name.localeCompare(b.employee_name));
}

function EmptyState({ message }: { message: string }) {
  return <div className="px-5 py-8 text-center text-sm text-gray-500">{message}</div>;
}

function ActionButtons({ onApprove, onReject, disabled }: { onApprove: () => void; onReject: () => void; disabled?: boolean }) {
  return (
    <div className="flex justify-end gap-2">
      <Button size="sm" variant="soft" disabled={disabled} onClick={onApprove}>Approve</Button>
      <Button size="sm" variant="ghost" disabled={disabled} onClick={onReject}>Reject</Button>
    </div>
  );
}

interface PendingDecision {
  url: string;
  decision: 'approve' | 'reject';
  label: string;
}

function OverviewSection({ data, onOpenQueue }: { data: TimeOffData; onOpenQueue: (label: string) => void }) {
  const recent = data.leave_requests.slice(0, 5);
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="overflow-hidden">
        <CardHeader title="Recent Leave Activity" icon={<CalendarCheck size={17} />} />
        {recent.length ? recent.map((row) => (
          <div key={row.id} className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-3 last:border-b-0">
            <div>
              <div className="text-sm font-bold text-[var(--color-brand-navy)]">{row.employee_name}</div>
              <div className="text-xs text-gray-500">{row.leave_type} · {formatDate(row.start_date)} - {formatDate(row.end_date)}</div>
            </div>
            <Badge variant={statusVariant(row.status)}>{row.status}</Badge>
          </div>
        )) : <EmptyState message="No leave activity yet." />}
      </Card>
      <Card className="overflow-hidden">
        <CardHeader title="Operational Queue" icon={<AlertTriangle size={17} />} />
        {[
          ['Leave requests waiting', data.overview.pending_leave_requests],
          ['Attendance corrections waiting', data.overview.pending_attendance_corrections],
          ['Timesheets waiting', data.overview.pending_timesheet_approvals],
          ['Employees absent today', data.overview.absent],
        ].map(([label, value]) => (
          <button
            key={label}
            type="button"
            onClick={() => onOpenQueue(String(label))}
            className="flex w-full items-center justify-between border-b border-[var(--color-border)] px-5 py-3 text-left transition-colors last:border-b-0 hover:bg-[var(--color-page-bg)]"
          >
            <span className="text-sm font-semibold text-[var(--color-brand-navy)]">{label}</span>
            <span className="text-lg font-bold text-olive">{value}</span>
          </button>
        ))}
      </Card>
    </div>
  );
}

function LeaveRequestsSection({ rows, onDecision, actionLoading }: { rows: LeaveRequestRow[]; onDecision: (url: string, decision: 'approve' | 'reject', label: string) => void; actionLoading: string }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader title="Leave Requests" icon={<CalendarCheck size={17} />} />
      {rows.length === 0 ? <EmptyState message="No leave requests found." /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
              <tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Leave Type</th><th className="px-5 py-3 text-left">Dates</th><th className="px-5 py-3 text-left">Days</th><th className="px-5 py-3 text-left">Reason</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-right">Action</th></tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="px-5 py-3 font-semibold">{row.employee_name}</td>
                  <td className="px-5 py-3">{row.leave_type}</td>
                  <td className="px-5 py-3">{formatDate(row.start_date)} - {formatDate(row.end_date)}</td>
                  <td className="px-5 py-3">{row.total_days}</td>
                  <td className="max-w-[260px] truncate px-5 py-3 text-gray-500">{row.reason || '-'}</td>
                  <td className="px-5 py-3"><Badge variant={statusVariant(row.status)}>{row.status}</Badge></td>
                  <td className="px-5 py-3 text-right">{row.status === 'pending' ? <ActionButtons disabled={!!actionLoading} onApprove={() => onDecision(`/admin/time-off/leave-requests/${row.id}/decision`, 'approve', 'Leave request')} onReject={() => onDecision(`/admin/time-off/leave-requests/${row.id}/decision`, 'reject', 'Leave request')} /> : <span className="text-xs text-gray-400">Reviewed</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function LeaveBalancesSection({ rows, employees, onOpen }: { rows: LeaveBalanceRow[]; employees: AdminEmployeeOption[]; onOpen: (group: EmployeeBalanceGroup) => void }) {
  const [search, setSearch] = useState('');
  const [department, setDepartment] = useState('All');
  const [leaveType, setLeaveType] = useState('All');
  const [lowBalance, setLowBalance] = useState(false);
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(1);

  const groups = useMemo(() => buildBalanceGroups(rows, employees), [employees, rows]);
  const departments = useMemo(() => ['All', ...Array.from(new Set(groups.map((group) => group.department))).sort()], [groups]);
  const leaveTypes = useMemo(() => ['All', ...Array.from(new Set(rows.map((row) => row.leave_type))).sort()], [rows]);
  const filtered = useMemo(() => groups.filter((group) => {
    const matchesSearch = group.employee_name.toLowerCase().includes(search.trim().toLowerCase());
    const matchesDepartment = department === 'All' || group.department === department;
    const matchesLeaveType = leaveType === 'All' || group.balances.some((balance) => balance.leave_type === leaveType);
    const matchesLowBalance = !lowBalance || group.balances.some((balance) => Number(balance.available_days || 0) <= 2 && Number(balance.total_days || 0) > 0);
    return matchesSearch && matchesDepartment && matchesLeaveType && matchesLowBalance;
  }), [department, groups, leaveType, lowBalance, search]);

  useEffect(() => {
    setPage(1);
  }, [department, leaveType, lowBalance, pageSize, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visible = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  return (
    <Card className="overflow-hidden">
      <CardHeader title="Leave Balances" icon={<BarChart3 size={17} />} />
      <div className="grid gap-3 border-b border-[var(--color-border)] px-5 py-4 xl:grid-cols-[1fr_auto_auto_auto_auto]">
        <label className="relative min-w-[240px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search employee..."
            className="h-10 w-full rounded-lg border border-[var(--color-border)] bg-warm-bg pl-9 pr-3 text-sm outline-none focus:border-olive"
          />
        </label>
        <select value={department} onChange={(event) => setDepartment(event.target.value)} className="h-10 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-olive">
          {departments.map((item) => <option key={item} value={item}>{item === 'All' ? 'Department: All' : item}</option>)}
        </select>
        <select value={leaveType} onChange={(event) => setLeaveType(event.target.value)} className="h-10 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-olive">
          {leaveTypes.map((item) => <option key={item} value={item}>{item === 'All' ? 'Leave Type: All' : item}</option>)}
        </select>
        <label className="flex h-10 items-center gap-2 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm font-semibold text-[var(--color-text-muted)]">
          <input type="checkbox" checked={lowBalance} onChange={(event) => setLowBalance(event.target.checked)} className="h-4 w-4 accent-olive" />
          Low balance
        </label>
        <select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))} className="h-10 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-olive">
          {[25, 50, 100].map((size) => <option key={size} value={size}>{size} rows</option>)}
        </select>
      </div>
      {rows.length === 0 ? <EmptyState message="No leave balances found." /> : visible.length === 0 ? <EmptyState message="No employees match the selected filters." /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
              <tr>
                <th className="px-5 py-3 text-left">Employee</th>
                <th className="px-5 py-3 text-left">Department</th>
                <th className="px-5 py-3 text-left">Balances</th>
                <th className="px-5 py-3 text-left">Total Available</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {visible.map((group) => (
                <tr key={group.employee_id} className="align-top">
                  <td className="px-5 py-4">
                    <div className="font-bold text-[var(--color-brand-navy)]">{group.employee_name}</div>
                    <div className="text-xs text-gray-400">{group.balances.length} leave types</div>
                  </td>
                  <td className="px-5 py-4 text-gray-600">{group.department}</td>
                  <td className="px-5 py-3">
                    <div className="flex max-w-[760px] flex-wrap gap-2">
                      {group.balances.map((balance) => {
                        const isLow = Number(balance.available_days || 0) <= 2 && Number(balance.total_days || 0) > 0;
                        return (
                          <span key={balance.id} className={cn('rounded-full border px-2.5 py-1 text-xs font-semibold', isLow ? 'border-status-warning/30 bg-status-warning/10 text-status-warning' : 'border-olive/15 bg-olive/5 text-[var(--color-text-muted)]')}>
                            {compactLeaveName(balance.leave_type)}: <span className="text-[var(--color-brand-navy)]">{formatBalanceNumber(balance.available_days)}/{formatBalanceNumber(balance.total_days)}</span>
                          </span>
                        );
                      })}
                    </div>
                  </td>
                  <td className="px-5 py-4 font-bold text-olive">{formatBalanceNumber(group.total_available)}</td>
                  <td className="px-5 py-3 text-right">
                    <Button size="sm" variant="ghost" icon={<Pencil size={13} />} onClick={() => onOpen(group)}>View / Adjust</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border)] px-5 py-3 text-sm text-gray-500">
        <span>Showing {visible.length ? (currentPage - 1) * pageSize + 1 : 0}-{Math.min(currentPage * pageSize, filtered.length)} of {filtered.length} employees</span>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" icon={<ChevronLeft size={14} />} disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button>
          <span className="text-xs font-semibold text-gray-400">Page {currentPage} of {totalPages}</span>
          <Button size="sm" variant="ghost" icon={<ChevronRight size={14} />} disabled={currentPage === totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>Next</Button>
        </div>
      </div>
    </Card>
  );
}

function AttendanceLogsSection({ rows, employees, filters, setFilters, onEdit }: { rows: AttendanceRow[]; employees: AdminEmployeeOption[]; filters: { date: string; employee: string; status: string }; setFilters: (filters: { date: string; employee: string; status: string }) => void; onEdit: (row: AttendanceRow) => void }) {
  const statuses = ['All', 'present', 'absent', 'late', 'wfh', 'checked_out'];
  return (
    <Card className="overflow-hidden">
      <CardHeader title="Attendance Logs" icon={<Clock3 size={17} />} />
      <div className="flex flex-wrap gap-2 border-b border-[var(--color-border)] px-5 py-3">
        <input type="date" value={filters.date} onChange={(event) => setFilters({ ...filters, date: event.target.value })} className="rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2 text-sm outline-none" />
        <select value={filters.employee} onChange={(event) => setFilters({ ...filters, employee: event.target.value })} className="rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2 text-sm outline-none">
          <option value="All">All Employees</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}
        </select>
        <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })} className="rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2 text-sm outline-none">
          {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
        </select>
      </div>
      {rows.length === 0 ? <EmptyState message="No attendance records match the filters." /> : (
        <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400"><tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Date</th><th className="px-5 py-3 text-left">Check In</th><th className="px-5 py-3 text-left">Check Out</th><th className="px-5 py-3 text-left">Hours</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-right">Action</th></tr></thead><tbody className="divide-y divide-[var(--color-border)]">{rows.map((row) => <tr key={row.id}><td className="px-5 py-3 font-semibold">{row.employee_name}</td><td className="px-5 py-3">{formatDate(row.date)}</td><td className="px-5 py-3">{formatDateTime(row.check_in)}</td><td className="px-5 py-3">{formatDateTime(row.check_out)}</td><td className="px-5 py-3">{row.total_hours || 0}h</td><td className="px-5 py-3"><Badge variant={statusVariant(row.status)}>{row.status}</Badge></td><td className="px-5 py-3 text-right"><Button size="sm" variant="ghost" icon={<Pencil size={13} />} onClick={() => onEdit(row)}>Correct</Button></td></tr>)}</tbody></table></div>
      )}
    </Card>
  );
}

function CorrectionsSection({ rows, onDecision, actionLoading }: { rows: CorrectionRow[]; onDecision: (url: string, decision: 'approve' | 'reject', label: string) => void; actionLoading: string }) {
  return (
    <Card className="overflow-hidden"><CardHeader title="Attendance Corrections" icon={<Pencil size={17} />} />{rows.length === 0 ? <EmptyState message="No correction requests found." /> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400"><tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Date</th><th className="px-5 py-3 text-left">Requested</th><th className="px-5 py-3 text-left">Reason</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-right">Action</th></tr></thead><tbody className="divide-y divide-[var(--color-border)]">{rows.map((row) => <tr key={row.id}><td className="px-5 py-3 font-semibold">{row.employee_name}</td><td className="px-5 py-3">{formatDate(row.attendance_date)}</td><td className="px-5 py-3">{formatDateTime(row.requested_check_in)} - {formatDateTime(row.requested_check_out)}</td><td className="max-w-[260px] truncate px-5 py-3 text-gray-500">{row.reason}</td><td className="px-5 py-3"><Badge variant={statusVariant(row.status)}>{row.status}</Badge></td><td className="px-5 py-3 text-right">{row.status === 'pending' ? <ActionButtons disabled={!!actionLoading} onApprove={() => onDecision(`/admin/time-off/corrections/${row.id}/decision`, 'approve', 'Attendance correction')} onReject={() => onDecision(`/admin/time-off/corrections/${row.id}/decision`, 'reject', 'Attendance correction')} /> : <span className="text-xs text-gray-400">Reviewed</span>}</td></tr>)}</tbody></table></div>}</Card>
  );
}

function TimesheetsAdminSection({ rows, onDecision, actionLoading }: { rows: TimesheetAdminRow[]; onDecision: (url: string, decision: 'approve' | 'reject', label: string) => void; actionLoading: string }) {
  return (
    <Card className="overflow-hidden"><CardHeader title="Timesheets" icon={<FileText size={17} />} />{rows.length === 0 ? <EmptyState message="No submitted or reviewed timesheets found." /> : <div className="overflow-x-auto"><table className="w-full min-w-[960px] text-sm"><thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400"><tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Week</th><th className="px-5 py-3 text-left">Working</th><th className="px-5 py-3 text-left">Break</th><th className="px-5 py-3 text-left">Overtime</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-right">Action</th></tr></thead><tbody className="divide-y divide-[var(--color-border)]">{rows.map((row) => <tr key={`${row.employee_id}-${row.week_start}`}><td className="px-5 py-3 font-semibold">{row.employee_name}</td><td className="px-5 py-3">{formatDate(row.week_start)} - {formatDate(row.week_end)}<details className="mt-1 text-xs text-gray-500"><summary className="cursor-pointer text-olive">Details</summary>{row.entries.slice(0, 8).map((entry, idx) => <div key={idx}>{formatDate(entry.date)} · {entry.code} · {entry.project} · {entry.hours}h</div>)}</details></td><td className="px-5 py-3">{row.working_hours}h</td><td className="px-5 py-3">{row.break_hours}h</td><td className="px-5 py-3">{row.overtime_hours}h</td><td className="px-5 py-3"><Badge variant={statusVariant(row.status)}>{row.status}</Badge></td><td className="px-5 py-3 text-right">{row.status === 'submitted' ? <ActionButtons disabled={!!actionLoading} onApprove={() => onDecision(`/admin/time-off/timesheets/${row.employee_id}/${row.week_start}/decision`, 'approve', 'Timesheet')} onReject={() => onDecision(`/admin/time-off/timesheets/${row.employee_id}/${row.week_start}/decision`, 'reject', 'Timesheet')} /> : <span className="text-xs text-gray-400">Reviewed</span>}</td></tr>)}</tbody></table></div>}</Card>
  );
}

function ReportsSection({ onExport }: { onExport: (report: string) => void }) {
  const reports = [
    ['attendance', 'Monthly Attendance Report', 'Daily check-in, check-out, status, and hours.'],
    ['leave', 'Leave Usage Report', 'Approved, rejected, and pending leave usage.'],
    ['overtime', 'Overtime Report', 'Overtime hours and approval status.'],
    ['absenteeism', 'Absenteeism Report', 'Absent-day summary by employee.'],
  ];
  return <div className="grid gap-3 md:grid-cols-2">{reports.map(([key, title, description]) => <Card key={key} className="p-5"><div className="mb-2 text-sm font-bold text-[var(--color-brand-navy)]">{title}</div><div className="mb-4 text-sm text-gray-500">{description}</div><Button variant="ghost" icon={<Download size={14} />} onClick={() => onExport(key)}>Export CSV</Button></Card>)}</div>;
}

function PoliciesSection({ data }: { data: TimeOffData }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="overflow-hidden"><CardHeader title="Leave Policies" icon={<ShieldCheck size={17} />} action={<a href="/admin/policies" className="text-xs font-bold text-olive">Manage Policies</a>} />{data.policies.map((policy) => <div key={policy.id} className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-3 last:border-b-0"><div><div className="text-sm font-bold text-[var(--color-brand-navy)]">{policy.name} ({policy.code})</div><div className="text-xs text-gray-500">{policy.default_days} days · {policy.paid ? 'Paid' : 'Unpaid'} · {policy.carry_forward ? `Carry forward up to ${policy.max_carry_forward}` : 'No carry forward'}</div></div><Badge variant={policy.active ? 'success' : 'neutral'}>{policy.active ? 'active' : 'inactive'}</Badge></div>)}</Card>
      <Card className="overflow-hidden"><CardHeader title="Attendance Policies" icon={<Clock3 size={17} />} />{data.attendance_policies.map((policy) => <div key={policy.name} className="border-b border-[var(--color-border)] px-5 py-3 last:border-b-0"><div className="text-sm font-bold text-[var(--color-brand-navy)]">{policy.name}</div><div className="text-xs text-gray-500">{policy.value}</div></div>)}</Card>
    </div>
  );
}

function BalanceDrawer({ group, headers, onClose, onSaved, onError }: { group: EmployeeBalanceGroup; headers: Record<string, string>; onClose: () => void; onSaved: (data: TimeOffData) => void; onError: (message: string) => void }) {
  const [editing, setEditing] = useState<LeaveBalanceRow | null>(null);
  const [form, setForm] = useState({ total_days: '', used_days: '', carry_forward_days: '', reason: '' });
  const [saving, setSaving] = useState(false);

  const startEdit = (row: LeaveBalanceRow) => {
    setEditing(row);
    setForm({
      total_days: String(row.total_days),
      used_days: String(row.used_days),
      carry_forward_days: String(row.carry_forward_days),
      reason: '',
    });
  };

  const save = async () => {
    if (!editing) return;
    if (!form.reason.trim()) return onError('Adjustment reason is required.');
    const totalDays = Number(form.total_days);
    const usedDays = Number(form.used_days);
    const carryForwardDays = Number(form.carry_forward_days);
    if ([totalDays, usedDays, carryForwardDays].some((value) => Number.isNaN(value) || value < 0)) return onError('Balance values must be valid positive numbers.');
    if (usedDays > totalDays + carryForwardDays) return onError('Used days cannot be greater than total plus carry forward.');
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/admin/time-off/leave-balances/${editing.id}`, { method: 'PUT', headers, body: JSON.stringify({ total_days: totalDays, used_days: usedDays, carry_forward_days: carryForwardDays, reason: form.reason.trim() }) });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || 'Could not adjust balance.');
      setEditing(null);
      onSaved(body);
    } catch (err) { onError(err instanceof Error ? err.message : 'Could not adjust balance.'); } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-[100] flex justify-end bg-[var(--color-brand-navy)]/40 backdrop-blur-sm">
      <button aria-label="Close leave balance drawer" className="absolute inset-0 cursor-default" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-4xl flex-col border-l border-[var(--color-border)] bg-white shadow-[0_24px_90px_rgba(17,24,39,0.30)]">
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-6 py-5">
          <div>
            <div className="text-xl font-bold text-[var(--color-brand-navy)]">Leave Balance</div>
            <div className="mt-1 text-sm text-gray-500">{group.employee_name} · {group.department}</div>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="grid gap-3 border-b border-[var(--color-border)] bg-warm-bg/60 px-6 py-4 sm:grid-cols-3">
          <div className="rounded-xl border border-[var(--color-border)] bg-white p-4">
            <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Leave Types</div>
            <div className="mt-1 text-2xl font-bold text-[var(--color-brand-navy)]">{group.balances.length}</div>
          </div>
          <div className="rounded-xl border border-[var(--color-border)] bg-white p-4">
            <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Total Available</div>
            <div className="mt-1 text-2xl font-bold text-olive">{formatBalanceNumber(group.total_available)}</div>
          </div>
          <div className="rounded-xl border border-[var(--color-border)] bg-white p-4">
            <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Low Balances</div>
            <div className="mt-1 text-2xl font-bold text-[var(--color-brand-orange)]">{group.balances.filter((balance) => Number(balance.available_days || 0) <= 2 && Number(balance.total_days || 0) > 0).length}</div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          <div className="overflow-hidden rounded-2xl border border-[var(--color-border)]">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="px-4 py-3 text-left">Leave Type</th>
                  <th className="px-4 py-3 text-left">Total</th>
                  <th className="px-4 py-3 text-left">Used</th>
                  <th className="px-4 py-3 text-left">Pending</th>
                  <th className="px-4 py-3 text-left">Available</th>
                  <th className="px-4 py-3 text-left">Last Updated By</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {group.balances.map((balance) => (
                  <tr key={balance.id} className={cn(editing?.id === balance.id && 'bg-olive/5')}>
                    <td className="px-4 py-3 font-bold text-[var(--color-brand-navy)]">{balance.leave_type}</td>
                    <td className="px-4 py-3">{formatBalanceNumber(balance.total_days)}</td>
                    <td className="px-4 py-3">{formatBalanceNumber(balance.used_days)}</td>
                    <td className="px-4 py-3">{formatBalanceNumber(balance.pending_days)}</td>
                    <td className="px-4 py-3 font-bold text-olive">{formatBalanceNumber(balance.available_days)}</td>
                    <td className="px-4 py-3 text-gray-500">{balance.updated_by || '-'}</td>
                    <td className="px-4 py-3 text-right"><Button size="sm" variant="ghost" icon={<Pencil size={13} />} onClick={() => startEdit(balance)}>Adjust</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {editing && (
            <div className="mt-5 rounded-2xl border border-olive/20 bg-olive/5 p-5">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-bold text-[var(--color-brand-navy)]">Adjust {editing.leave_type}</div>
                  <div className="text-xs text-gray-500">Changes are saved with an audit reason and updater details.</div>
                </div>
                <button onClick={() => setEditing(null)} className="rounded-lg p-1 text-gray-400 hover:bg-white hover:text-gray-600"><X size={16} /></button>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <NumberField label="Total Days" value={form.total_days} onChange={(v) => setForm({ ...form, total_days: v })} />
                <NumberField label="Used Days" value={form.used_days} onChange={(v) => setForm({ ...form, used_days: v })} />
                <NumberField label="Carry Forward" value={form.carry_forward_days} onChange={(v) => setForm({ ...form, carry_forward_days: v })} />
              </div>
              <div className="mt-3"><TextArea label="Adjustment Reason" value={form.reason} onChange={(v) => setForm({ ...form, reason: v })} /></div>
              <div className="mt-4 flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                <Button disabled={saving} onClick={save}>{saving ? 'Saving' : 'Save Adjustment'}</Button>
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function AttendanceModal({ row, headers, onClose, onSaved, onError }: { row: AttendanceRow; headers: Record<string, string>; onClose: () => void; onSaved: (data: TimeOffData) => void; onError: (message: string) => void }) {
  const toLocalInput = (value?: string | null) => value ? value.slice(0, 16) : '';
  const [form, setForm] = useState({ check_in: toLocalInput(row.check_in), check_out: toLocalInput(row.check_out), status: row.status, remarks: row.remarks || '', reason: '' });
  const save = async () => {
    if (!form.reason.trim()) return onError('Correction reason is required.');
    try {
      const res = await fetch(`${API_BASE}/admin/time-off/attendance/${row.id}`, { method: 'PUT', headers, body: JSON.stringify({ check_in: form.check_in ? new Date(form.check_in).toISOString() : null, check_out: form.check_out ? new Date(form.check_out).toISOString() : null, status: form.status, remarks: form.remarks, reason: form.reason.trim() }) });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || 'Could not update attendance.');
      onSaved(body);
    } catch (err) { onError(err instanceof Error ? err.message : 'Could not update attendance.'); }
  };
  return <Modal title="Correct Attendance" subtitle={`${row.employee_name} · ${formatDate(row.date)}`} onClose={onClose}><DateTimeField label="Check In" value={form.check_in} onChange={(v) => setForm({ ...form, check_in: v })} /><DateTimeField label="Check Out" value={form.check_out} onChange={(v) => setForm({ ...form, check_out: v })} /><label className="block text-sm font-semibold text-[var(--color-brand-navy)]">Status<select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2"><option value="present">Present</option><option value="absent">Absent</option><option value="late">Late</option><option value="wfh">WFH</option><option value="checked_out">Checked Out</option></select></label><TextArea label="Remarks" value={form.remarks} onChange={(v) => setForm({ ...form, remarks: v })} /><TextArea label="Reason" value={form.reason} onChange={(v) => setForm({ ...form, reason: v })} /><div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save}>Save Correction</Button></div></Modal>;
}

function Modal({ title, subtitle, children, onClose }: { title: string; subtitle?: string; children: React.ReactNode; onClose: () => void }) {
  return createPortal(
    <div className="fixed inset-0 z-[100] flex min-h-screen items-center justify-center bg-black/35 p-4">
      <div className="flex max-h-[calc(100vh-2rem)] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-[var(--color-border)] bg-white shadow-[0_24px_80px_rgba(17,24,39,0.25)]">
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <div className="text-lg font-bold text-[var(--color-brand-navy)]">{title}</div>
            {subtitle && <div className="text-sm text-gray-500">{subtitle}</div>}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="grid gap-3 overflow-y-auto p-5">{children}</div>
      </div>
    </div>,
    document.body
  );
}

function DecisionModal({
  decision,
  loading,
  onClose,
  onConfirm,
}: {
  decision: PendingDecision;
  loading: boolean;
  onClose: () => void;
  onConfirm: (note: string) => void;
}) {
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const isReject = decision.decision === 'reject';

  const submit = () => {
    if (isReject && !note.trim()) {
      setError('Rejection reason is required.');
      return;
    }
    onConfirm(note.trim());
  };

  return (
    <Modal
      title={`${isReject ? 'Reject' : 'Approve'} ${decision.label}`}
      subtitle={isReject ? 'Add a clear reason so the employee understands what needs to change.' : 'Add an optional note for audit history.'}
      onClose={loading ? () => undefined : onClose}
    >
      <label className="block text-sm font-semibold text-[var(--color-brand-navy)]">
        {isReject ? 'Rejection reason' : 'Approval note'}
        <textarea
          value={note}
          onChange={(event) => {
            setNote(event.target.value);
            setError('');
          }}
          rows={4}
          placeholder={isReject ? 'Explain why this cannot be approved...' : 'Optional note...'}
          className={cn('mt-2 w-full resize-none rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-brand-orange)]', error ? 'border-status-error' : 'border-[var(--color-border)]')}
        />
      </label>
      {error && <div className="rounded-lg border border-status-error/20 bg-status-error/10 px-3 py-2 text-sm text-status-error">{error}</div>}
      <div className="mt-2 flex justify-end gap-2">
        <Button variant="ghost" disabled={loading} onClick={onClose}>Cancel</Button>
        <Button disabled={loading} onClick={submit}>
          {loading ? 'Saving...' : isReject ? `Reject ${decision.label}` : `Approve ${decision.label}`}
        </Button>
      </div>
    </Modal>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm font-semibold text-[var(--color-brand-navy)]">{label}<input type="number" min="0" step="0.5" value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2 outline-none focus:border-olive" /></label>;
}

function DateTimeField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm font-semibold text-[var(--color-brand-navy)]">{label}<input type="datetime-local" value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2 outline-none focus:border-olive" /></label>;
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm font-semibold text-[var(--color-brand-navy)]">{label}<textarea value={value} onChange={(e) => onChange(e.target.value)} rows={2} className="mt-1 w-full resize-none rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2 outline-none focus:border-olive" /></label>;
}

export function EmployeesPage() {
  return (
    <PlaceholderPage
      title="Employees"
      description="View, manage, and search the complete employee directory."
    />
  );
}

interface OnboardingCandidate {
  id: string;
  name: string;
  initials: string;
  role: string;
  stage: 'offer' | 'paperwork' | 'access' | 'first_week' | 'complete';
  startDate: string;
  owner: string;
  location: string;
  priority: 'normal' | 'watch' | 'blocked' | 'done';
  checklist: Array<{ label: string; done: boolean; owner: string }>;
}

const onboardingStages: Array<{ key: OnboardingCandidate['stage']; label: string; helper: string }> = [
  { key: 'offer', label: 'Offer Accepted', helper: 'Pre-start readiness' },
  { key: 'paperwork', label: 'Paperwork', helper: 'Documents and compliance' },
  { key: 'access', label: 'IT & Access', helper: 'Devices, apps, credentials' },
  { key: 'first_week', label: 'First Week', helper: 'Manager and team ramp' },
  { key: 'complete', label: 'Complete', helper: 'Ready for regular work' },
];

const onboardingCandidates: OnboardingCandidate[] = [
  {
    id: 'onb-priyanka',
    name: 'Priyanka Shah',
    initials: 'PS',
    role: 'AI Engineer',
    stage: 'offer',
    startDate: '2026-08-04',
    owner: 'Priya Nair',
    location: 'Hyderabad',
    priority: 'watch',
    checklist: [
      { label: 'Offer letter accepted', done: true, owner: 'HR' },
      { label: 'Confirm joining date', done: false, owner: 'HR' },
      { label: 'Collect personal documents', done: false, owner: 'HR' },
      { label: 'Assign reporting manager', done: false, owner: 'People Ops' },
      { label: 'Create onboarding plan', done: false, owner: 'Manager' },
      { label: 'Share pre-joining handbook', done: false, owner: 'HR' },
      { label: 'Collect bank and payroll details', done: false, owner: 'Payroll' },
      { label: 'Schedule day-one orientation', done: false, owner: 'People Ops' },
    ],
  },
  {
    id: 'onb-sofia',
    name: 'Sofia Lind',
    initials: 'SL',
    role: 'Recruiter',
    stage: 'paperwork',
    startDate: '2026-07-08',
    owner: 'Hari Prasad',
    location: 'Remote',
    priority: 'normal',
    checklist: [
      { label: 'Background verification', done: true, owner: 'HR' },
      { label: 'Tax forms', done: true, owner: 'Payroll' },
      { label: 'Policy acknowledgment', done: true, owner: 'HR' },
      { label: 'Employment agreement signed', done: true, owner: 'HR' },
      { label: 'Emergency contact details', done: true, owner: 'HR' },
      { label: 'Benefits enrollment', done: false, owner: 'People Ops' },
      { label: 'Upload signed documents', done: false, owner: 'Employee' },
      { label: 'Payroll profile review', done: false, owner: 'Payroll' },
    ],
  },
  {
    id: 'onb-leo',
    name: 'Leo Nakamura',
    initials: 'LN',
    role: 'ML Engineer',
    stage: 'access',
    startDate: '2026-07-13',
    owner: 'David Park',
    location: 'New York',
    priority: 'blocked',
    checklist: [
      { label: 'Laptop assigned', done: true, owner: 'IT' },
      { label: 'Email account created', done: true, owner: 'IT' },
      { label: 'HRMS account activated', done: true, owner: 'IT' },
      { label: 'Git and cloud access', done: false, owner: 'Engineering' },
      { label: 'Security training', done: false, owner: 'IT' },
      { label: 'MFA and password setup', done: false, owner: 'IT' },
    ],
  },
  {
    id: 'onb-james',
    name: 'James Okoro',
    initials: 'JO',
    role: 'Data Engineer',
    stage: 'paperwork',
    startDate: '2026-07-28',
    owner: 'Priya Sharma',
    location: 'Austin',
    priority: 'normal',
    checklist: [
      { label: 'Offer letter accepted', done: true, owner: 'HR' },
      { label: 'Identity verification', done: true, owner: 'HR' },
      { label: 'Background verification', done: true, owner: 'HR' },
      { label: 'Payroll setup', done: false, owner: 'Payroll' },
      { label: 'Compliance forms', done: false, owner: 'HR' },
      { label: 'Policy acknowledgment', done: false, owner: 'HR' },
      { label: 'Benefits enrollment', done: false, owner: 'People Ops' },
      { label: 'Document audit review', done: false, owner: 'People Ops' },
    ],
  },
  {
    id: 'onb-tomas',
    name: 'Tomas Berg',
    initials: 'TB',
    role: 'Data Engineer',
    stage: 'first_week',
    startDate: '2026-07-06',
    owner: 'David Park',
    location: 'Chicago',
    priority: 'watch',
    checklist: [
      { label: 'Team introduction', done: true, owner: 'Manager' },
      { label: 'Project overview', done: true, owner: 'Manager' },
      { label: 'Workspace and tool walkthrough', done: true, owner: 'Buddy' },
      { label: 'Buddy check-in', done: true, owner: 'Buddy' },
      { label: 'First week feedback', done: true, owner: 'Manager' },
      { label: '30-day goals confirmed', done: false, owner: 'Manager' },
    ],
  },
  {
    id: 'onb-diego',
    name: 'Diego Santos',
    initials: 'DS',
    role: 'Account Executive',
    stage: 'complete',
    startDate: '2026-06-17',
    owner: 'Priya Nair',
    location: 'Miami',
    priority: 'done',
    checklist: [
      { label: 'Offer and paperwork completed', done: true, owner: 'HR' },
      { label: 'All access confirmed', done: true, owner: 'IT' },
      { label: 'Equipment delivered', done: true, owner: 'IT' },
      { label: 'Team and manager introductions completed', done: true, owner: 'Manager' },
      { label: 'Manager sign-off', done: true, owner: 'Manager' },
      { label: 'Probation goals created', done: true, owner: 'HR' },
      { label: 'Onboarding survey sent', done: true, owner: 'People Ops' },
      { label: 'Moved to active employee roster', done: true, owner: 'People Ops' },
    ],
  },
];

function onboardingPriorityVariant(priority: OnboardingCandidate['priority']): 'success' | 'warning' | 'error' | 'neutral' {
  if (priority === 'done') return 'success';
  if (priority === 'blocked') return 'error';
  if (priority === 'watch') return 'warning';
  return 'neutral';
}

function onboardingPriorityLabel(priority: OnboardingCandidate['priority']) {
  if (priority === 'done') return 'Complete';
  if (priority === 'blocked') return 'Blocked';
  if (priority === 'watch') return 'Watch';
  return 'On track';
}

function onboardingProgress(candidate: OnboardingCandidate) {
  return Math.round((onboardingCompletedTasks(candidate) / onboardingTotalTasks(candidate)) * 100);
}

function onboardingCompletedTasks(candidate: OnboardingCandidate) {
  return candidate.checklist.filter((item) => item.done).length;
}

function onboardingTotalTasks(candidate: OnboardingCandidate) {
  return Math.max(candidate.checklist.length, 1);
}

function OnboardingCard({ candidate, selected, onSelect }: { candidate: OnboardingCandidate; selected: boolean; onSelect: () => void }) {
  const progress = onboardingProgress(candidate);
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'w-full rounded-xl border bg-white p-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-[var(--color-brand-orange)]/40 hover:shadow-card-md',
        selected ? 'border-[var(--color-brand-orange)] ring-2 ring-[var(--color-brand-orange)]/10' : 'border-[var(--color-border)]'
      )}
    >
      <div className="flex items-start gap-3">
        <Avatar initials={candidate.initials} size="sm" variant="filled" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold leading-tight text-[var(--color-brand-navy)]">{candidate.name}</div>
          <div className="mt-0.5 text-xs font-medium leading-tight text-gray-500">{candidate.role}</div>
        </div>
        <Badge variant={onboardingPriorityVariant(candidate.priority)}>{onboardingPriorityLabel(candidate.priority)}</Badge>
      </div>
      <div className="mt-4 h-2 rounded-full bg-[var(--color-brand-orange)]/10">
        <div className={cn('h-2 rounded-full', candidate.priority === 'blocked' ? 'bg-status-error' : candidate.priority === 'watch' ? 'bg-status-warning' : 'bg-[var(--color-brand-orange)]')} style={{ width: `${progress}%` }} />
      </div>
      <div className="mt-3 flex items-center justify-between text-xs font-semibold text-gray-500">
        <span>{onboardingCompletedTasks(candidate)}/{onboardingTotalTasks(candidate)} tasks</span>
        <span>Starts {formatDate(candidate.startDate).replace(', 2026', '')}</span>
      </div>
    </button>
  );
}

export function OnboardingPage() {
  const [selectedId, setSelectedId] = useState(onboardingCandidates[0]?.id || '');
  const [query, setQuery] = useState('');
  const filteredCandidates = onboardingCandidates.filter((candidate) => (
    [candidate.name, candidate.role, candidate.owner, candidate.location].join(' ').toLowerCase().includes(query.trim().toLowerCase())
  ));
  const selected = onboardingCandidates.find((candidate) => candidate.id === selectedId) || onboardingCandidates[0];
  const totalTasks = onboardingCandidates.reduce((sum, candidate) => sum + onboardingTotalTasks(candidate), 0);
  const completedTasks = onboardingCandidates.reduce((sum, candidate) => sum + onboardingCompletedTasks(candidate), 0);
  const completion = Math.round((completedTasks / totalTasks) * 100);

  return (
    <div className="animate-fade-up pt-2">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Onboarding Center</h1>
          <p className="text-sm text-gray-500">Track new hires from accepted offer through first-week completion.</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="relative min-w-[280px]">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search new hires, owners..."
              className="h-10 w-full rounded-xl border border-[var(--color-border)] bg-white pl-9 pr-3 text-sm outline-none focus:border-[var(--color-brand-orange)]"
            />
          </label>
          <Button icon={<Plus size={15} />}>Add New Hire</Button>
        </div>
      </div>

      <div className="mb-5 grid gap-3 md:grid-cols-4">
        <Card className="p-4">
          <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Active Onboarding</div>
          <div className="mt-2 text-2xl font-bold text-[var(--color-brand-navy)]">{onboardingCandidates.filter((candidate) => candidate.stage !== 'complete').length}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Tasks Complete</div>
          <div className="mt-2 text-2xl font-bold text-[var(--color-brand-navy)]">{completedTasks}/{totalTasks}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Overall Progress</div>
          <div className="mt-2 flex items-center gap-3">
            <div className="h-2 flex-1 rounded-full bg-[var(--color-brand-orange)]/10"><div className="h-2 rounded-full bg-[var(--color-brand-orange)]" style={{ width: `${completion}%` }} /></div>
            <span className="text-sm font-bold text-[var(--color-brand-orange)]">{completion}%</span>
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Needs Attention</div>
          <div className="mt-2 text-2xl font-bold text-status-warning">{onboardingCandidates.filter((candidate) => candidate.priority === 'watch' || candidate.priority === 'blocked').length}</div>
        </Card>
      </div>

      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-5">
          {onboardingStages.map((stage) => {
            const stageCandidates = filteredCandidates.filter((candidate) => candidate.stage === stage.key);
            return (
              <section key={stage.key} className="min-h-[330px] rounded-2xl border border-[var(--color-border)] bg-white p-4 shadow-sm">
                <div className="mb-3 flex items-start justify-between gap-2 px-1">
                  <div>
                    <div className="text-xs font-bold uppercase tracking-wide text-gray-400">{stage.label}</div>
                    <div className="mt-1 text-xs text-gray-500">{stage.helper}</div>
                  </div>
                  <span className="rounded-full bg-[var(--color-brand-orange)]/10 px-2 py-0.5 text-xs font-bold text-[var(--color-brand-orange)] shadow-sm">{stageCandidates.length}</span>
                </div>
                <div className="space-y-3">
                  {stageCandidates.length ? stageCandidates.map((candidate) => (
                    <OnboardingCard
                      key={candidate.id}
                      candidate={candidate}
                      selected={selected?.id === candidate.id}
                      onSelect={() => setSelectedId(candidate.id)}
                    />
                  )) : (
                    <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-page-bg)] px-3 py-8 text-center text-sm text-gray-400">No new hires</div>
                  )}
                </div>
              </section>
            );
          })}
        </div>

        <Card className="overflow-hidden">
          {selected ? (
            <div className="grid gap-0 xl:grid-cols-[380px_minmax(0,1fr)]">
              <div className="border-b border-[var(--color-border)] p-5 xl:border-b-0 xl:border-r">
                <div className="flex items-start gap-3">
                  <Avatar initials={selected.initials} size="lg" variant="filled" />
                  <div className="min-w-0 flex-1">
                    <div className="text-lg font-bold text-[var(--color-brand-navy)]">{selected.name}</div>
                    <div className="text-sm text-gray-500">{selected.role} - {selected.location}</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge variant={onboardingPriorityVariant(selected.priority)}>{onboardingPriorityLabel(selected.priority)}</Badge>
                      <Badge variant="neutral">{selected.owner}</Badge>
                    </div>
                  </div>
                </div>
                <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
                  <div className="rounded-xl bg-[var(--color-page-bg)] p-3">
                    <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Start Date</div>
                    <div className="mt-1 text-sm font-bold text-[var(--color-brand-navy)]">{formatDate(selected.startDate)}</div>
                  </div>
                  <div className="rounded-xl bg-[var(--color-page-bg)] p-3">
                    <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Progress</div>
                    <div className="mt-1 text-sm font-bold text-[var(--color-brand-navy)]">{onboardingCompletedTasks(selected)}/{onboardingTotalTasks(selected)} tasks</div>
                  </div>
                </div>
              </div>
              <div className="p-5">
                <div className="mb-3 text-sm font-bold text-[var(--color-brand-navy)]">Checklist</div>
                <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {selected.checklist.map((item) => (
                    <div key={item.label} className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] bg-white p-3">
                      <span className={cn('mt-0.5 flex h-5 w-5 items-center justify-center rounded-full border', item.done ? 'border-[var(--color-brand-orange)] bg-[var(--color-brand-orange)] text-white' : 'border-gray-300 text-gray-300')}>
                        <CheckCircle2 size={13} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className={cn('text-sm font-semibold', item.done ? 'text-[var(--color-brand-navy)]' : 'text-gray-500')}>{item.label}</div>
                        <div className="mt-0.5 text-xs text-gray-400">Owner: {item.owner}</div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <Button variant="ghost" icon={<Pencil size={14} />}>Edit Plan</Button>
                  <Button icon={<UserCheck size={14} />}>Assign Owner</Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-sm text-gray-500">Select an onboarding card to see details.</div>
          )}
        </Card>
      </div>
    </div>
  );
}

interface ClientRow { id: string; client_name: string; industry?: string | null; website?: string | null; status: string; primary_contact_name?: string | null; contact_email?: string | null; onboarding_stage: string; progress_percent: number; target_go_live_date?: string | null; owner_id?: string | null; owner_name: string }
interface ClientActivityRow { id: string; action: string; details?: string | null; performed_by_name: string; created_at?: string | null }
interface ClientDetail {
  client: ClientRow & { contact_phone?: string | null; contract_start_date?: string | null; contract_end_date?: string | null; notes?: string | null; created_at?: string | null; updated_at?: string | null };
  onboarding: { id?: string; stage: string; progress_percent: number; target_go_live_date?: string | null; actual_go_live_date?: string | null; owner_id?: string | null };
  checklist: Array<{ id: string; title: string; is_complete: boolean; owner_id?: string | null; owner_name?: string | null; due_date?: string | null; notes?: string | null }>;
  tasks: Array<{ id: string; title: string; description?: string | null; assigned_to_id?: string | null; assigned_to_name?: string | null; priority: string; status: string; due_date?: string | null }>;
  team: Array<{ id: string; employee_id: string; employee_name: string; role: string; notes?: string | null }>;
  documents: Array<{ id: string; document_type: string; file_name: string; file_url?: string | null; notes?: string | null; uploaded_by_name?: string | null; created_at?: string | null }>;
  milestones: Array<{ id: string; milestone_name: string; target_date?: string | null; actual_date?: string | null; status: string }>;
  activity: ClientActivityRow[];
}
interface ClientMetrics { total_clients: number; in_onboarding: number; active_clients: number; at_risk: number }
interface ClientData { clients: ClientRow[]; total_count: number; metrics: ClientMetrics; employees: AdminEmployeeOption[]; stages: string[] }

const emptyClientMetrics: ClientMetrics = { total_clients: 0, in_onboarding: 0, active_clients: 0, at_risk: 0 };

const clientStatuses = ['Prospect', 'Contract Signed', 'Onboarding', 'Active', 'Paused', 'Completed', 'At Risk'];
const clientTabs = ['Overview', 'Checklist', 'Tasks', 'Team', 'Documents', 'Milestones', 'Activity'];
const teamRoles = ['Client Manager', 'Project Manager', 'Technical Lead', 'Developer', 'QA', 'Support'];
const documentTypes = ['NDA', 'MSA', 'SOW', 'Requirements', 'Architecture', 'Training Material', 'Other'];

function apiValue(value: string) {
  return value.toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_');
}

function labelize(value?: string | null) {
  return (value || '-').replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function clientInitials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'CL';
}

function clientStatusVariant(status?: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'olive' {
  if (status === 'active' || status === 'completed') return 'success';
  if (status === 'at_risk') return 'error';
  if (status === 'paused') return 'warning';
  if (status === 'onboarding' || status === 'contract_signed') return 'info';
  return 'neutral';
}

function ClientField({ label, value, onChange, onBlur, type = 'text', options, required, error }: { label: string; value: string; onChange: (value: string) => void; onBlur?: () => void; type?: string; options?: Array<{ value: string; label: string }>; required?: boolean; error?: string }) {
  return (
    <label className="block text-sm font-semibold text-[var(--color-brand-navy)]">
      {label}{required && <span className="text-status-error"> *</span>}
      {options ? (
        <select value={value} onChange={(event) => onChange(event.target.value)} onBlur={onBlur} className={cn('mt-1 w-full rounded-lg border bg-warm-bg px-3 py-2 outline-none focus:border-olive', error ? 'border-status-error' : 'border-[var(--color-border)]')}>
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      ) : (
        <input type={type} value={value} onChange={(event) => onChange(event.target.value)} onBlur={onBlur} className={cn('mt-1 w-full rounded-lg border bg-warm-bg px-3 py-2 outline-none focus:border-olive', error ? 'border-status-error' : 'border-[var(--color-border)]')} />
      )}
      {error && <span className="mt-1 block text-xs font-medium text-status-error">{error}</span>}
    </label>
  );
}

function ClientFormDrawer({ client, employees, stages, currentUserId, onClose, onSave, saving }: { client?: ClientDetail | null; employees: AdminEmployeeOption[]; stages: string[]; currentUserId?: string; onClose: () => void; onSave: (payload: Record<string, unknown>, id?: string) => void; saving: boolean }) {
  const [form, setForm] = useState({
    client_name: client?.client.client_name || '',
    industry: client?.client.industry || '',
    website: client?.client.website || '',
    primary_contact_name: client?.client.primary_contact_name || '',
    contact_email: client?.client.contact_email || '',
    contact_phone: client?.client.contact_phone || '',
    contract_start_date: client?.client.contract_start_date || '',
    contract_end_date: client?.client.contract_end_date || '',
    status: client?.client.status || 'contract_signed',
    owner_id: client?.client.owner_id || currentUserId || '',
    notes: client?.client.notes || '',
    onboarding_stage: client?.onboarding.stage || 'Contract Signed',
    target_go_live_date: client?.onboarding.target_go_live_date || '',
  });
  const [touched, setTouched] = useState<Partial<Record<keyof typeof form, boolean>>>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const update = (key: keyof typeof form, value: string) => setForm({ ...form, [key]: value });
  const markTouched = (key: keyof typeof form) => setTouched((current) => ({ ...current, [key]: true }));
  const employeeOptions = [{ value: '', label: 'Unassigned' }, ...employees.map((employee) => ({ value: employee.id, label: employee.name }))];
  const stageOptions = stages.map((stage) => ({ value: stage, label: stage }));
  const errors = {
    client_name: form.client_name.trim().length < 2 ? 'Client name is required.' : '',
    industry: form.industry.trim().length < 2 ? 'Industry is required.' : '',
    primary_contact_name: form.primary_contact_name.trim().length < 2 ? 'Primary contact is required.' : '',
    contact_email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.contact_email.trim()) ? '' : 'Enter a valid email address.',
    contract_end_date: form.contract_start_date && form.contract_end_date && form.contract_end_date < form.contract_start_date ? 'End date cannot be before start date.' : '',
    target_go_live_date: form.contract_start_date && form.target_go_live_date && form.target_go_live_date < form.contract_start_date ? 'Go-live cannot be before contract start.' : '',
  };
  const isValid = Object.values(errors).every((value) => !value);
  const visibleError = (key: keyof typeof errors) => submitAttempted || touched[key] ? errors[key] : '';
  const submit = () => {
    setSubmitAttempted(true);
    if (!isValid) return;
    onSave(form, client?.client.id);
  };
  return (
    <div className="fixed inset-0 z-[110] bg-black/35">
      <div className="ml-auto flex h-full w-full max-w-[640px] animate-fade-up flex-col border-l border-[var(--color-border)] bg-white shadow-[0_24px_90px_rgba(17,24,39,0.35)]">
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-[var(--color-border)] bg-white px-6 py-5">
          <div><div className="text-xl font-bold text-[var(--color-brand-navy)]">{client ? 'Edit Client' : 'Add Client'}</div><div className="text-sm text-gray-500">Create and manage client onboarding details.</div></div>
          <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg hover:text-gray-700"><X size={18} /></button>
        </div>
        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          <ClientFormSection title="Client Information">
            <ClientField required label="Client Name" value={form.client_name} error={visibleError('client_name')} onBlur={() => markTouched('client_name')} onChange={(v) => update('client_name', v)} />
            <ClientField required label="Industry" value={form.industry} error={visibleError('industry')} onBlur={() => markTouched('industry')} onChange={(v) => update('industry', v)} />
            <ClientField label="Website" value={form.website} onChange={(v) => update('website', v)} />
          </ClientFormSection>
          <ClientFormSection title="Contact Information">
            <ClientField required label="Primary Contact Name" value={form.primary_contact_name} error={visibleError('primary_contact_name')} onBlur={() => markTouched('primary_contact_name')} onChange={(v) => update('primary_contact_name', v)} />
            <ClientField required label="Contact Email" value={form.contact_email} error={visibleError('contact_email')} onBlur={() => markTouched('contact_email')} onChange={(v) => update('contact_email', v)} />
            <ClientField label="Contact Phone" value={form.contact_phone} onChange={(v) => update('contact_phone', v.replace(/[^\d+()\-\s]/g, ''))} />
          </ClientFormSection>
          <ClientFormSection title="Contract Information">
            <ClientField label="Contract Start Date" type="date" value={form.contract_start_date} onChange={(v) => update('contract_start_date', v)} />
            <ClientField label="Contract End Date" type="date" value={form.contract_end_date} error={visibleError('contract_end_date')} onBlur={() => markTouched('contract_end_date')} onChange={(v) => update('contract_end_date', v)} />
          </ClientFormSection>
          <ClientFormSection title="Onboarding Details">
            <ClientField required label="Status" value={form.status} onChange={(v) => update('status', v)} options={clientStatuses.map((status) => ({ value: apiValue(status), label: status }))} />
            <ClientField required label="Onboarding Stage" value={form.onboarding_stage} onChange={(v) => update('onboarding_stage', v)} options={stageOptions} />
            <ClientField label="Owner / Client Manager" value={form.owner_id} onChange={(v) => update('owner_id', v)} options={employeeOptions} />
            <ClientField label="Target Go-Live Date" type="date" value={form.target_go_live_date} error={visibleError('target_go_live_date')} onBlur={() => markTouched('target_go_live_date')} onChange={(v) => update('target_go_live_date', v)} />
          </ClientFormSection>
          <div>
            <div className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-gray-400">Notes</div>
            <textarea value={form.notes} onChange={(event) => update('notes', event.target.value)} rows={4} className="w-full resize-none rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2 text-sm outline-none focus:border-olive" placeholder="Add onboarding context, risks, or expectations..." />
          </div>
        </div>
        <div className="sticky bottom-0 flex justify-end gap-2 border-t border-[var(--color-border)] bg-white px-6 py-4">
          <Button variant="ghost" disabled={saving} onClick={onClose}>Cancel</Button>
          <Button disabled={saving} onClick={submit}>{saving ? 'Saving...' : 'Save Client'}</Button>
        </div>
      </div>
    </div>
  );
}

function ClientFormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section><div className="mb-3 text-xs font-bold uppercase tracking-[0.16em] text-gray-400">{title}</div><div className="grid gap-3 md:grid-cols-2">{children}</div></section>;
}

function ClientQuickModal({ title, fields, onClose, onSave }: { title: string; fields: Array<{ key: string; label: string; type?: string; options?: Array<{ value: string; label: string }> }>; onClose: () => void; onSave: (payload: Record<string, string>) => void }) {
  const [form, setForm] = useState<Record<string, string>>(Object.fromEntries(fields.map((field) => [field.key, field.options?.[0]?.value || ''])));
  return (
    <Modal title={title} onClose={onClose}>
      {fields.map((field) => <ClientField key={field.key} label={field.label} value={form[field.key] || ''} type={field.type || 'text'} options={field.options} onChange={(value) => setForm({ ...form, [field.key]: value })} />)}
      <div className="mt-2 flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={() => onSave(form)}>Save</Button></div>
    </Modal>
  );
}

export function ClientOnboardingPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const role = (user?.role || '').toLowerCase().replace(/\s+/g, '_');
  const canAdmin = ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(role);
  const headers = useMemo(() => ({ 'Content-Type': 'application/json', 'x-user-id': user?.id || '', 'x-user-email': user?.email || '', 'x-user-name': user?.name || '' }), [user]);
  const [data, setData] = useState<ClientData>({ clients: [], total_count: 0, metrics: emptyClientMetrics, employees: [], stages: [] });
  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({ status: 'All', stage: 'All', owner: 'All' });
  const [activeTab, setActiveTab] = useState('Overview');
  const [clientForm, setClientForm] = useState<ClientDetail | null | 'new'>(null);
  const [quickForm, setQuickForm] = useState<null | { type: string; title: string; fields: Array<{ key: string; label: string; type?: string; options?: Array<{ value: string; label: string }> }> }>(null);
  const [savingClient, setSavingClient] = useState(false);

  const loadClients = useCallback(async () => {
    if (!user || !canAdmin) return;
    setLoading(true);
    setLoadError(null);
    const params = new URLSearchParams();
    if (search.trim()) params.set('search', search.trim());
    if (filters.status !== 'All') params.set('status', filters.status);
    if (filters.stage !== 'All') params.set('stage', filters.stage);
    if (filters.owner !== 'All') params.set('owner', filters.owner);
    try {
      const res = await fetch(`${API_BASE}/admin/client-onboarding?${params.toString()}`, { headers });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || 'Could not load client onboarding.');
      setData({ ...body, metrics: body.metrics || emptyClientMetrics });
      if (detail && !body.clients.some((client: ClientRow) => client.id === detail.client.id)) setDetail(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not load client onboarding.';
      setLoadError(message);
      showToast({ message });
    } finally {
      setLoading(false);
    }
  }, [canAdmin, detail, filters.owner, filters.stage, filters.status, headers, search, showToast, user]);

  useEffect(() => { loadClients(); }, [loadClients]);

  const loadDetail = async (id: string) => {
    const res = await fetch(`${API_BASE}/admin/client-onboarding/${id}`, { headers });
    const body = await res.json().catch(() => null);
    if (!res.ok) return showToast({ message: body?.detail || 'Could not load client details.' });
    setDetail(body);
    setActiveTab('Overview');
  };

  const saveClient = async (payload: Record<string, unknown>, id?: string) => {
    if (!String(payload.client_name || '').trim()) return showToast({ message: 'Client name is required.' });
    setSavingClient(true);
    const method = id ? 'PUT' : 'POST';
    const url = id ? `${API_BASE}/admin/client-onboarding/${id}` : `${API_BASE}/admin/client-onboarding`;
    const cleaned = Object.fromEntries(Object.entries(payload).map(([key, value]) => [key, value === '' ? null : value]));
    try {
      const res = await fetch(url, { method, headers, body: JSON.stringify(cleaned) });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || 'Could not save client.');
      setClientForm(null);
      setDetail(body);
      await loadClients();
      showToast({ message: id ? 'Client updated.' : 'Client added.' });
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not save client.' });
    } finally {
      setSavingClient(false);
    }
  };

  const updateDetail = async (url: string, method: string, payload?: Record<string, unknown>, message = 'Saved.') => {
    if (!detail) return;
    const res = await fetch(`${API_BASE}/admin/client-onboarding/${detail.client.id}${url}`, { method, headers, body: payload ? JSON.stringify(Object.fromEntries(Object.entries(payload).map(([key, value]) => [key, value === '' ? null : value]))) : undefined });
    const body = await res.json().catch(() => null);
    if (!res.ok) return showToast({ message: body?.detail || 'Action failed.' });
    setDetail(body);
    await loadClients();
    showToast({ message });
  };

  const employeeOptions = [{ value: '', label: 'Unassigned' }, ...data.employees.map((employee) => ({ value: employee.id, label: employee.name }))];
  const ownerOptions = ['All', ...data.employees.map((employee) => employee.id)];
  const filtersActive = !!search.trim() || filters.status !== 'All' || filters.stage !== 'All' || filters.owner !== 'All';
  const metrics = useMemo(() => {
    return [
      { label: 'Total Clients', value: data.metrics.total_clients, icon: <Building2 size={18} />, tone: 'olive' },
      { label: 'In Onboarding', value: data.metrics.in_onboarding, icon: <RefreshCw size={18} />, tone: 'info' },
      { label: 'Active Clients', value: data.metrics.active_clients, icon: <CheckCircle2 size={18} />, tone: 'success' },
      { label: 'Delayed / At Risk', value: data.metrics.at_risk, icon: <AlertTriangle size={18} />, tone: 'warning' },
    ];
  }, [data.metrics]);

  if (!canAdmin) return <PlaceholderPage title="Client Onboarding" description="Admin access required." />;

  return (
    <div className="animate-fade-up">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="mb-1 text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Client Onboarding</h1><p className="text-sm text-gray-500">Manage client onboarding from contract signed to go-live.</p></div>
        <Button icon={<Plus size={15} />} onClick={() => setClientForm('new')}>Add Client</Button>
      </div>
      <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((item) => <Card key={item.label} className="p-5"><div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-hover-bg text-olive">{item.icon}</div><div className="text-2xl font-bold text-[var(--color-brand-navy)]">{loading || loadError ? '—' : item.value}</div><div className="text-sm text-gray-500">{item.label}</div></Card>)}
      </div>
      <Card className="mb-5 p-4">
        <div className="grid gap-3 xl:grid-cols-[1fr_auto_auto_auto_auto]">
          <label className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search clients or contacts..." className="h-10 w-full rounded-lg border border-[var(--color-border)] bg-warm-bg pl-9 pr-3 text-sm outline-none focus:border-olive" /></label>
          <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })} className="h-10 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm"><option>All</option>{clientStatuses.map((status) => <option key={status} value={apiValue(status)}>{status}</option>)}</select>
          <select value={filters.stage} onChange={(event) => setFilters({ ...filters, stage: event.target.value })} className="h-10 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm"><option>All</option>{data.stages.map((stage) => <option key={stage}>{stage}</option>)}</select>
          <select value={filters.owner} onChange={(event) => setFilters({ ...filters, owner: event.target.value })} className="h-10 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm">{ownerOptions.map((owner) => <option key={owner} value={owner}>{owner === 'All' ? 'Owner: All' : data.employees.find((employee) => employee.id === owner)?.name || owner}</option>)}</select>
          {filtersActive && <Button variant="ghost" onClick={() => { setSearch(''); setFilters({ status: 'All', stage: 'All', owner: 'All' }); }}>Clear filters</Button>}
        </div>
        <div className="mt-3 text-xs font-semibold text-gray-500">{filtersActive ? `Showing ${data.clients.length} of ${data.total_count} clients` : `${data.total_count || data.clients.length} clients`}</div>
      </Card>
      <Card className="mb-5 overflow-hidden">
        <CardHeader title="Clients" icon={<Users size={17} />} />
        {loading ? <EmptyState message="Loading clients..." /> : loadError ? (
          <div className="px-6 py-16 text-center"><div className="text-lg font-bold text-[var(--color-brand-navy)]">Could not load clients</div><div className="mx-auto mt-2 max-w-xl text-sm text-gray-500">{loadError}</div><Button className="mt-5" variant="ghost" onClick={loadClients}>Try Again</Button></div>
        ) : data.clients.length === 0 ? (
          <div className="px-6 py-16 text-center"><div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-hover-bg text-olive"><BriefcaseBusiness size={24} /></div><div className="text-lg font-bold text-[var(--color-brand-navy)]">No clients yet</div><div className="mx-auto mt-2 max-w-xl text-sm text-gray-500">Create your first client onboarding record using Add Client above to track contracts, checklist items, tasks, team assignments, milestones, and go-live progress.</div></div>
        ) : <div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-sm"><thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400"><tr><th className="px-5 py-3 text-left">Client</th><th className="px-5 py-3 text-left">Industry</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-left">Stage</th><th className="px-5 py-3 text-left">Progress</th><th className="px-5 py-3 text-left">Owner</th><th className="px-5 py-3 text-left">Target Go-Live</th><th className="px-5 py-3 text-right">Actions</th></tr></thead><tbody className="divide-y divide-[var(--color-border)]">{data.clients.map((client) => <tr key={client.id} className={cn('cursor-pointer hover:bg-hover-bg/70', detail?.client.id === client.id && 'bg-olive/5')} onClick={() => loadDetail(client.id)}><td className="px-5 py-4"><div className="flex items-center gap-3"><Avatar initials={clientInitials(client.client_name)} variant="filled" /><div><div className="font-bold text-[var(--color-brand-navy)]">{client.client_name}</div><div className="text-xs text-gray-400">{client.website || client.contact_email || 'No contact yet'}</div></div></div></td><td className="px-5 py-4">{client.industry || '-'}</td><td className="px-5 py-4"><Badge variant={clientStatusVariant(client.status)}>{labelize(client.status)}</Badge></td><td className="px-5 py-4"><Badge variant="neutral">{client.onboarding_stage}</Badge></td><td className="px-5 py-4"><div className="flex items-center gap-2"><div className="h-2 w-28 rounded-full bg-olive/10"><div className="h-2 rounded-full bg-olive" style={{ width: `${client.progress_percent}%` }} /></div><span className="text-xs font-bold text-gray-500">{client.progress_percent}%</span></div></td><td className="px-5 py-4">{client.owner_name}</td><td className="px-5 py-4">{formatDate(client.target_go_live_date)}</td><td className="px-5 py-4 text-right"><Button size="sm" variant="ghost" onClick={(event) => { event.stopPropagation(); loadDetail(client.id); }}>View / Edit</Button></td></tr>)}</tbody></table></div>}
      </Card>
      {detail && <ClientDetailSection detail={detail} activeTab={activeTab} setActiveTab={setActiveTab} employeeOptions={employeeOptions} onEdit={() => setClientForm(detail)} updateDetail={updateDetail} setQuickForm={setQuickForm} />}
      {(clientForm === 'new' || clientForm) && <ClientFormDrawer client={clientForm === 'new' ? null : clientForm} employees={data.employees} stages={data.stages} currentUserId={user?.id} onClose={() => setClientForm(null)} onSave={saveClient} saving={savingClient} />}
      {quickForm && <ClientQuickModal title={quickForm.title} fields={quickForm.fields} onClose={() => setQuickForm(null)} onSave={(payload) => { const endpoint = quickForm.type === 'task' ? '/tasks' : quickForm.type === 'team' ? '/team' : quickForm.type === 'document' ? '/documents' : '/milestones'; updateDetail(endpoint, 'POST', payload, `${quickForm.title} saved.`); setQuickForm(null); }} />}
    </div>
  );
}

function ClientDetailSection({ detail, activeTab, setActiveTab, employeeOptions, onEdit, updateDetail, setQuickForm }: { detail: ClientDetail; activeTab: string; setActiveTab: (tab: string) => void; employeeOptions: Array<{ value: string; label: string }>; onEdit: () => void; updateDetail: (url: string, method: string, payload?: Record<string, unknown>, message?: string) => void; setQuickForm: (form: null | { type: string; title: string; fields: Array<{ key: string; label: string; type?: string; options?: Array<{ value: string; label: string }> }> }) => void }) {
  return <Card className="overflow-hidden"><div className="border-b border-[var(--color-border)] p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div className="flex items-center gap-3"><Avatar initials={clientInitials(detail.client.client_name)} size="lg" variant="filled" /><div><div className="text-xl font-bold text-[var(--color-brand-navy)]">{detail.client.client_name}</div><div className="text-sm text-gray-500">{detail.client.industry || 'Industry not set'} - {detail.client.owner_name}</div></div></div><Button size="sm" variant="ghost" icon={<Pencil size={13} />} onClick={onEdit}>Edit Client</Button></div><div className="mt-5 grid gap-3 md:grid-cols-4"><MiniMetric label="Status" value={labelize(detail.client.status)} /><MiniMetric label="Stage" value={detail.onboarding.stage} /><MiniMetric label="Progress" value={`${detail.onboarding.progress_percent}%`} /><MiniMetric label="Target Go-Live" value={formatDate(detail.onboarding.target_go_live_date)} /></div></div><div className="flex gap-1 overflow-x-auto border-b border-[var(--color-border)] p-2">{clientTabs.map((tab) => <button key={tab} onClick={() => setActiveTab(tab)} className={cn('rounded-lg px-3 py-2 text-xs font-bold', activeTab === tab ? 'bg-olive text-white' : 'text-gray-500 hover:bg-hover-bg')}>{tab}</button>)}</div><div className="p-5">
    {activeTab === 'Overview' && <div className="grid gap-4 lg:grid-cols-3"><InfoBlock title="Client Information" rows={[['Client', detail.client.client_name], ['Industry', detail.client.industry || '-'], ['Website', detail.client.website || '-']]} /><InfoBlock title="Contact Information" rows={[['Primary Contact', detail.client.primary_contact_name || '-'], ['Email', detail.client.contact_email || '-'], ['Phone', detail.client.contact_phone || '-']]} /><InfoBlock title="Contract & Audit" rows={[['Contract', `${formatDate(detail.client.contract_start_date)} - ${formatDate(detail.client.contract_end_date)}`], ['Created', formatDateTime(detail.client.created_at)], ['Updated', formatDateTime(detail.client.updated_at)]]} /><div className="lg:col-span-3 rounded-xl border border-[var(--color-border)] bg-warm-bg p-4 text-sm"><div className="mb-1 font-bold text-[var(--color-brand-navy)]">Notes</div><div className="text-gray-600">{detail.client.notes || 'No notes added.'}</div></div></div>}
    {activeTab === 'Checklist' && <div className="grid gap-3 md:grid-cols-2">{detail.checklist.map((item) => <div key={item.id} className="rounded-xl border border-[var(--color-border)] p-4"><label className="flex items-center gap-2 font-bold"><input type="checkbox" checked={item.is_complete} onChange={(event) => updateDetail(`/checklist/${item.id}`, 'PUT', { is_complete: event.target.checked, owner_id: item.owner_id, due_date: item.due_date, notes: item.notes }, 'Checklist updated.')} className="h-4 w-4 accent-olive" />{item.title}</label><div className="mt-3 grid gap-2 md:grid-cols-2"><select value={item.owner_id || ''} onChange={(event) => updateDetail(`/checklist/${item.id}`, 'PUT', { owner_id: event.target.value, is_complete: item.is_complete, due_date: item.due_date, notes: item.notes }, 'Checklist owner updated.')} className="rounded-lg border border-[var(--color-border)] bg-warm-bg px-2 py-2 text-xs">{employeeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select><input type="date" value={item.due_date || ''} onChange={(event) => updateDetail(`/checklist/${item.id}`, 'PUT', { due_date: event.target.value, is_complete: item.is_complete, owner_id: item.owner_id, notes: item.notes }, 'Checklist due date updated.')} className="rounded-lg border border-[var(--color-border)] bg-warm-bg px-2 py-2 text-xs" /></div></div>)}</div>}
    {activeTab === 'Tasks' && <CrudList rows={detail.tasks} onAdd={() => setQuickForm({ type: 'task', title: 'Add Task', fields: [{ key: 'title', label: 'Task Title' }, { key: 'description', label: 'Description' }, { key: 'assigned_to_id', label: 'Assigned To', options: employeeOptions }, { key: 'priority', label: 'Priority', options: ['Low', 'Medium', 'High'].map((v) => ({ value: apiValue(v), label: v })) }, { key: 'status', label: 'Status', options: ['Not Started', 'In Progress', 'Blocked', 'Completed'].map((v) => ({ value: apiValue(v), label: v })) }, { key: 'due_date', label: 'Due Date', type: 'date' }] })} render={(row) => <div><b>{row.title}</b><div className="text-xs text-gray-500">{labelize(row.status)} - {labelize(row.priority)} - {row.assigned_to_name || 'Unassigned'} - Due {formatDate(row.due_date)}</div>{row.due_date && row.status !== 'completed' && new Date(`${row.due_date}T00:00:00`) < new Date(new Date().toDateString()) && <Badge variant="error">Overdue</Badge>}</div>} onDelete={(row) => updateDetail(`/tasks/${row.id}`, 'DELETE', undefined, 'Task deleted.')} />}
    {activeTab === 'Team' && <CrudList rows={detail.team} onAdd={() => setQuickForm({ type: 'team', title: 'Assign Team Member', fields: [{ key: 'employee_id', label: 'Employee', options: employeeOptions.filter((option) => option.value) }, { key: 'role', label: 'Role', options: teamRoles.map((v) => ({ value: apiValue(v), label: v })) }, { key: 'notes', label: 'Notes' }] })} render={(row) => <div><b>{row.employee_name}</b><div className="text-xs text-gray-500">{labelize(row.role)} - {row.notes || '-'}</div></div>} onDelete={(row) => updateDetail(`/team/${row.id}`, 'DELETE', undefined, 'Team member removed.')} />}
    {activeTab === 'Documents' && <CrudList rows={detail.documents} onAdd={() => setQuickForm({ type: 'document', title: 'Attach Document', fields: [{ key: 'document_type', label: 'Document Type', options: documentTypes.map((v) => ({ value: apiValue(v), label: v })) }, { key: 'file_name', label: 'File Name' }, { key: 'file_url', label: 'File URL' }, { key: 'notes', label: 'Notes' }] })} render={(row) => <div><b>{row.file_name}</b><div className="text-xs text-gray-500">{labelize(row.document_type)} - {row.uploaded_by_name || '-'}</div></div>} onDelete={(row) => updateDetail(`/documents/${row.id}`, 'DELETE', undefined, 'Document removed.')} />}
    {activeTab === 'Milestones' && <CrudList rows={detail.milestones} onAdd={() => setQuickForm({ type: 'milestone', title: 'Add Milestone', fields: [{ key: 'milestone_name', label: 'Milestone Name' }, { key: 'target_date', label: 'Target Date', type: 'date' }, { key: 'actual_date', label: 'Actual Date', type: 'date' }, { key: 'status', label: 'Status', options: ['Not Started', 'In Progress', 'Blocked', 'Completed', 'Approved'].map((v) => ({ value: apiValue(v), label: v })) }] })} render={(row) => <div><b>{row.milestone_name}</b><div className="text-xs text-gray-500">{labelize(row.status)} - Target {formatDate(row.target_date)} - Actual {formatDate(row.actual_date)}</div></div>} onDelete={(row) => updateDetail(`/milestones/${row.id}`, 'DELETE', undefined, 'Milestone deleted.')} />}
    {activeTab === 'Activity' && (detail.activity.length === 0 ? <EmptyState message="No activity yet." /> : <div className="grid gap-3">{detail.activity.map((row) => <div key={row.id} className="rounded-xl border border-[var(--color-border)] p-4 text-sm"><div className="font-bold text-[var(--color-brand-navy)]">{row.action}</div><div className="text-gray-500">{row.details || 'No details'} - {row.performed_by_name} - {formatDateTime(row.created_at)}</div></div>)}</div>)}
  </div></Card>;
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg p-3"><div className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</div><div className="mt-1 font-bold text-[var(--color-brand-navy)]">{value}</div></div>;
}

function InfoBlock({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return <div className="rounded-xl border border-[var(--color-border)] p-4"><div className="mb-3 font-bold text-[var(--color-brand-navy)]">{title}</div><div className="grid gap-2 text-sm">{rows.map(([label, value]) => <div key={label} className="flex justify-between gap-3"><span className="text-gray-500">{label}</span><span className="text-right font-semibold text-[var(--color-brand-navy)]">{value}</span></div>)}</div></div>;
}

function CrudList<T extends { id: string }>({ rows, render, onAdd, onDelete }: { rows: T[]; render: (row: T) => React.ReactNode; onAdd: () => void; onDelete?: (row: T) => void }) {
  return (
    <div>
      <div className="mb-3 flex justify-end"><Button size="sm" icon={<Plus size={13} />} onClick={onAdd}>Add</Button></div>
      {rows.length === 0 ? <EmptyState message="No records yet." /> : <div className="grid gap-2">{rows.map((row) => <div key={row.id} className="flex items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] p-3 text-sm"><div>{render(row)}</div>{onDelete && <button onClick={() => onDelete(row)} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg hover:text-status-error"><Trash2 size={15} /></button>}</div>)}</div>}
    </div>
  );
}

export function TimeOffPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState('overview');
  const [data, setData] = useState<TimeOffData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState('');
  const [attendanceFilters, setAttendanceFilters] = useState({ date: '', employee: 'All', status: 'All' });
  const [balanceEmployee, setBalanceEmployee] = useState<EmployeeBalanceGroup | null>(null);
  const [attendanceEdit, setAttendanceEdit] = useState<AttendanceRow | null>(null);
  const [pendingDecision, setPendingDecision] = useState<PendingDecision | null>(null);

  const role = (user?.role || '').toLowerCase().replace(/\s+/g, '_');
  const canAdmin = ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(role);
  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': role,
    'x-user-name': user?.name || '',
  }), [role, user]);

  const loadData = useCallback(async () => {
    if (!user || !canAdmin) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/admin/time-off/dashboard`, { headers });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || 'Could not load Time Off & Attendance data.');
      setData(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load Time Off & Attendance data.');
    } finally {
      setLoading(false);
    }
  }, [canAdmin, headers, user]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const requestedTab = searchParams.get('tab');
    if (requestedTab && timeOffTabs.some((tab) => tab.key === requestedTab)) {
      setActiveTab(requestedTab);
    }
  }, [searchParams]);

  const requestDecision = (url: string, decision: 'approve' | 'reject', label: string) => {
    setPendingDecision({ url, decision, label });
  };

  const runDecision = async (pending: PendingDecision, reason: string) => {
    setActionLoading(`${pending.url}-${pending.decision}`);
    try {
      const res = await fetch(`${API_BASE}${pending.url}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ decision: pending.decision, reason: reason.trim() || null }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || 'Action failed.');
      setData(body);
      setPendingDecision(null);
      showToast({ message: `${pending.label} ${pending.decision === 'approve' ? 'approved' : 'rejected'}.` });
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Action failed.' });
    } finally {
      setActionLoading('');
    }
  };

  const exportReport = async (report: string) => {
    try {
      const month = new Date().toISOString().slice(0, 7);
      const res = await fetch(`${API_BASE}/admin/time-off/reports/${report}/csv?month=${month}`, { headers });
      if (!res.ok) throw new Error('Could not export report.');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `reknew-${report}-${month}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not export report.' });
    }
  };

  const openMetricDetails = (label: string) => {
    const today = localDateInput();
    if (label === 'Pending Leave Requests' || label === 'Leave requests waiting') {
      setActiveTab('leave');
      return;
    }
    if (label === 'Pending Attendance Corrections' || label === 'Attendance corrections waiting') {
      setActiveTab('corrections');
      return;
    }
    if (label === 'Pending Timesheet Approvals' || label === 'Timesheets waiting') {
      setActiveTab('timesheets');
      return;
    }
    const attendanceStatusByLabel: Record<string, string> = {
      'Today Present': 'present',
      'Employees absent today': 'absent',
      Absent: 'absent',
      'Late Arrivals': 'late',
      WFH: 'wfh',
      'Checked Out': 'checked_out',
    };
    const status = attendanceStatusByLabel[label];
    if (status) {
      setAttendanceFilters({ date: today, employee: 'All', status });
      setActiveTab('attendance');
    }
  };

  if (!canAdmin) {
    return (
      <div className="animate-fade-up">
        <h1 className="mb-1 text-2xl font-bold text-[var(--color-brand-navy)]">Time Off & Attendance</h1>
        <p className="mb-6 text-sm text-gray-500">Admin access required.</p>
        <Card className="p-6 text-sm text-status-error">Only Super Admin and HR roles can access this page.</Card>
      </div>
    );
  }

  const filteredAttendance = (data?.attendance_logs || []).filter((row) => {
    if (attendanceFilters.date && row.date !== attendanceFilters.date) return false;
    if (attendanceFilters.employee !== 'All' && row.employee_id !== attendanceFilters.employee) return false;
    if (attendanceFilters.status !== 'All' && row.status !== attendanceFilters.status) return false;
    return true;
  });

  return (
    <div className="animate-fade-up">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Time Off & Attendance</h1>
          <p className="text-sm text-gray-500">Track attendance, manage leave approvals, corrections, timesheets, reports, and policies.</p>
        </div>
        <Button variant="ghost" icon={<RefreshCw size={15} />} disabled={loading} onClick={loadData}>Refresh</Button>
      </div>

      {error && <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metricCards(data?.overview).map((metric) => (
          <Card
            key={metric.label}
            role="button"
            tabIndex={0}
            onClick={() => !loading && openMetricDetails(metric.label)}
            onKeyDown={(event) => {
              if (!loading && (event.key === 'Enter' || event.key === ' ')) {
                event.preventDefault();
                openMetricDetails(metric.label);
              }
            }}
            className="cursor-pointer p-4 transition hover:-translate-y-0.5 hover:border-[var(--color-brand-orange)]/40 hover:shadow-card-md focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-orange)]/20"
          >
            <div className="mb-3 flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-olive/10 text-olive">{metric.icon}</div>
              <span className="text-[11px] font-semibold uppercase text-gray-400">{metric.meta}</span>
            </div>
            <div className="text-2xl font-bold text-[var(--color-brand-navy)]">{loading ? '-' : metric.value}</div>
            <div className="mt-1 text-xs font-medium text-gray-500">{metric.label}</div>
          </Card>
        ))}
      </div>

      <div className="mb-4 flex gap-2 overflow-x-auto rounded-xl border border-[var(--color-border)] bg-white p-1">
        {timeOffTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn('whitespace-nowrap rounded-lg px-3 py-2 text-[13px] font-semibold transition-colors', activeTab === tab.key ? 'bg-olive text-white' : 'text-gray-500 hover:bg-hover-bg')}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Card className="p-8 text-center text-sm text-gray-500">Loading Time Off & Attendance...</Card>
      ) : !data ? (
        <Card className="p-8 text-center text-sm text-gray-500">No data available.</Card>
      ) : (
        <>
          {activeTab === 'overview' && <OverviewSection data={data} onOpenQueue={openMetricDetails} />}
          {activeTab === 'leave' && <LeaveRequestsSection rows={data.leave_requests} onDecision={requestDecision} actionLoading={actionLoading} />}
          {activeTab === 'balances' && <LeaveBalancesSection rows={data.leave_balances} employees={data.employees} onOpen={setBalanceEmployee} />}
          {activeTab === 'attendance' && (
            <AttendanceLogsSection
              rows={filteredAttendance}
              employees={data.employees}
              filters={attendanceFilters}
              setFilters={setAttendanceFilters}
              onEdit={setAttendanceEdit}
            />
          )}
          {activeTab === 'corrections' && <CorrectionsSection rows={data.corrections} onDecision={requestDecision} actionLoading={actionLoading} />}
          {activeTab === 'timesheets' && <TimesheetsAdminSection rows={data.timesheets} onDecision={requestDecision} actionLoading={actionLoading} />}
          {activeTab === 'reports' && <ReportsSection onExport={exportReport} />}
          {activeTab === 'policies' && <PoliciesSection data={data} />}
        </>
      )}

      {balanceEmployee && (
        <BalanceDrawer
          group={balanceEmployee}
          headers={headers}
          onClose={() => setBalanceEmployee(null)}
          onSaved={(next) => {
            setData(next);
            const nextGroup = buildBalanceGroups(next.leave_balances, next.employees).find((group) => group.employee_id === balanceEmployee.employee_id);
            setBalanceEmployee(nextGroup || null);
            showToast({ message: 'Leave balance adjusted.' });
          }}
          onError={(message) => showToast({ message })}
        />
      )}
      {attendanceEdit && (
        <AttendanceModal
          row={attendanceEdit}
          headers={headers}
          onClose={() => setAttendanceEdit(null)}
          onSaved={(next) => {
            setData(next);
            setAttendanceEdit(null);
            showToast({ message: 'Attendance record updated.' });
          }}
          onError={(message) => showToast({ message })}
        />
      )}
      {pendingDecision && (
        <DecisionModal
          decision={pendingDecision}
          loading={!!actionLoading}
          onClose={() => setPendingDecision(null)}
          onConfirm={(note) => runDecision(pendingDecision, note)}
        />
      )}
    </div>
  );
}

export function TeamAllocationPage() {
  return (
    <PlaceholderPage
      title="Team Allocation"
      description="View and manage team allocations across projects and departments."
    />
  );
}

export function AssetsPage() {
  return (
    <PlaceholderPage
      title="Assets & Access"
      description="Manage hardware assets, software licenses, and access permissions."
    />
  );
}

export function UserManagementPage() {
  return (
    <PlaceholderPage
      title="User Management"
      description="Manage portal users, roles, and access levels."
    />
  );
}

export function RolesPage() {
  return (
    <PlaceholderPage
      title="Roles & Permissions"
      description="Configure role-based access control and permission sets."
    />
  );
}

export function PoliciesPage() {
  return (
    <PlaceholderPage
      title="Policies"
      description="Create and manage organizational policies and guidelines."
    />
  );
}

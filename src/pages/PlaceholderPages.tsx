import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, BarChart3, CalendarCheck, CalendarClock, CheckCircle2, Clock3,
  ChevronLeft, ChevronRight, Download, FileText, Pencil, RefreshCw, Search, ShieldCheck,
  UserCheck, UserX, X,
} from 'lucide-react';
import { Badge, Button, Card, CardHeader } from '@/components/ui';
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
        <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">
          {title}
        </h1>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
      <Card className="flex items-center justify-center py-32">
        <div className="text-center">
          <div className="text-4xl mb-3">🚀</div>
          <div className="text-lg font-semibold text-[#2F3437] mb-1">
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

const API_BASE = 'http://localhost:8000/api/v1';

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

function OverviewSection({ data }: { data: TimeOffData }) {
  const recent = data.leave_requests.slice(0, 5);
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="overflow-hidden">
        <CardHeader title="Recent Leave Activity" icon={<CalendarCheck size={17} />} />
        {recent.length ? recent.map((row) => (
          <div key={row.id} className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-3 last:border-b-0">
            <div>
              <div className="text-sm font-bold text-[#2F3437]">{row.employee_name}</div>
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
          <div key={label} className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-3 last:border-b-0">
            <span className="text-sm font-semibold text-[#2F3437]">{label}</span>
            <span className="text-lg font-bold text-olive">{value}</span>
          </div>
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
            <tbody className="divide-y divide-[#E5E7EB]">
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
      <div className="grid gap-3 border-b border-[#E5E7EB] px-5 py-4 xl:grid-cols-[1fr_auto_auto_auto_auto]">
        <label className="relative min-w-[240px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search employee..."
            className="h-10 w-full rounded-lg border border-[#E5E7EB] bg-warm-bg pl-9 pr-3 text-sm outline-none focus:border-olive"
          />
        </label>
        <select value={department} onChange={(event) => setDepartment(event.target.value)} className="h-10 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm outline-none focus:border-olive">
          {departments.map((item) => <option key={item} value={item}>{item === 'All' ? 'Department: All' : item}</option>)}
        </select>
        <select value={leaveType} onChange={(event) => setLeaveType(event.target.value)} className="h-10 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm outline-none focus:border-olive">
          {leaveTypes.map((item) => <option key={item} value={item}>{item === 'All' ? 'Leave Type: All' : item}</option>)}
        </select>
        <label className="flex h-10 items-center gap-2 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm font-semibold text-[#5F6F5A]">
          <input type="checkbox" checked={lowBalance} onChange={(event) => setLowBalance(event.target.checked)} className="h-4 w-4 accent-olive" />
          Low balance
        </label>
        <select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))} className="h-10 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm outline-none focus:border-olive">
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
            <tbody className="divide-y divide-[#E5E7EB]">
              {visible.map((group) => (
                <tr key={group.employee_id} className="align-top">
                  <td className="px-5 py-4">
                    <div className="font-bold text-[#2F3437]">{group.employee_name}</div>
                    <div className="text-xs text-gray-400">{group.balances.length} leave types</div>
                  </td>
                  <td className="px-5 py-4 text-gray-600">{group.department}</td>
                  <td className="px-5 py-3">
                    <div className="flex max-w-[760px] flex-wrap gap-2">
                      {group.balances.map((balance) => {
                        const isLow = Number(balance.available_days || 0) <= 2 && Number(balance.total_days || 0) > 0;
                        return (
                          <span key={balance.id} className={cn('rounded-full border px-2.5 py-1 text-xs font-semibold', isLow ? 'border-status-warning/30 bg-status-warning/10 text-status-warning' : 'border-olive/15 bg-olive/5 text-[#5F6F5A]')}>
                            {compactLeaveName(balance.leave_type)}: <span className="text-[#2F3437]">{formatBalanceNumber(balance.available_days)}/{formatBalanceNumber(balance.total_days)}</span>
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
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#E5E7EB] px-5 py-3 text-sm text-gray-500">
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
      <div className="flex flex-wrap gap-2 border-b border-[#E5E7EB] px-5 py-3">
        <input type="date" value={filters.date} onChange={(event) => setFilters({ ...filters, date: event.target.value })} className="rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2 text-sm outline-none" />
        <select value={filters.employee} onChange={(event) => setFilters({ ...filters, employee: event.target.value })} className="rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2 text-sm outline-none">
          <option value="All">All Employees</option>{employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}
        </select>
        <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })} className="rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2 text-sm outline-none">
          {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
        </select>
      </div>
      {rows.length === 0 ? <EmptyState message="No attendance records match the filters." /> : (
        <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400"><tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Date</th><th className="px-5 py-3 text-left">Check In</th><th className="px-5 py-3 text-left">Check Out</th><th className="px-5 py-3 text-left">Hours</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-right">Action</th></tr></thead><tbody className="divide-y divide-[#E5E7EB]">{rows.map((row) => <tr key={row.id}><td className="px-5 py-3 font-semibold">{row.employee_name}</td><td className="px-5 py-3">{formatDate(row.date)}</td><td className="px-5 py-3">{formatDateTime(row.check_in)}</td><td className="px-5 py-3">{formatDateTime(row.check_out)}</td><td className="px-5 py-3">{row.total_hours || 0}h</td><td className="px-5 py-3"><Badge variant={statusVariant(row.status)}>{row.status}</Badge></td><td className="px-5 py-3 text-right"><Button size="sm" variant="ghost" icon={<Pencil size={13} />} onClick={() => onEdit(row)}>Correct</Button></td></tr>)}</tbody></table></div>
      )}
    </Card>
  );
}

function CorrectionsSection({ rows, onDecision, actionLoading }: { rows: CorrectionRow[]; onDecision: (url: string, decision: 'approve' | 'reject', label: string) => void; actionLoading: string }) {
  return (
    <Card className="overflow-hidden"><CardHeader title="Attendance Corrections" icon={<Pencil size={17} />} />{rows.length === 0 ? <EmptyState message="No correction requests found." /> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400"><tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Date</th><th className="px-5 py-3 text-left">Requested</th><th className="px-5 py-3 text-left">Reason</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-right">Action</th></tr></thead><tbody className="divide-y divide-[#E5E7EB]">{rows.map((row) => <tr key={row.id}><td className="px-5 py-3 font-semibold">{row.employee_name}</td><td className="px-5 py-3">{formatDate(row.attendance_date)}</td><td className="px-5 py-3">{formatDateTime(row.requested_check_in)} - {formatDateTime(row.requested_check_out)}</td><td className="max-w-[260px] truncate px-5 py-3 text-gray-500">{row.reason}</td><td className="px-5 py-3"><Badge variant={statusVariant(row.status)}>{row.status}</Badge></td><td className="px-5 py-3 text-right">{row.status === 'pending' ? <ActionButtons disabled={!!actionLoading} onApprove={() => onDecision(`/admin/time-off/corrections/${row.id}/decision`, 'approve', 'Attendance correction')} onReject={() => onDecision(`/admin/time-off/corrections/${row.id}/decision`, 'reject', 'Attendance correction')} /> : <span className="text-xs text-gray-400">Reviewed</span>}</td></tr>)}</tbody></table></div>}</Card>
  );
}

function TimesheetsAdminSection({ rows, onDecision, actionLoading }: { rows: TimesheetAdminRow[]; onDecision: (url: string, decision: 'approve' | 'reject', label: string) => void; actionLoading: string }) {
  return (
    <Card className="overflow-hidden"><CardHeader title="Timesheets" icon={<FileText size={17} />} />{rows.length === 0 ? <EmptyState message="No submitted or reviewed timesheets found." /> : <div className="overflow-x-auto"><table className="w-full min-w-[960px] text-sm"><thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400"><tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Week</th><th className="px-5 py-3 text-left">Working</th><th className="px-5 py-3 text-left">Break</th><th className="px-5 py-3 text-left">Overtime</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-right">Action</th></tr></thead><tbody className="divide-y divide-[#E5E7EB]">{rows.map((row) => <tr key={`${row.employee_id}-${row.week_start}`}><td className="px-5 py-3 font-semibold">{row.employee_name}</td><td className="px-5 py-3">{formatDate(row.week_start)} - {formatDate(row.week_end)}<details className="mt-1 text-xs text-gray-500"><summary className="cursor-pointer text-olive">Details</summary>{row.entries.slice(0, 8).map((entry, idx) => <div key={idx}>{formatDate(entry.date)} · {entry.code} · {entry.project} · {entry.hours}h</div>)}</details></td><td className="px-5 py-3">{row.working_hours}h</td><td className="px-5 py-3">{row.break_hours}h</td><td className="px-5 py-3">{row.overtime_hours}h</td><td className="px-5 py-3"><Badge variant={statusVariant(row.status)}>{row.status}</Badge></td><td className="px-5 py-3 text-right">{row.status === 'submitted' ? <ActionButtons disabled={!!actionLoading} onApprove={() => onDecision(`/admin/time-off/timesheets/${row.employee_id}/${row.week_start}/decision`, 'approve', 'Timesheet')} onReject={() => onDecision(`/admin/time-off/timesheets/${row.employee_id}/${row.week_start}/decision`, 'reject', 'Timesheet')} /> : <span className="text-xs text-gray-400">Reviewed</span>}</td></tr>)}</tbody></table></div>}</Card>
  );
}

function ReportsSection({ onExport }: { onExport: (report: string) => void }) {
  const reports = [
    ['attendance', 'Monthly Attendance Report', 'Daily check-in, check-out, status, and hours.'],
    ['leave', 'Leave Usage Report', 'Approved, rejected, and pending leave usage.'],
    ['overtime', 'Overtime Report', 'Overtime hours and approval status.'],
    ['absenteeism', 'Absenteeism Report', 'Absent-day summary by employee.'],
  ];
  return <div className="grid gap-3 md:grid-cols-2">{reports.map(([key, title, description]) => <Card key={key} className="p-5"><div className="mb-2 text-sm font-bold text-[#2F3437]">{title}</div><div className="mb-4 text-sm text-gray-500">{description}</div><Button variant="ghost" icon={<Download size={14} />} onClick={() => onExport(key)}>Export CSV</Button></Card>)}</div>;
}

function PoliciesSection({ data }: { data: TimeOffData }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="overflow-hidden"><CardHeader title="Leave Policies" icon={<ShieldCheck size={17} />} action={<a href="/admin/policies" className="text-xs font-bold text-olive">Manage Policies</a>} />{data.policies.map((policy) => <div key={policy.id} className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-3 last:border-b-0"><div><div className="text-sm font-bold text-[#2F3437]">{policy.name} ({policy.code})</div><div className="text-xs text-gray-500">{policy.default_days} days · {policy.paid ? 'Paid' : 'Unpaid'} · {policy.carry_forward ? `Carry forward up to ${policy.max_carry_forward}` : 'No carry forward'}</div></div><Badge variant={policy.active ? 'success' : 'neutral'}>{policy.active ? 'active' : 'inactive'}</Badge></div>)}</Card>
      <Card className="overflow-hidden"><CardHeader title="Attendance Policies" icon={<Clock3 size={17} />} />{data.attendance_policies.map((policy) => <div key={policy.name} className="border-b border-[#E5E7EB] px-5 py-3 last:border-b-0"><div className="text-sm font-bold text-[#2F3437]">{policy.name}</div><div className="text-xs text-gray-500">{policy.value}</div></div>)}</Card>
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
    <div className="fixed inset-0 z-[100] flex justify-end bg-[#111827]/40 backdrop-blur-sm">
      <button aria-label="Close leave balance drawer" className="absolute inset-0 cursor-default" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-4xl flex-col border-l border-[#E5E7EB] bg-white shadow-[0_24px_90px_rgba(17,24,39,0.30)]">
        <div className="flex items-start justify-between border-b border-[#E5E7EB] px-6 py-5">
          <div>
            <div className="text-xl font-bold text-[#2F3437]">Leave Balance</div>
            <div className="mt-1 text-sm text-gray-500">{group.employee_name} · {group.department}</div>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="grid gap-3 border-b border-[#E5E7EB] bg-warm-bg/60 px-6 py-4 sm:grid-cols-3">
          <div className="rounded-xl border border-[#E5E7EB] bg-white p-4">
            <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Leave Types</div>
            <div className="mt-1 text-2xl font-bold text-[#2F3437]">{group.balances.length}</div>
          </div>
          <div className="rounded-xl border border-[#E5E7EB] bg-white p-4">
            <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Total Available</div>
            <div className="mt-1 text-2xl font-bold text-olive">{formatBalanceNumber(group.total_available)}</div>
          </div>
          <div className="rounded-xl border border-[#E5E7EB] bg-white p-4">
            <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Low Balances</div>
            <div className="mt-1 text-2xl font-bold text-[#D9A24E]">{group.balances.filter((balance) => Number(balance.available_days || 0) <= 2 && Number(balance.total_days || 0) > 0).length}</div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          <div className="overflow-hidden rounded-2xl border border-[#E5E7EB]">
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
              <tbody className="divide-y divide-[#E5E7EB]">
                {group.balances.map((balance) => (
                  <tr key={balance.id} className={cn(editing?.id === balance.id && 'bg-olive/5')}>
                    <td className="px-4 py-3 font-bold text-[#2F3437]">{balance.leave_type}</td>
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
                  <div className="text-sm font-bold text-[#2F3437]">Adjust {editing.leave_type}</div>
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
  return <Modal title="Correct Attendance" subtitle={`${row.employee_name} · ${formatDate(row.date)}`} onClose={onClose}><DateTimeField label="Check In" value={form.check_in} onChange={(v) => setForm({ ...form, check_in: v })} /><DateTimeField label="Check Out" value={form.check_out} onChange={(v) => setForm({ ...form, check_out: v })} /><label className="block text-sm font-semibold text-[#2F3437]">Status<select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="mt-1 w-full rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2"><option value="present">Present</option><option value="absent">Absent</option><option value="late">Late</option><option value="wfh">WFH</option><option value="checked_out">Checked Out</option></select></label><TextArea label="Remarks" value={form.remarks} onChange={(v) => setForm({ ...form, remarks: v })} /><TextArea label="Reason" value={form.reason} onChange={(v) => setForm({ ...form, reason: v })} /><div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save}>Save Correction</Button></div></Modal>;
}

function Modal({ title, subtitle, children, onClose }: { title: string; subtitle?: string; children: React.ReactNode; onClose: () => void }) {
  return <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/35 p-4"><div className="w-full max-w-lg rounded-2xl border border-[#E5E7EB] bg-white shadow-[0_24px_80px_rgba(17,24,39,0.25)]"><div className="flex items-start justify-between border-b border-[#E5E7EB] px-5 py-4"><div><div className="text-lg font-bold text-[#2F3437]">{title}</div>{subtitle && <div className="text-sm text-gray-500">{subtitle}</div>}</div><button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button></div><div className="grid gap-3 p-5">{children}</div></div></div>;
}

function NumberField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm font-semibold text-[#2F3437]">{label}<input type="number" min="0" step="0.5" value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2 outline-none focus:border-olive" /></label>;
}

function DateTimeField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm font-semibold text-[#2F3437]">{label}<input type="datetime-local" value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2 outline-none focus:border-olive" /></label>;
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm font-semibold text-[#2F3437]">{label}<textarea value={value} onChange={(e) => onChange(e.target.value)} rows={2} className="mt-1 w-full resize-none rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2 outline-none focus:border-olive" /></label>;
}

export function EmployeesPage() {
  return (
    <PlaceholderPage
      title="Employees"
      description="View, manage, and search the complete employee directory."
    />
  );
}

export function OnboardingPage() {
  return (
    <PlaceholderPage
      title="Onboarding Center"
      description="Track and manage employee onboarding workflows."
    />
  );
}

export function ClientOnboardingPage() {
  return (
    <PlaceholderPage
      title="Client Onboarding"
      description="Manage client onboarding processes and milestones."
    />
  );
}

export function TimeOffPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState('overview');
  const [data, setData] = useState<TimeOffData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState('');
  const [attendanceFilters, setAttendanceFilters] = useState({ date: '', employee: 'All', status: 'All' });
  const [balanceEmployee, setBalanceEmployee] = useState<EmployeeBalanceGroup | null>(null);
  const [attendanceEdit, setAttendanceEdit] = useState<AttendanceRow | null>(null);

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

  const runDecision = async (url: string, decision: 'approve' | 'reject', label: string) => {
    const reason = decision === 'reject' ? window.prompt(`Enter rejection reason for ${label}:`) : window.prompt(`Optional approval note for ${label}:`) || '';
    if (decision === 'reject' && !reason?.trim()) {
      showToast({ message: 'Rejection reason is required.' });
      return;
    }
    setActionLoading(`${url}-${decision}`);
    try {
      const res = await fetch(`${API_BASE}${url}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ decision, reason: reason?.trim() || null }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || 'Action failed.');
      setData(body);
      showToast({ message: `${label} ${decision === 'approve' ? 'approved' : 'rejected'}.` });
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

  if (!canAdmin) {
    return (
      <div className="animate-fade-up">
        <h1 className="mb-1 text-2xl font-bold text-[#2F3437]">Time Off & Attendance</h1>
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
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[#2F3437]">Time Off & Attendance</h1>
          <p className="text-sm text-gray-500">Track attendance, manage leave approvals, corrections, timesheets, reports, and policies.</p>
        </div>
        <Button variant="ghost" icon={<RefreshCw size={15} />} disabled={loading} onClick={loadData}>Refresh</Button>
      </div>

      {error && <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metricCards(data?.overview).map((metric) => (
          <Card key={metric.label} className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-olive/10 text-olive">{metric.icon}</div>
              <span className="text-[11px] font-semibold uppercase text-gray-400">{metric.meta}</span>
            </div>
            <div className="text-2xl font-bold text-[#2F3437]">{loading ? '-' : metric.value}</div>
            <div className="mt-1 text-xs font-medium text-gray-500">{metric.label}</div>
          </Card>
        ))}
      </div>

      <div className="mb-4 flex gap-2 overflow-x-auto rounded-xl border border-[#E5E7EB] bg-white p-1">
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
          {activeTab === 'overview' && <OverviewSection data={data} />}
          {activeTab === 'leave' && <LeaveRequestsSection rows={data.leave_requests} onDecision={runDecision} actionLoading={actionLoading} />}
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
          {activeTab === 'corrections' && <CorrectionsSection rows={data.corrections} onDecision={runDecision} actionLoading={actionLoading} />}
          {activeTab === 'timesheets' && <TimesheetsAdminSection rows={data.timesheets} onDecision={runDecision} actionLoading={actionLoading} />}
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

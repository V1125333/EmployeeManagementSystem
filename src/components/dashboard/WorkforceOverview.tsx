import { useEffect, useMemo, useState, type ElementType } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight, BriefcaseBusiness, CalendarDays, Check, ChevronDown, Clock3,
  FileText, Megaphone, Plus, Send, UserMinus, UsersRound,
} from 'lucide-react';
import { authenticatedFetch } from '@/services/apiClient';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface KpiMetric {
  label: string;
  value: string | number | null | undefined;
  details?: Array<{ employee_id: string; name: string; date: string; subtitle?: string }>;
}

interface PendingTask {
  label: string;
  count: number;
  urgent: number;
}

interface BenchPerson {
  employee_id: string;
  employee_name: string;
  department?: string | null;
  designation?: string | null;
  available_capacity_percentage: number;
}

interface BenchOverview {
  summary?: { on_bench_count?: number };
  on_bench?: BenchPerson[];
}

interface StaffingRequest {
  id: string;
  role_needed: string;
  headcount_needed: number;
  headcount_fulfilled: number;
  priority: string;
  project_name: string;
}

interface DepartmentPoint { dept: string; count: number }
interface AttendancePoint { day: string; rate: number }

interface DashboardData {
  kpis: KpiMetric[];
  tasks: PendingTask[];
  departments: DepartmentPoint[];
  attendance: AttendancePoint[];
  bench: BenchOverview | null;
  staffing: StaffingRequest[];
  announcementCount: number;
}

const emptyData: DashboardData = {
  kpis: [], tasks: [], departments: [], attendance: [], bench: null, staffing: [], announcementCount: 0,
};

function numberValue(value: unknown) {
  const parsed = Number(String(value ?? 0).replace('%', ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toUpperCase() || 'NA';
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <section className={cn('rounded-2xl border border-[#e9e1d5] bg-[#fffefb] shadow-[0_1px_2px_rgba(31,36,48,.025)]', className)}>{children}</section>;
}

function SectionTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-[#eee8de] px-5 py-3.5">
      <h2 className="text-[15px] font-bold tracking-[-.01em] text-[#202431]">{title}</h2>
      {action && <button type="button" onClick={onAction} className="text-[12px] font-bold text-[#c94f13] hover:underline">{action} →</button>}
    </div>
  );
}

function MetricCard({ label, value, detail, progress, action, onAction, avatars }: {
  label: string;
  value: string;
  detail: string;
  progress: number;
  action: string;
  onAction: () => void;
  avatars?: BenchPerson[];
}) {
  return (
    <Card className="min-h-[152px] p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="text-[12px] font-semibold text-[#777987]">{label}</div>
        <button type="button" onClick={onAction} className="inline-flex items-center gap-1 text-[11px] font-bold text-[#c94f13] hover:underline">
          {action}<ArrowRight size={12} />
        </button>
      </div>
      <div className="mt-2.5 flex items-end gap-2">
        <div className="text-[36px] font-bold leading-none tracking-[-.045em] text-[#202431]">{value}</div>
        {avatars?.length ? (
          <div className="mb-0.5 flex -space-x-1.5">
            {avatars.slice(0, 3).map((person, index) => (
              <span key={person.employee_id} className={cn('flex h-7 w-7 items-center justify-center rounded-full border-2 border-[#fffefb] text-[9px] font-bold', index === 0 ? 'bg-[#fff0e5] text-[#a84218]' : index === 1 ? 'bg-[#e8f0fb] text-[#315b91]' : 'bg-[#e8f5eb] text-[#39734b]')}>
                {initials(person.employee_name)}
              </span>
            ))}
            {avatars.length > 3 && <span className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-[#fffefb] bg-[#eeeae3] text-[9px] font-bold text-[#696b75]">+{avatars.length - 3}</span>}
          </div>
        ) : null}
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#eee9e1]">
        <div className="h-full rounded-full bg-[#202431]" style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }} />
      </div>
      <div className="mt-2 text-[11px] text-[#777987]">{detail}</div>
    </Card>
  );
}

const taskRoutes: Record<string, { path: string; description: string; action: string; icon: ElementType }> = {
  'Leave Approvals': { path: '/time-off?tab=leave', description: 'Review submitted leave requests', action: 'Review', icon: CalendarDays },
  'Attendance Corrections': { path: '/time-off?tab=corrections', description: 'Resolve attendance adjustment requests', action: 'Review', icon: Clock3 },
  'Onboarding Tasks': { path: '/onboarding', description: 'Complete new employee setup activities', action: 'Open', icon: UsersRound },
  'Profile Updates': { path: '/employees?filter=profile-updates', description: 'Verify employee profile changes', action: 'Review', icon: FileText },
};

async function jsonOr<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await authenticatedFetch(url);
    if (!response.ok) return fallback;
    return await response.json() as T;
  } catch {
    return fallback;
  }
}

export function WorkforceOverview({ onAddEmployee, onCreateAnnouncement }: { onAddEmployee: () => void; onCreateAnnouncement: () => void }) {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData>(emptyData);

  useEffect(() => {
    let active = true;
    Promise.all([
      jsonOr<{ kpis?: KpiMetric[] }>(`${API_BASE}/dashboard/kpis`, {}),
      jsonOr<{ tasks?: PendingTask[] }>(`${API_BASE}/dashboard/pending-tasks`, {}),
      jsonOr<{ departments?: DepartmentPoint[] }>(`${API_BASE}/dashboard/department-chart`, {}),
      jsonOr<{ trend?: AttendancePoint[] }>(`${API_BASE}/dashboard/attendance-trend`, {}),
      jsonOr<BenchOverview | null>(`${API_BASE}/allocations/bench/overview`, null),
      // The FastAPI collection route is declared at `/staffing-requests/`.
      // Omitting the slash makes FastAPI issue an absolute redirect to the
      // backend origin; browsers then strip the Authorization header while
      // following that cross-origin redirect, producing a misleading 401.
      jsonOr<{ items?: StaffingRequest[] }>(`${API_BASE}/staffing-requests/?page=1&per_page=3`, {}),
      jsonOr<{ announcements?: unknown[] }>(`${API_BASE}/dashboard/announcements`, {}),
    ]).then(([kpis, tasks, departments, attendance, bench, staffing, announcements]) => {
      if (!active) return;
      setData({
        kpis: kpis.kpis || [],
        tasks: tasks.tasks || [],
        departments: departments.departments || [],
        attendance: attendance.trend || [],
        bench,
        staffing: staffing.items || [],
        announcementCount: announcements.announcements?.length || 0,
      });
    });
    return () => { active = false; };
  }, []);

  const metrics = useMemo(() => new Map(data.kpis.map((item) => [item.label, item])), [data.kpis]);
  const total = numberValue(metrics.get('Total Employees')?.value);
  const activeCount = numberValue(metrics.get('Active Employees')?.value);
  const inactiveCount = numberValue(metrics.get('Inactive')?.value);
  const attendanceRate = numberValue(metrics.get("Today's Attendance")?.value);
  const benchCount = data.bench?.summary?.on_bench_count ?? numberValue(metrics.get('Bench Capacity')?.value);
  const allocated = Math.max(0, activeCount - benchCount);
  const allocationRate = activeCount ? Math.round((allocated / activeCount) * 100) : 0;
  const pendingLeave = numberValue(metrics.get('Pending Leave')?.value);
  const attentionItems = data.tasks.filter((task) => task.count > 0);
  const maxDepartment = Math.max(1, ...data.departments.map((item) => item.count));
  const maxAttendance = Math.max(1, ...data.attendance.map((item) => item.rate));

  const upcoming = useMemo(() => {
    const items: Array<{ name: string; date: string; kind: string }> = [];
    for (const label of ['Upcoming Birthdays', 'Work Anniversaries']) {
      const kind = label === 'Upcoming Birthdays' ? 'Birthday' : 'Work anniversary';
      for (const detail of metrics.get(label)?.details || []) items.push({ name: detail.name, date: detail.date, kind });
    }
    return items.sort((a, b) => a.date.localeCompare(b.date)).slice(0, 3);
  }, [metrics]);

  const today = new Date();
  const dateLabel = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  const weekNumber = Math.ceil((((today.getTime() - new Date(today.getFullYear(), 0, 1).getTime()) / 86400000) + new Date(today.getFullYear(), 0, 1).getDay() + 1) / 7);

  return (
    <div className="mx-auto max-w-[1500px]">
      <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <div className="text-[12px] font-semibold text-[#777987]">{dateLabel} · Week {weekNumber}</div>
          <h1 className="mt-1.5 max-w-[680px] text-[30px] font-bold leading-[1.08] tracking-[-.035em] text-[#202431]">
            {greeting()}. Here&apos;s your workforce today.
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => navigate('/notifications')} className="inline-flex h-10 items-center gap-2 rounded-xl border border-[#e2dbcf] bg-[#fffefb] px-4 text-[13px] font-semibold text-[#343745] hover:bg-[#faf6ef]">
            <Megaphone size={15} /> Announce
          </button>
          <button type="button" onClick={onAddEmployee} className="inline-flex h-10 items-center gap-2 rounded-xl bg-[#c94f13] px-5 text-[13px] font-bold text-white shadow-sm hover:bg-[#b94410]">
            <Plus size={16} /> Add employee
          </button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Headcount" value={String(total)} detail={`${activeCount} active · ${inactiveCount} inactive`} progress={total ? (activeCount / total) * 100 : 0} action="Directory" onAction={() => navigate('/employees')} />
        <MetricCard label="Attendance today" value={`${attendanceRate}%`} detail={`${pendingLeave} pending leave request${pendingLeave === 1 ? '' : 's'}`} progress={attendanceRate} action="Attendance" onAction={() => navigate('/time-off?tab=attendance')} />
        <MetricCard label="Allocation" value={`${allocationRate}%`} detail={`${allocated} of ${activeCount} active employees allocated`} progress={allocationRate} action="Allocations" onAction={() => navigate('/team-allocation')} />
        <MetricCard label="Bench" value={String(benchCount)} detail="Available for staffing now" progress={total ? (benchCount / total) * 100 : 0} action="Staff them" onAction={() => navigate('/bench')} avatars={data.bench?.on_bench} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.8fr)_minmax(300px,.9fr)]">
        <Card>
          <SectionTitle title="Needs your attention" action={`${attentionItems.length + (data.announcementCount === 0 ? 1 : 0)} items`} />
          <div className="divide-y divide-[#eee8de] px-4">
            {attentionItems.map((task) => {
              const meta = taskRoutes[task.label] || { path: '/dashboard', description: 'Review this workforce item', action: 'View', icon: FileText };
              const Icon = meta.icon;
              return (
                <div key={task.label} className="flex items-center gap-3 py-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#fff0e5] text-[#c94f13]"><Icon size={16} /></div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-bold text-[#262a36]">{task.count} {task.label.toLowerCase()}</div>
                    <div className="mt-0.5 truncate text-[11px] text-[#777987]">{meta.description}{task.urgent ? ` · ${task.urgent} urgent` : ''}</div>
                  </div>
                  <button type="button" onClick={() => navigate(meta.path)} className="rounded-lg border border-[#e2dbcf] bg-white px-3 py-1.5 text-[11px] font-bold text-[#343745] hover:bg-[#faf6ef]">{meta.action}</button>
                </div>
              );
            })}
            {data.announcementCount === 0 && (
              <div className="flex items-center gap-3 py-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#fff0e5] text-[#c94f13]"><Megaphone size={16} /></div>
                <div className="min-w-0 flex-1"><div className="text-[13px] font-bold text-[#262a36]">No active announcements</div><div className="mt-0.5 text-[11px] text-[#777987]">Keep everyone informed with a company update</div></div>
                <button type="button" onClick={onCreateAnnouncement} className="rounded-lg border border-[#e2dbcf] bg-white px-3 py-1.5 text-[11px] font-bold text-[#343745] hover:bg-[#faf6ef]">Write one</button>
              </div>
            )}
          </div>
          {pendingLeave === 0 && (
            <div className="mx-4 mb-4 flex items-center gap-2 rounded-xl bg-[#edf8ef] px-4 py-2.5 text-[12px] font-semibold text-[#317444]"><Check size={15} /> Leave requests are all caught up.</div>
          )}
        </Card>

        <Card>
          <SectionTitle title="Coming up" action="Calendar" onAction={() => navigate('/employee/holidays')} />
          <div className="min-h-[204px] divide-y divide-[#eee8de] px-4">
            {upcoming.length ? upcoming.map((item) => {
              const date = new Date(`${item.date}T00:00:00`);
              return <div key={`${item.name}-${item.date}`} className="flex items-center gap-3 py-3"><div className="w-11 shrink-0 rounded-xl border border-[#e9e1d5] bg-white py-1 text-center"><div className="text-[9px] font-bold uppercase text-[#c94f13]">{date.toLocaleDateString('en-US', { month: 'short' })}</div><div className="text-[17px] font-bold leading-5 text-[#202431]">{date.getDate()}</div></div><div><div className="text-[13px] font-bold text-[#262a36]">{item.name}</div><div className="text-[11px] text-[#777987]">{item.kind}</div></div></div>;
            }) : <div className="flex min-h-[204px] flex-col items-center justify-center text-center"><CalendarDays size={22} className="text-[#c9c2b7]" /><div className="mt-2 text-[13px] font-semibold text-[#555866]">Nothing scheduled soon</div><div className="mt-1 text-[11px] text-[#8a8b95]">Birthdays and anniversaries will appear here.</div></div>}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1.05fr_.95fr]">
        <Card>
          <SectionTitle title="Headcount by team" />
          <div className="space-y-3 p-5">
            {data.departments.slice(0, 5).map((department) => <div key={department.dept}><div className="mb-1 flex justify-between text-[11px]"><span className="font-semibold text-[#474a56]">{department.dept}</span><span className="text-[#777987]">{department.count}</span></div><div className="h-2 overflow-hidden rounded-full bg-[#f0ebe4]"><div className="h-full rounded-full bg-[#202431]" style={{ width: `${(department.count / maxDepartment) * 100}%` }} /></div></div>)}
            {!data.departments.length && <div className="py-12 text-center text-[12px] text-[#8a8b95]">Department data is unavailable.</div>}
          </div>
        </Card>

        <Card>
          <SectionTitle title="Attendance, last 10 days" />
          <div className="flex h-[190px] items-end gap-2 px-5 pb-5 pt-8">
            {data.attendance.map((point, index) => <div key={`${point.day}-${index}`} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1"><span className="text-[9px] font-semibold text-[#777987]">{point.rate}%</span><div className={cn('w-full max-w-10 rounded-t-md', index === data.attendance.length - 1 ? 'bg-[#ea5b12]' : 'bg-[#e8dfd2]')} style={{ height: `${Math.max(12, (point.rate / maxAttendance) * 112)}px` }} /><span className="max-w-full truncate text-[8px] text-[#8a8b95]">{point.day.replace(' ', '\n')}</span></div>)}
            {!data.attendance.length && <div className="m-auto text-[12px] text-[#8a8b95]">Attendance history is unavailable.</div>}
          </div>
        </Card>

        <Card>
          <SectionTitle title="Ready to staff" action="View all" onAction={() => navigate('/staffing-requests')} />
          <div className="divide-y divide-[#eee8de] px-4">
            {data.staffing.slice(0, 3).map((request, index) => <button type="button" key={request.id} onClick={() => navigate(`/staffing-requests/${request.id}`)} className="flex w-full items-center gap-3 py-3 text-left"><span className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[10px] font-bold', index === 0 ? 'bg-[#fff0e5] text-[#a84218]' : index === 1 ? 'bg-[#e8f0fb] text-[#315b91]' : 'bg-[#e8f5eb] text-[#39734b]')}><BriefcaseBusiness size={14} /></span><span className="min-w-0 flex-1"><span className="block truncate text-[12px] font-bold text-[#262a36]">{request.role_needed}</span><span className="block truncate text-[10px] text-[#777987]">{request.project_name} · {request.priority}</span></span><span className="text-[10px] font-bold text-[#c94f13]">{Math.max(0, request.headcount_needed - request.headcount_fulfilled)} open</span></button>)}
            {!data.staffing.length && <div className="flex min-h-[190px] flex-col items-center justify-center text-center"><UserMinus size={22} className="text-[#c9c2b7]" /><div className="mt-2 text-[12px] font-semibold text-[#555866]">No open staffing requests</div></div>}
          </div>
        </Card>
      </div>

      <Card className="mt-4 p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#fff0e5] text-[#c94f13]"><Megaphone size={16} /></div>
          <button type="button" onClick={onCreateAnnouncement} className="h-10 flex-1 rounded-xl border border-[#e2dbcf] bg-[#fbf8f2] px-4 text-left text-[12px] text-[#8a8b95] hover:border-[#d6c9b8]">Share an update with all {total} people...</button>
          <button type="button" onClick={onCreateAnnouncement} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#e2dbcf] bg-white px-4 text-[12px] font-bold text-[#343745]">Schedule <ChevronDown size={14} /></button>
          <button type="button" onClick={onCreateAnnouncement} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#202431] px-5 text-[12px] font-bold text-white"><Send size={14} /> Post</button>
        </div>
      </Card>
    </div>
  );
}

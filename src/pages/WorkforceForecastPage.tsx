import { useEffect, useMemo, useState } from 'react';
import { CalendarClock, Download, SearchX, TrendingUp } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Avatar, Badge, Button, Card } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface ForecastEmployeeRow {
  employee_id: string;
  employee_name: string;
  department: string | null;
  designation: string | null;
  manager_name: string | null;
  current_allocation_percentage: number;
  current_available_percentage: number;
  forecast_allocation_percentage: number;
  forecast_available_percentage: number;
  next_allocation_end_date: string | null;
  forecast_status: 'becoming_available' | 'partially_available' | 'fully_allocated' | 'fully_available' | 'overallocated' | 'bench_risk';
}

interface ForecastSummary {
  total_employees: number;
  becoming_available_count: number;
  fully_allocated_count: number;
  fully_available_count: number;
  partially_available_count: number;
  bench_risk_count: number;
  overallocated_count: number;
}

interface ForecastBenchRiskRow {
  employee_id: string;
  employee_name: string;
  department: string | null;
  manager_name: string | null;
  date_becoming_available: string | null;
}

interface ForecastProjectImpactRow {
  project: string;
  employee_id: string;
  employee_name: string;
  role: string | null;
  allocation_percentage: number;
  end_date: string;
  days_remaining: number;
}

interface ForecastResponse {
  generated_at: string;
  forecast_window_days: number;
  summary: ForecastSummary;
  employees: ForecastEmployeeRow[];
  bench_risk_employees: ForecastBenchRiskRow[];
  projects_losing_resources_soon: ForecastProjectImpactRow[];
}

function normalizeRole(role?: string) {
  return (role || '').toLowerCase().replace(/\s+/g, '_');
}

function canViewForecast(role?: string) {
  return ['super_admin', 'hr_admin', 'admin', 'global_access', 'manager'].includes(normalizeRole(role));
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
}

function titleCase(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value?: string | null) {
  if (!value) return 'Open-ended';
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function statusVariant(status: ForecastEmployeeRow['forecast_status']): 'info' | 'olive' | 'success' | 'warning' | 'error' | 'neutral' {
  if (status === 'becoming_available') return 'info';
  if (status === 'partially_available') return 'olive';
  if (status === 'fully_allocated') return 'neutral';
  if (status === 'fully_available') return 'success';
  if (status === 'bench_risk') return 'warning';
  return 'error';
}

function AllocationBar({ value }: { value: number }) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-semibold text-[var(--color-brand-navy)]">{value}%</span>
      </div>
      <div className="h-2 w-28 overflow-hidden rounded-full bg-hover-bg">
        <div
          className={cn('h-full rounded-full', value > 100 ? 'bg-status-error' : value >= 100 ? 'bg-olive' : 'bg-sage')}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

function SkeletonBlock() {
  return <div className="h-4 animate-pulse rounded bg-gray-100" />;
}

export function WorkforceForecastPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [windowDays, setWindowDays] = useState('30');
  const [department, setDepartment] = useState('all');
  const [manager, setManager] = useState('all');
  const [designation, setDesignation] = useState('all');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  const headers = useMemo(() => ({
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const loadForecast = async () => {
    if (!user || !canViewForecast(user.role)) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/forecasting?window_days=${windowDays}`, { headers });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Unable to load workforce forecast.');
      setForecast(data);
    } catch (err) {
      setForecast(null);
      setError(err instanceof Error ? err.message : 'Unable to load workforce forecast.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadForecast();
  }, [user?.id, user?.email, user?.role, windowDays]);

  const employees = forecast?.employees || [];
  const departments = useMemo(() => Array.from(new Set(employees.map((row) => row.department).filter(Boolean) as string[])).sort(), [employees]);
  const managers = useMemo(() => Array.from(new Set(employees.map((row) => row.manager_name).filter(Boolean) as string[])).sort(), [employees]);
  const designations = useMemo(() => Array.from(new Set(employees.map((row) => row.designation).filter(Boolean) as string[])).sort(), [employees]);
  const filteredEmployees = useMemo(() => employees.filter((row) => (
    (department === 'all' || row.department === department)
    && (manager === 'all' || row.manager_name === manager)
    && (designation === 'all' || row.designation === designation)
  )), [department, designation, employees, manager]);
  const filteredIds = new Set(filteredEmployees.map((row) => row.employee_id));
  const benchRiskRows = (forecast?.bench_risk_employees || []).filter((row) => filteredIds.has(row.employee_id));
  const projectImpactRows = (forecast?.projects_losing_resources_soon || []).filter((row) => filteredIds.has(row.employee_id));

  const filteredSummary = useMemo(() => ({
    becoming_available_count: filteredEmployees.filter((row) => row.forecast_status === 'becoming_available').length,
    fully_allocated_count: filteredEmployees.filter((row) => row.forecast_status === 'fully_allocated').length,
    fully_available_count: filteredEmployees.filter((row) => row.forecast_status === 'fully_available').length,
    partially_available_count: filteredEmployees.filter((row) => row.forecast_status === 'partially_available').length,
    bench_risk_count: filteredEmployees.filter((row) => row.forecast_status === 'bench_risk').length,
    overallocated_count: filteredEmployees.filter((row) => row.forecast_status === 'overallocated').length,
  }), [filteredEmployees]);

  const exportCsv = async () => {
    if (!user) return;
    setExporting(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/forecasting/export?window_days=${windowDays}`, { headers });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || 'Unable to export workforce forecast.');
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `workforce-forecast-${windowDays}-days.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to export workforce forecast.');
    } finally {
      setExporting(false);
    }
  };

  if (!canViewForecast(user?.role)) {
    return (
      <div>
        <h1 className="mb-1 text-2xl font-bold text-[var(--color-brand-navy)]">Workforce Forecasting</h1>
        <p className="mb-6 text-sm text-gray-500">Forecast employee availability and bench risk.</p>
        <Card className="p-10 text-center">
          <div className="text-[15px] font-semibold text-[var(--color-brand-navy)]">Access restricted</div>
          <div className="mt-1 text-sm text-gray-500">Only Super Admin, HR/Admin, and managers can view workforce forecasting.</div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Workforce Forecasting</h1>
          <p className="text-sm text-gray-500">Forecast employee availability and bench risk.</p>
        </div>
        <Button variant="ghost" icon={<Download size={15} />} disabled={exporting || loading} onClick={exportCsv}>
          {exporting ? 'Exporting' : 'Export CSV'}
        </Button>
      </div>

      {error && (
        <div className="mb-5 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}

      <Card className="mb-5 p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="text-[12px] font-bold text-gray-400">
            Forecast Window
            <select value={windowDays} onChange={(event) => setWindowDays(event.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10">
              <option value="30">30 Days</option>
              <option value="60">60 Days</option>
              <option value="90">90 Days</option>
            </select>
          </label>
          <label className="text-[12px] font-bold text-gray-400">
            Department
            <select value={department} onChange={(event) => setDepartment(event.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10">
              <option value="all">All departments</option>
              {departments.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="text-[12px] font-bold text-gray-400">
            Manager
            <select value={manager} onChange={(event) => setManager(event.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10">
              <option value="all">All managers</option>
              {managers.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="text-[12px] font-bold text-gray-400">
            Designation
            <select value={designation} onChange={(event) => setDesignation(event.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10">
              <option value="all">All designations</option>
              {designations.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>
      </Card>

      <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {[
          ['Becoming Available', filteredSummary.becoming_available_count, 'info'],
          ['Fully Allocated', filteredSummary.fully_allocated_count, 'neutral'],
          ['Fully Available', filteredSummary.fully_available_count, 'success'],
          ['Partially Available', filteredSummary.partially_available_count, 'olive'],
          ['Bench Risk', filteredSummary.bench_risk_count, 'warning'],
          ['Overallocated', filteredSummary.overallocated_count, 'error'],
        ].map(([label, value, tone]) => (
          <Card key={label} className="p-4">
            <div className={cn('mb-3 flex h-9 w-9 items-center justify-center rounded-xl', tone === 'error' ? 'bg-status-error/10 text-status-error' : tone === 'warning' ? 'bg-status-warning/10 text-status-warning' : 'bg-hover-bg text-olive')}>
              <TrendingUp size={17} />
            </div>
            <div className="text-2xl font-bold text-[var(--color-brand-navy)]">{value}</div>
            <div className="text-sm text-gray-500">{label}</div>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <div className="text-[13px] font-bold text-[var(--color-brand-navy)]">Forecast Table</div>
            <div className="text-xs text-gray-500">{filteredEmployees.length} of {forecast?.summary.total_employees || 0} employees</div>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <CalendarClock size={15} />
            Generated {forecast ? new Date(`${forecast.generated_at}Z`).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-'}
          </div>
        </div>

        {loading ? (
          <div className="divide-y divide-[var(--color-border)]">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="grid grid-cols-8 gap-4 px-6 py-5">
                {Array.from({ length: 8 }).map((__, cell) => <SkeletonBlock key={cell} />)}
              </div>
            ))}
          </div>
        ) : filteredEmployees.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-hover-bg text-olive">
              <SearchX size={20} />
            </div>
            <div className="text-[15px] font-semibold text-[var(--color-brand-navy)]">No employees match the selected forecast criteria.</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1200px] text-left">
              <thead className="bg-warm-bg">
                <tr className="text-[11px] font-bold uppercase tracking-wide text-gray-400">
                  <th className="px-5 py-3">Employee</th>
                  <th className="px-4 py-3">Department</th>
                  <th className="px-4 py-3">Designation</th>
                  <th className="px-4 py-3">Manager</th>
                  <th className="px-4 py-3">Current Allocation</th>
                  <th className="px-4 py-3">Forecast Allocation</th>
                  <th className="px-4 py-3">Current Available</th>
                  <th className="px-4 py-3">Forecast Available</th>
                  <th className="px-4 py-3">Next End Date</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredEmployees.map((row) => (
                  <tr key={row.employee_id} className="border-t border-[var(--color-border)] text-[14px] text-[var(--color-brand-navy)]">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <Avatar initials={initials(row.employee_name)} variant="filled" />
                        <div className="font-semibold">{row.employee_name}</div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-gray-600">{row.department || '-'}</td>
                    <td className="px-4 py-4 text-gray-600">{row.designation || '-'}</td>
                    <td className="px-4 py-4 text-gray-600">{row.manager_name || '-'}</td>
                    <td className="px-4 py-4"><AllocationBar value={row.current_allocation_percentage} /></td>
                    <td className="px-4 py-4"><AllocationBar value={row.forecast_allocation_percentage} /></td>
                    <td className="px-4 py-4 font-semibold">{row.current_available_percentage}%</td>
                    <td className="px-4 py-4 font-semibold">{row.forecast_available_percentage}%</td>
                    <td className="px-4 py-4 text-gray-600">{formatDate(row.next_allocation_end_date)}</td>
                    <td className="px-4 py-4"><Badge variant={statusVariant(row.forecast_status)}>{titleCase(row.forecast_status)}</Badge></td>
                    <td className="px-4 py-4"><Button size="sm" variant="ghost" onClick={() => navigate(`/profile?employee_id=${encodeURIComponent(row.employee_id)}&tab=allocations`)}>View</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <Card className="overflow-hidden">
          <div className="border-b border-[var(--color-border)] px-5 py-4">
            <div className="text-[13px] font-bold text-[var(--color-brand-navy)]">Employees Likely To Hit Bench</div>
          </div>
          {benchRiskRows.length === 0 ? (
            <div className="px-5 py-8 text-sm text-gray-500">No bench risk employees in this forecast window.</div>
          ) : (
            <div className="divide-y divide-[var(--color-border)]">
              {benchRiskRows.map((row) => (
                <div key={row.employee_id} className="grid grid-cols-[1fr_120px] gap-3 px-5 py-4 text-sm">
                  <div>
                    <div className="font-semibold text-[var(--color-brand-navy)]">{row.employee_name}</div>
                    <div className="text-gray-500">{row.department || '-'} • {row.manager_name || 'No manager'}</div>
                  </div>
                  <div className="text-right font-semibold text-status-warning">{formatDate(row.date_becoming_available)}</div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="overflow-hidden">
          <div className="border-b border-[var(--color-border)] px-5 py-4">
            <div className="text-[13px] font-bold text-[var(--color-brand-navy)]">Projects Losing Resources Soon</div>
          </div>
          {projectImpactRows.length === 0 ? (
            <div className="px-5 py-8 text-sm text-gray-500">No project resource endings in this forecast window.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[620px] text-left text-sm">
                <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
                  <tr>
                    <th className="px-4 py-3">Project</th>
                    <th className="px-4 py-3">Employee</th>
                    <th className="px-4 py-3">Role</th>
                    <th className="px-4 py-3">Allocation</th>
                    <th className="px-4 py-3">End Date</th>
                    <th className="px-4 py-3">Days</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {projectImpactRows.slice(0, 12).map((row) => (
                    <tr key={`${row.employee_id}-${row.project}-${row.end_date}`}>
                      <td className="px-4 py-3 font-semibold text-[var(--color-brand-navy)]">{row.project}</td>
                      <td className="px-4 py-3 text-gray-600">{row.employee_name}</td>
                      <td className="px-4 py-3 text-gray-600">{row.role || '-'}</td>
                      <td className="px-4 py-3 font-semibold">{row.allocation_percentage}%</td>
                      <td className="px-4 py-3 text-gray-600">{formatDate(row.end_date)}</td>
                      <td className="px-4 py-3"><Badge variant={row.days_remaining <= 15 ? 'warning' : 'info'}>{row.days_remaining}d</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

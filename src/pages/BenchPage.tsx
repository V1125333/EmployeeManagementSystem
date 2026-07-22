import { useEffect, useMemo, useState } from 'react';
import { RefreshCw, SearchX, UserPlus } from 'lucide-react';
import { Avatar, Badge, Button, Card } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { AssignEmployeeModal } from '@/components/projects/AssignEmployeeModal';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface ProjectRecord {
  id: string;
  name: string;
  code: string;
  status?: string;
}

interface BenchEmployee {
  employee_id: string;
  employee_name: string;
  department: string | null;
  designation: string | null;
  profile_image_url: string | null;
  total_active_allocation_percentage: number;
  available_capacity_percentage: number;
  allocation_status: string;
  active_project_names: string[];
  next_available_date: string | null;
}

function normalizeRole(role: string | undefined) {
  return (role || '').toLowerCase().replace(/\s+/g, '_');
}

function canViewBench(role: string | undefined) {
  return ['super_admin', 'hr_admin', 'global_access', 'manager'].includes(normalizeRole(role));
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
}

function formatDate(value: string | null) {
  if (!value) return 'Open-ended';
  return new Date(value).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatStatus(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function availableTone(value: number) {
  if (value >= 50) return 'text-status-success';
  if (value >= 20) return 'text-status-warning';
  return 'text-status-error';
}

function statusVariant(value: string): 'olive' | 'success' | 'warning' | 'error' | 'neutral' | 'info' {
  if (value === 'bench') return 'neutral';
  if (value === 'partially_allocated') return 'info';
  if (value === 'fully_allocated') return 'olive';
  if (value === 'overallocated') return 'error';
  return 'neutral';
}

function projectSummary(projects: string[]) {
  if (projects.length === 0) return 'No active projects';
  if (projects.length <= 2) return projects.join(', ');
  return `${projects.slice(0, 2).join(', ')} +${projects.length - 2} more`;
}

export function BenchPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [rows, setRows] = useState<BenchEmployee[]>([]);
  const [allRows, setAllRows] = useState<BenchEmployee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [department, setDepartment] = useState('all');
  const [designation, setDesignation] = useState('all');
  const [availability, setAvailability] = useState('all');
  const [availableWithin, setAvailableWithin] = useState('any');
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [projectError, setProjectError] = useState('');
  const [selectedEmployee, setSelectedEmployee] = useState<BenchEmployee | null>(null);

  const departments = useMemo(
    () => Array.from(new Set(allRows.map((row) => row.department).filter(Boolean) as string[])).sort(),
    [allRows]
  );
  const designations = useMemo(
    () => Array.from(new Set(allRows.map((row) => row.designation).filter(Boolean) as string[])).sort(),
    [allRows]
  );

  const fetchBench = async (applyFilters = true) => {
    if (!canViewBench(user?.role)) return;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (applyFilters) {
        if (department !== 'all') params.set('department', department);
        if (designation !== 'all') params.set('designation', designation);
        if (availability === 'bench') params.set('max_allocation', '0');
        if (availability === 'partial') params.set('max_allocation', '99');
        if (availability === 'available_50') params.set('max_allocation', '50');
        if (availableWithin !== 'any') params.set('available_within_days', availableWithin);
      }

      const res = await fetch(`${API_BASE}/allocations/bench${params.toString() ? `?${params.toString()}` : ''}`, {
        headers: {
          'x-user-id': user?.id || '',
          'x-user-email': user?.email || '',
          'x-user-role': normalizeRole(user?.role),
        },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Unable to load bench availability.');
      setRows(Array.isArray(data) ? data : []);
    } catch (err) {
      setRows([]);
      setError(err instanceof Error ? err.message : 'Unable to load bench availability.');
    } finally {
      setLoading(false);
    }
  };

  const loadFilterOptions = async () => {
    if (!canViewBench(user?.role)) return;
    try {
      const res = await fetch(`${API_BASE}/allocations/bench`, {
        headers: {
          'x-user-id': user?.id || '',
          'x-user-email': user?.email || '',
          'x-user-role': normalizeRole(user?.role),
        },
      });
      const data = await res.json();
      if (res.ok && Array.isArray(data)) setAllRows(data);
    } catch {
      setAllRows([]);
    }
  };

  const loadProjects = async () => {
    if (!canViewBench(user?.role)) return;
    setProjectError('');
    try {
      const params = new URLSearchParams({ status: 'active', limit: '250' });
      const res = await fetch(`${API_BASE}/projects/?${params.toString()}`, {
        headers: {
          'x-user-id': user?.id || '',
          'x-user-email': user?.email || '',
          'x-user-role': normalizeRole(user?.role),
        },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Unable to load active projects.');
      setProjects(Array.isArray(data.projects) ? data.projects : []);
    } catch (err) {
      setProjects([]);
      setProjectError(err instanceof Error ? err.message : 'Unable to load active projects.');
    }
  };

  useEffect(() => {
    loadFilterOptions();
    loadProjects();
  }, [user?.id, user?.email, user?.role]);

  useEffect(() => {
    fetchBench();
  }, [department, designation, availability, availableWithin, user?.id, user?.email, user?.role]);

  const resetFilters = () => {
    setDepartment('all');
    setDesignation('all');
    setAvailability('all');
    setAvailableWithin('any');
  };

  if (!canViewBench(user?.role)) {
    return (
      <div>
        <h1 className="mb-1 text-2xl font-bold text-[var(--color-brand-navy)]">Bench & Availability</h1>
        <p className="mb-6 text-sm text-gray-500">Employees with available capacity based on active allocations.</p>
        <Card className="p-10 text-center">
          <div className="text-[15px] font-semibold text-[var(--color-brand-navy)]">Access restricted</div>
          <div className="mt-1 text-sm text-gray-500">Only Super Admin, HR Admin, and managers can view bench availability.</div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="mb-1 text-2xl font-bold text-[var(--color-brand-navy)]">Bench & Availability</h1>
        <p className="text-sm text-gray-500">Employees with available capacity based on active allocations.</p>
      </div>

      <Card className="mb-5 p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="text-[12px] font-bold text-gray-400">
            Department
            <select value={department} onChange={(event) => setDepartment(event.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10">
              <option value="all">All departments</option>
              {departments.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="text-[12px] font-bold text-gray-400">
            Designation
            <select value={designation} onChange={(event) => setDesignation(event.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10">
              <option value="all">All designations</option>
              {designations.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="text-[12px] font-bold text-gray-400">
            Availability
            <select value={availability} onChange={(event) => setAvailability(event.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10">
              <option value="all">All</option>
              <option value="bench">Bench Only (0%)</option>
              <option value="partial">Partially Available (&lt;100%)</option>
              <option value="available_50">Available &gt;= 50%</option>
            </select>
          </label>
          <label className="text-[12px] font-bold text-gray-400">
            Available Within
            <select value={availableWithin} onChange={(event) => setAvailableWithin(event.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10">
              <option value="any">Any Time</option>
              <option value="30">30 Days</option>
              <option value="60">60 Days</option>
              <option value="90">90 Days</option>
            </select>
          </label>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <div className="text-[13px] font-bold text-[var(--color-brand-navy)]">Availability Overview</div>
            <div className="text-xs text-gray-500">{rows.length} employees</div>
          </div>
          <Button variant="ghost" size="sm" icon={<RefreshCw size={14} />} onClick={() => fetchBench()}>
            Refresh
          </Button>
        </div>

        {loading ? (
          <div className="divide-y divide-[var(--color-border)]">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="grid grid-cols-8 gap-4 px-6 py-5">
                {Array.from({ length: 8 }).map((__, cell) => (
                  <div key={cell} className="h-4 animate-pulse rounded bg-gray-100" />
                ))}
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="px-6 py-16 text-center">
            <div className="text-[15px] font-semibold text-[var(--color-brand-navy)]">Could not load availability</div>
            <div className="mt-1 text-sm text-gray-500">{error}</div>
          </div>
        ) : rows.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-hover-bg text-olive">
              <SearchX size={20} />
            </div>
            <div className="text-[15px] font-semibold text-[var(--color-brand-navy)]">No employees match the current filters.</div>
            <Button className="mt-4" variant="ghost" onClick={resetFilters}>Reset Filters</Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1080px] text-left">
              <thead className="bg-warm-bg">
                <tr className="text-[11px] font-bold uppercase tracking-wide text-gray-400">
                  <th className="px-6 py-3">Employee</th>
                  <th className="px-4 py-3">Department</th>
                  <th className="px-4 py-3">Designation</th>
                  <th className="px-4 py-3">Allocation %</th>
                  <th className="px-4 py-3">Available %</th>
                  <th className="px-4 py-3">Current Projects</th>
                  <th className="px-4 py-3">Next Available</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.employee_id} className="border-t border-[var(--color-border)] text-[14px] text-[var(--color-brand-navy)]">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <Avatar initials={initials(row.employee_name)} src={row.profile_image_url} variant="filled" />
                        <div className="min-w-0">
                          <div className="font-semibold">{row.employee_name}</div>
                          <Badge variant={statusVariant(row.allocation_status)}>{formatStatus(row.allocation_status)}</Badge>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-gray-600">{row.department || '-'}</td>
                    <td className="px-4 py-4 text-gray-600">{row.designation || '-'}</td>
                    <td className="px-4 py-4">
                      <div className="font-semibold">{row.total_active_allocation_percentage}%</div>
                      <div className="mt-1 h-1.5 w-24 overflow-hidden rounded-full bg-hover-bg">
                        <div className="h-full rounded-full bg-olive" style={{ width: `${Math.min(100, Math.max(0, row.total_active_allocation_percentage))}%` }} />
                      </div>
                    </td>
                    <td className={cn('px-4 py-4 font-bold', availableTone(row.available_capacity_percentage))}>
                      {row.available_capacity_percentage}%
                    </td>
                    <td className="px-4 py-4 text-gray-600">{projectSummary(row.active_project_names)}</td>
                    <td className="px-4 py-4 text-gray-600">{formatDate(row.next_available_date)}</td>
                    <td className="px-4 py-4 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<UserPlus size={14} />}
                        disabled={row.available_capacity_percentage <= 0 || projects.length === 0}
                        onClick={() => setSelectedEmployee(row)}
                      >
                        Assign
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {projectError && (
        <div className="mt-4 rounded-lg border border-status-warning/20 bg-status-warning/10 px-4 py-3 text-sm text-status-warning">
          Assignment is temporarily unavailable: {projectError}
        </div>
      )}

      <AssignEmployeeModal
        open={Boolean(selectedEmployee)}
        project={null}
        projects={projects}
        user={user}
        initialEmployeeId={selectedEmployee?.employee_id || ''}
        initialAllocationPercentage={selectedEmployee?.available_capacity_percentage || 100}
        lockEmployee
        onClose={() => setSelectedEmployee(null)}
        onAssigned={() => {
          showToast({ message: `${selectedEmployee?.employee_name || 'Employee'} assigned to project.` });
          setSelectedEmployee(null);
          fetchBench();
          loadFilterOptions();
        }}
      />
    </div>
  );
}

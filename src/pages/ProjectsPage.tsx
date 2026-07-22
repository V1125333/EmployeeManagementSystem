import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRightLeft,
  Briefcase,
  Calendar,
  CalendarPlus,
  Edit3,
  MoreVertical,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
  UserMinus,
  UserPlus,
  Users,
} from 'lucide-react';
import { AssignEmployeeModal } from '@/components/projects/AssignEmployeeModal';
import { AllocationMixBar } from '@/components/allocations/AllocationMixBar';
import { Avatar, Badge, Button, Card, StatusDot } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface ProjectRecord {
  id: string;
  name: string;
  code: string;
  description: string | null;
  client_id: string | null;
  client_name: string | null;
  start_date: string | null;
  end_date: string | null;
  status: string;
  allocation_count: number;
  active_allocation_count: number;
}

interface ClientOption {
  id: string;
  client_name: string;
  status: string;
}

interface AllocationRecord {
  id: string;
  employee_id: string;
  employee_name: string | null;
  employee_email: string | null;
  project_id: string | null;
  project_name: string | null;
  project_code?: string | null;
  project_location?: string | null;
  manager_id: string;
  manager_name: string | null;
  allocation_percentage: number;
  allocation_role: string;
  billing_type: string;
  status: string;
  start_date: string;
  end_date: string | null;
  notes?: string | null;
}

interface AllocationDisplayRow extends AllocationRecord {
  isDerivedAvailability?: boolean;
}

const STATUS_OPTIONS = ['all', 'planning', 'active', 'on_hold', 'completed', 'cancelled'];
const statusVariant: Record<string, 'olive' | 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  planning: 'info',
  active: 'success',
  available: 'info',
  bench: 'warning',
  on_hold: 'warning',
  completed: 'neutral',
  cancelled: 'error',
};

function normalizeRole(role?: string) {
  return (role || '').toLowerCase().replace(/\s+/g, '_');
}

function canManageProjects(role?: string) {
  return ['super_admin', 'hr_admin', 'admin', 'global_access'].includes(normalizeRole(role));
}

function canAssign(role?: string) {
  return ['super_admin', 'hr_admin', 'admin', 'global_access', 'manager'].includes(normalizeRole(role));
}

function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function toDateOnly(value?: string | null) {
  if (!value) return null;
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function toIsoDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

function addDays(value: Date, days: number) {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return next;
}

function isCurrentAllocation(allocation: AllocationRecord) {
  if (allocation.status !== 'active') return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = toDateOnly(allocation.start_date);
  const end = toDateOnly(allocation.end_date);
  if (!start) return false;
  return start <= today && (!end || end >= today);
}

function effectiveAllocationStatus(allocation: AllocationRecord) {
  if (allocation.status === 'active' && !isCurrentAllocation(allocation)) {
    return 'completed';
  }
  return allocation.status;
}

function label(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function buildAvailabilityRow(allocations: AllocationRecord[]): AllocationDisplayRow | null {
  const currentAllocations = allocations.filter(isCurrentAllocation);
  const activeTotal = currentAllocations.reduce(
    (total, allocation) => total + Number(allocation.allocation_percentage || 0),
    0
  );
  if (activeTotal >= 100) return null;

  const endedDates = allocations
    .filter((allocation) => allocation.status !== 'cancelled')
    .map((allocation) => toDateOnly(allocation.end_date))
    .filter((value): value is Date => Boolean(value))
    .sort((a, b) => b.getTime() - a.getTime());
  const benchStart = endedDates[0] ? addDays(endedDates[0], 1) : new Date();
  benchStart.setHours(0, 0, 0, 0);
  const reviewDate = addDays(benchStart, 30);

  return {
    id: 'derived-availability',
    employee_id: allocations[0]?.employee_id || '',
    employee_name: allocations[0]?.employee_name || null,
    employee_email: allocations[0]?.employee_email || null,
    project_id: null,
    project_code: activeTotal === 0 ? 'BENCH' : 'AVAILABLE',
    project_name: activeTotal === 0 ? 'Bench / Available' : 'Available Capacity',
    project_location: allocations[0]?.project_location || 'Remote',
    manager_id: currentAllocations[0]?.manager_id || allocations[0]?.manager_id || '',
    manager_name: currentAllocations[0]?.manager_name || allocations[0]?.manager_name || 'Resource Management',
    allocation_percentage: 100 - activeTotal,
    allocation_role: activeTotal === 0 ? 'Bench' : 'Available capacity',
    billing_type: 'internal',
    status: activeTotal === 0 ? 'bench' : 'available',
    start_date: toIsoDate(benchStart),
    end_date: toIsoDate(reviewDate),
    notes: 'Derived from project allocation dates',
    isDerivedAvailability: true,
  };
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').toUpperCase().slice(0, 2) || 'U';
}

function emptyForm() {
  return {
    name: '',
    code: '',
    client_id: '',
    client_name: 'Internal',
    description: '',
    start_date: '',
    end_date: '',
    status: 'planning',
  };
}

export function ProjectsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [clientOptions, setClientOptions] = useState<ClientOption[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectRecord | null>(null);
  const [allocations, setAllocations] = useState<AllocationRecord[]>([]);
  const [myAllocations, setMyAllocations] = useState<AllocationRecord[]>([]);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<ProjectRecord | null>(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [editingAllocation, setEditingAllocation] = useState<AllocationRecord | null>(null);
  const [allocationMode, setAllocationMode] = useState<'assign' | 'edit' | 'change' | 'extend'>('assign');
  const [openAllocationMenu, setOpenAllocationMenu] = useState('');
  const [confirmAllocationAction, setConfirmAllocationAction] = useState<{
    type: 'end' | 'remove';
    allocation: AllocationRecord;
  } | null>(null);
  const [allocationActionSaving, setAllocationActionSaving] = useState(false);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': normalizeRole(user?.role),
  }), [user]);
  const isProjectAdmin = canManageProjects(user?.role);
  const isProjectManager = normalizeRole(user?.role) === 'manager';
  const isEmployeeAllocationsView = !isProjectAdmin && !isProjectManager;
  const canEditAllocations = canAssign(user?.role);
  const allocationByProjectId = useMemo(() => {
    const entries = new Map<string, AllocationRecord>();
    myAllocations.forEach((allocation) => {
      if (allocation.project_id) entries.set(allocation.project_id, allocation);
    });
    return entries;
  }, [myAllocations]);
  const myAllocationRows = useMemo<AllocationDisplayRow[]>(() => {
    const availabilityRow = buildAvailabilityRow(myAllocations);
    return availabilityRow ? [...myAllocations, availabilityRow] : myAllocations;
  }, [myAllocations]);
  const visibleMyAllocations = useMemo(() => {
    const query = search.trim().toLowerCase();
    return myAllocationRows.filter((allocation) => {
      const allocationStatus = allocation.isDerivedAvailability ? allocation.status : effectiveAllocationStatus(allocation);
      const matchesStatus = status === 'all' || allocationStatus === status;
      const haystack = [
        allocation.project_code,
        allocation.project_name,
        allocation.manager_name,
        allocation.project_location,
        allocation.allocation_role,
      ].filter(Boolean).join(' ').toLowerCase();
      return matchesStatus && (!query || haystack.includes(query));
    });
  }, [myAllocationRows, search, status]);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      if (isEmployeeAllocationsView) {
        const allocationsRes = user?.id
          ? await fetch(`${API_BASE}/allocations/employee/${user.id}`, { headers })
          : await fetch(`${API_BASE}/projects/my-allocations`, { headers });
        const allocationsPayload = await allocationsRes.json().catch(() => []);
        if (!allocationsRes.ok) throw new Error(allocationsPayload.detail || 'Could not load your allocations.');
        setProjects([]);
        setMyAllocations(Array.isArray(allocationsPayload) ? allocationsPayload : []);
        setSelectedProject(null);
        return;
      }
      const params = new URLSearchParams();
      if (search.trim()) params.set('search', search.trim());
      if (status !== 'all') params.set('status', status);
      const res = await fetch(`${API_BASE}/projects/?${params.toString()}`, { headers });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || 'Could not load projects.');
      const rows = payload.projects || [];
      setProjects(rows);
      setMyAllocations([]);
      setSelectedProject((current) => {
        if (!current) return rows[0] || null;
        return rows.find((row: ProjectRecord) => row.id === current.id) || rows[0] || null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load projects.');
    } finally {
      setLoading(false);
    }
  }, [headers, isEmployeeAllocationsView, search, status]);

  const loadAllocations = useCallback(async (projectId: string) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/allocations`, { headers });
      const payload = await res.json().catch(() => []);
      if (!res.ok) throw new Error(payload.detail || 'Could not load assignments.');
      setAllocations(payload);
    } catch {
      setAllocations([]);
    } finally {
      setDetailLoading(false);
    }
  }, [headers]);

  const loadClientOptions = useCallback(async () => {
    if (!isProjectAdmin) {
      setClientOptions([]);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/projects/client-options`, { headers });
      const payload = await res.json().catch(() => []);
      if (!res.ok) throw new Error(payload.detail || 'Could not load clients.');
      setClientOptions(Array.isArray(payload) ? payload : []);
    } catch (err) {
      setClientOptions([]);
      showToast({ message: err instanceof Error ? err.message : 'Could not load clients.' });
    }
  }, [headers, isProjectAdmin, showToast]);

  useEffect(() => {
    const timeout = window.setTimeout(() => loadProjects(), 200);
    return () => window.clearTimeout(timeout);
  }, [loadProjects]);

  useEffect(() => {
    loadClientOptions();
  }, [loadClientOptions]);

  useEffect(() => {
    if (selectedProject?.id) {
      loadAllocations(selectedProject.id);
    } else {
      setAllocations([]);
    }
  }, [loadAllocations, selectedProject?.id]);

  const openCreate = () => {
    setEditingProject(null);
    setForm(emptyForm());
    setError('');
    setFormOpen(true);
  };

  const openEdit = (project: ProjectRecord) => {
    setEditingProject(project);
    setError('');
    setForm({
      name: project.name,
      code: project.code,
      client_id: project.client_id || '',
      client_name: project.client_name || '',
      description: project.description || '',
      start_date: project.start_date || '',
      end_date: project.end_date || '',
      status: project.status,
    });
    setFormOpen(true);
  };

  const submitProject = async () => {
    if (!form.name.trim() || !form.code.trim()) {
      setError('Project name and code are required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const body = {
        name: form.name.trim(),
        code: form.code.trim(),
        client_id: form.client_id || null,
        client_name: form.client_id ? null : 'Internal',
        description: form.description.trim() || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        status: form.status,
      };
      const res = await fetch(`${API_BASE}/projects/${editingProject ? editingProject.id : ''}`, {
        method: editingProject ? 'PATCH' : 'POST',
        headers,
        body: JSON.stringify(body),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || 'Could not save project.');
      showToast({ message: editingProject ? 'Project updated' : 'Project created' });
      setFormOpen(false);
      setSelectedProject(payload);
      if (!editingProject && payload?.id) {
        navigate(`/projects/${payload.id}`);
      }
      loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save project.');
    } finally {
      setSaving(false);
    }
  };

  const openAssignModal = () => {
    setEditingAllocation(null);
    setAllocationMode('assign');
    setAssignOpen(true);
  };

  const openAllocationModal = (allocation: AllocationRecord, mode: 'edit' | 'change' | 'extend') => {
    setOpenAllocationMenu('');
    setEditingAllocation(allocation);
    setAllocationMode(mode);
    setAssignOpen(true);
  };

  const refreshAfterAllocationChange = () => {
    if (selectedProject) loadAllocations(selectedProject.id);
    loadProjects();
    window.dispatchEvent(new CustomEvent('reknew:allocations-updated'));
  };

  const runAllocationAction = async () => {
    if (!confirmAllocationAction) return;
    const { type, allocation } = confirmAllocationAction;
    setAllocationActionSaving(true);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const res = await fetch(`${API_BASE}/allocations/${allocation.id}`, {
        method: type === 'remove' ? 'DELETE' : 'PATCH',
        headers,
        body: type === 'remove'
          ? undefined
          : JSON.stringify({
              status: 'completed',
              end_date: allocation.end_date && allocation.end_date < today ? allocation.end_date : today,
            }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || (type === 'remove' ? 'Could not remove assignment.' : 'Could not end assignment.'));
      showToast({ message: type === 'remove' ? 'Assignment removed.' : 'Assignment ended.' });
      setConfirmAllocationAction(null);
      refreshAfterAllocationChange();
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Assignment action failed.' });
    } finally {
      setAllocationActionSaving(false);
    }
  };

  const currentMyAllocations = myAllocations.filter(isCurrentAllocation);
  const employeeProjectCount = new Set(myAllocations.map((allocation) => allocation.project_id || allocation.project_name || allocation.id)).size;
  const employeeActiveAllocationPercent = currentMyAllocations.reduce((sum, allocation) => sum + Number(allocation.allocation_percentage || 0), 0);
  const employeeAvailablePercent = Math.max(0, 100 - employeeActiveAllocationPercent);
  const activeProjects = isEmployeeAllocationsView ? new Set(currentMyAllocations.map((allocation) => allocation.project_id || allocation.project_name || allocation.id)).size : projects.filter((project) => project.status === 'active').length;
  const totalActiveAssignments = isEmployeeAllocationsView
    ? currentMyAllocations.length
    : projects.reduce((sum, project) => sum + (project.active_allocation_count || 0), 0);
  const statusOptions = isEmployeeAllocationsView
    ? ['all', 'active', 'available', 'bench', 'completed', 'cancelled']
    : STATUS_OPTIONS;
  const pageTitle = isEmployeeAllocationsView ? 'My Allocations' : 'Projects';
  const pageDescription = isEmployeeAllocationsView
    ? 'View your active project allocations and assignment details.'
    : 'Manage projects and employee assignments.';

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">{pageTitle}</h1>
          <p className="mt-1 text-sm text-gray-500">{pageDescription}</p>
        </div>
        <div className="flex gap-2">
          {isProjectAdmin && (
            <Button onClick={openCreate} icon={<Plus size={15} />}>Add Project</Button>
          )}
          {selectedProject && canEditAllocations && (
            <Button variant="soft" onClick={openAssignModal} icon={<UserPlus size={15} />}>Assign Employee</Button>
          )}
        </div>
      </div>

      {error && !formOpen && (
        <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}

      <div className={cn('mb-5 grid gap-4', isEmployeeAllocationsView ? 'md:grid-cols-2 xl:grid-cols-5' : 'md:grid-cols-3')}>
        <Card className="p-5">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{isEmployeeAllocationsView ? 'My Projects' : 'Total Projects'}</div>
          <div className="mt-2 text-2xl font-bold text-[var(--color-brand-navy)]">{isEmployeeAllocationsView ? employeeProjectCount : projects.length}</div>
        </Card>
        {isEmployeeAllocationsView && (
          <Card className="p-5 md:col-span-2">
            <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Allocation Mix</div>
            <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
              <div className="text-2xl font-bold text-[var(--color-brand-navy)]">{employeeActiveAllocationPercent}% allocated</div>
              <div className="text-sm font-bold text-status-success">{employeeAvailablePercent}% available</div>
            </div>
            <AllocationMixBar allocated={employeeActiveAllocationPercent} className="mt-4" />
          </Card>
        )}
        <Card className="p-5">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Active Projects</div>
          <div className="mt-2 text-2xl font-bold text-[var(--color-brand-navy)]">{activeProjects}</div>
        </Card>
        <Card className="p-5">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{isEmployeeAllocationsView ? 'Active Allocations' : 'Active Assignments'}</div>
          <div className="mt-2 text-2xl font-bold text-[var(--color-brand-navy)]">{totalActiveAssignments}</div>
        </Card>
      </div>

      <Card className="mb-5 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={17} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={isEmployeeAllocationsView ? 'Search my allocations...' : 'Search projects, clients, or codes...'}
              className="h-11 w-full rounded-lg border border-[var(--color-border)] bg-warm-card pl-10 pr-3 text-sm font-medium text-[var(--color-brand-navy)] outline-none focus:border-accent"
            />
          </div>
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={17} className="text-gray-400" />
            <select value={status} onChange={(event) => setStatus(event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-card px-3 text-sm font-semibold text-gray-600 outline-none focus:border-accent">
              {statusOptions.map((option) => (
                <option key={option} value={option}>{option === 'all' ? 'All statuses' : label(option)}</option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {isEmployeeAllocationsView ? (
        <Card className="overflow-hidden">
          {loading ? (
            <div className="px-6 py-16 text-center text-sm text-gray-500">Loading allocations...</div>
          ) : visibleMyAllocations.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-accent-light text-accent">
                <Briefcase size={20} />
              </div>
              <div className="text-[15px] font-semibold text-[var(--color-brand-navy)]">No allocations found</div>
              <div className="mt-1 text-sm text-gray-500">You do not have allocations for the selected filters.</div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-left">
                <thead className="bg-warm-bg">
                  <tr className="text-[11px] font-bold uppercase tracking-wide text-gray-400">
                    <th className="px-5 py-3">Project Code</th>
                    <th className="px-4 py-3">Project Name</th>
                    <th className="px-4 py-3">Manager</th>
                    <th className="px-4 py-3">Project Location</th>
                    <th className="px-4 py-3">Allocation %</th>
                    <th className="px-4 py-3">Start Date</th>
                    <th className="px-4 py-3">End / Review Date</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {visibleMyAllocations.map((allocation) => {
                    const rowStatus = allocation.isDerivedAvailability ? allocation.status : effectiveAllocationStatus(allocation);
                    return (
                    <tr key={allocation.id} className="text-sm text-[var(--color-brand-navy)] hover:bg-hover-bg/60">
                      <td className="px-5 py-4 font-bold">{allocation.project_code || '-'}</td>
                      <td className="px-4 py-4">
                        <div className="font-bold">{allocation.project_name || 'Assigned project'}</div>
                        <div className="text-xs text-gray-500">{allocation.allocation_role}</div>
                      </td>
                      <td className="px-4 py-4 text-gray-600">{allocation.manager_name || 'Not assigned'}</td>
                      <td className="px-4 py-4 text-gray-600">{allocation.project_location || 'Remote'}</td>
                      <td className="px-4 py-4 font-bold">{allocation.allocation_percentage}%</td>
                      <td className="px-4 py-4 text-gray-600">{formatDate(allocation.start_date)}</td>
                      <td className="px-4 py-4 text-gray-600">{formatDate(allocation.end_date)}</td>
                      <td className="px-4 py-4">
                        <Badge variant={statusVariant[rowStatus] || 'neutral'}>{label(rowStatus)}</Badge>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : (
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
        <Card className="overflow-visible">
          {loading ? (
            <div className="px-6 py-16 text-center text-sm text-gray-500">Loading projects...</div>
          ) : projects.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-accent-light text-accent">
                <Briefcase size={20} />
              </div>
              <div className="text-[15px] font-semibold text-[var(--color-brand-navy)]">
                {isEmployeeAllocationsView ? 'No active allocations found' : 'No projects found'}
              </div>
              <div className="mt-1 text-sm text-gray-500">
                {isEmployeeAllocationsView ? 'You do not have an active project allocation for the selected filters.' : 'Create a project or adjust the filters.'}
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left">
                <thead className="bg-warm-bg text-[11px] font-bold uppercase tracking-wide text-gray-400">
                  {isEmployeeAllocationsView ? (
                    <tr>
                      <th className="px-5 py-3">Project</th>
                      <th className="px-4 py-3">Client</th>
                      <th className="px-4 py-3">Role</th>
                      <th className="px-4 py-3">Allocation</th>
                      <th className="px-4 py-3">Manager</th>
                      <th className="px-4 py-3">Dates</th>
                      <th className="px-4 py-3">Status</th>
                    </tr>
                  ) : (
                    <tr>
                      <th className="px-5 py-3">Project</th>
                      <th className="px-4 py-3">Client</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Assignments</th>
                      <th className="px-4 py-3">Dates</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  )}
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {projects.map((project) => (
                    <tr
                      key={project.id}
                      onClick={() => setSelectedProject(project)}
                      className={cn('cursor-pointer text-sm text-[var(--color-brand-navy)] hover:bg-hover-bg/60', selectedProject?.id === project.id && 'bg-accent-light/50')}
                    >
                      <td className="px-5 py-4">
                        <div className="font-bold">{project.name}</div>
                        <div className="text-xs font-semibold text-gray-400">{project.code}</div>
                      </td>
                      <td className="px-4 py-4 text-gray-600">{project.client_name || '-'}</td>
                      {isEmployeeAllocationsView ? (
                        <>
                          <td className="px-4 py-4 text-gray-600">{allocationByProjectId.get(project.id)?.allocation_role || '-'}</td>
                          <td className="px-4 py-4 font-bold text-[var(--color-brand-navy)]">{allocationByProjectId.get(project.id)?.allocation_percentage ?? 0}%</td>
                          <td className="px-4 py-4 text-gray-600">{allocationByProjectId.get(project.id)?.manager_name || '-'}</td>
                          <td className="px-4 py-4 text-gray-600">
                            {formatDate(allocationByProjectId.get(project.id)?.start_date)} - {formatDate(allocationByProjectId.get(project.id)?.end_date)}
                          </td>
                          <td className="px-4 py-4"><Badge variant={statusVariant[allocationByProjectId.get(project.id)?.status || project.status] || 'neutral'}>{label(allocationByProjectId.get(project.id)?.status || project.status)}</Badge></td>
                        </>
                      ) : (
                        <>
                          <td className="px-4 py-4"><Badge variant={statusVariant[project.status] || 'neutral'}>{label(project.status)}</Badge></td>
                          <td className="px-4 py-4">
                            <div className="flex items-center gap-2">
                              <Users size={15} className="text-gray-400" />
                              <span className="font-semibold">{project.active_allocation_count}</span>
                              <span className="text-gray-400">active</span>
                            </div>
                          </td>
                          <td className="px-4 py-4 text-gray-600">{formatDate(project.start_date)} - {formatDate(project.end_date)}</td>
                          <td className="px-4 py-4 text-right">
                            {isProjectAdmin && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={(event) => { event.stopPropagation(); openEdit(project); }}
                                icon={<Edit3 size={13} />}
                              >
                                Edit
                              </Button>
                            )}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="overflow-visible">
          {selectedProject ? (
            <>
              <div className="border-b border-[var(--color-border)] px-5 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <StatusDot color="var(--color-brand-orange)" />
                      <h2 className="text-base font-bold text-[var(--color-brand-navy)]">{selectedProject.name}</h2>
                    </div>
                    <div className="mt-1 text-xs font-semibold text-gray-400">{selectedProject.code}</div>
                  </div>
                  <Badge variant={statusVariant[selectedProject.status] || 'neutral'}>{label(selectedProject.status)}</Badge>
                </div>
                {selectedProject.description && <p className="mt-3 text-sm leading-6 text-gray-600">{selectedProject.description}</p>}
              </div>

              <div className="grid grid-cols-2 gap-3 px-5 py-4 text-sm">
                <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg p-3">
                  <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Client</div>
                  <div className="mt-1 font-semibold text-[var(--color-brand-navy)]">{selectedProject.client_name || '-'}</div>
                </div>
                <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg p-3">
                  <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">
                    {isEmployeeAllocationsView ? 'My Allocation' : 'Active Assignments'}
                  </div>
                  <div className="mt-1 font-semibold text-[var(--color-brand-navy)]">
                    {isEmployeeAllocationsView ? `${allocationByProjectId.get(selectedProject.id)?.allocation_percentage ?? 0}%` : selectedProject.active_allocation_count}
                  </div>
                </div>
                <div className="col-span-2 rounded-xl border border-[var(--color-border)] bg-warm-bg p-3">
                  <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-gray-400">
                    <Calendar size={13} /> Timeline
                  </div>
                  <div className="mt-1 font-semibold text-[var(--color-brand-navy)]">{formatDate(selectedProject.start_date)} - {formatDate(selectedProject.end_date)}</div>
                </div>
              </div>

              <div className="border-t border-[var(--color-border)] px-5 py-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-sm font-bold text-[var(--color-brand-navy)]">{isEmployeeAllocationsView ? 'My Assignment' : 'Assignments'}</div>
                  {canEditAllocations && <Button size="sm" variant="soft" onClick={openAssignModal} icon={<UserPlus size={13} />}>Assign</Button>}
                </div>
                {detailLoading ? (
                  <div className="py-8 text-center text-sm text-gray-500">Loading assignments...</div>
                ) : allocations.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[var(--color-border)] px-4 py-8 text-center text-sm text-gray-500">No employees assigned yet.</div>
                ) : (
                  <div className="space-y-2">
                    {allocations.map((allocation) => (
                      <div key={allocation.id} className="relative flex items-center gap-3 rounded-xl border border-[var(--color-border)] bg-warm-card px-3 py-3">
                        <Avatar initials={initials(allocation.employee_name || allocation.employee_email || 'Employee')} size="sm" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-bold text-[var(--color-brand-navy)]">{allocation.employee_name || allocation.employee_email}</div>
                          <div className="mt-0.5 truncate text-[11px] font-medium text-gray-400">
                            {formatDate(allocation.start_date)} - {formatDate(allocation.end_date)}
                          </div>
                          <div className="truncate text-xs text-gray-500">{allocation.allocation_role} · {allocation.manager_name || 'No manager'}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-bold text-[var(--color-brand-navy)]">{allocation.allocation_percentage}%</div>
                          <Badge variant={statusVariant[allocation.status] || 'neutral'}>{allocation.status}</Badge>
                        </div>
                        {canEditAllocations && (
                          <div className="relative">
                            <button
                              type="button"
                              onClick={() => setOpenAllocationMenu((current) => current === allocation.id ? '' : allocation.id)}
                              className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg hover:text-[var(--color-brand-navy)]"
                              aria-label="Open assignment actions"
                            >
                              <MoreVertical size={16} />
                            </button>
                            {openAllocationMenu === allocation.id && (
                              <div className="absolute right-0 top-9 z-20 w-52 overflow-hidden rounded-xl border border-[var(--color-border)] bg-white py-1 shadow-[0_18px_45px_rgba(15,23,42,0.16)]">
                                <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-[var(--color-brand-navy)] hover:bg-hover-bg" onClick={() => openAllocationModal(allocation, 'edit')}>
                                  <Edit3 size={14} /> Edit Allocation
                                </button>
                                <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-[var(--color-brand-navy)] hover:bg-hover-bg" onClick={() => openAllocationModal(allocation, 'change')}>
                                  <ArrowRightLeft size={14} /> Change Project
                                </button>
                                <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-[var(--color-brand-navy)] hover:bg-hover-bg" onClick={() => openAllocationModal(allocation, 'extend')}>
                                  <CalendarPlus size={14} /> Extend Assignment
                                </button>
                                <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-[var(--color-brand-navy)] hover:bg-hover-bg" onClick={() => { setOpenAllocationMenu(''); setConfirmAllocationAction({ type: 'end', allocation }); }}>
                                  <UserMinus size={14} /> End Assignment
                                </button>
                                <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-status-error hover:bg-status-error/[0.06]" onClick={() => { setOpenAllocationMenu(''); setConfirmAllocationAction({ type: 'remove', allocation }); }}>
                                  <Trash2 size={14} /> Remove Assignment
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="px-6 py-16 text-center text-sm text-gray-500">Select a project to view details.</div>
          )}
        </Card>
      </div>
      )}

      {formOpen && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-[var(--color-brand-navy)]/35 px-4 py-8 backdrop-blur-sm">
          <Card className="w-full max-w-2xl overflow-hidden shadow-[0_24px_70px_rgba(15,23,42,0.25)]">
            <div className="border-b border-[var(--color-border)] px-6 py-5">
              <h2 className="text-lg font-bold text-[var(--color-brand-navy)]">{editingProject ? 'Edit Project' : 'Add Project'}</h2>
              <p className="mt-1 text-sm text-gray-500">Project information used for allocation and timesheets.</p>
            </div>
            <div className="grid max-h-[70vh] gap-4 overflow-y-auto px-6 py-5 md:grid-cols-2">
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Project Name</span>
                <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="h-11 w-full rounded-lg border border-[var(--color-border)] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent" />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Code</span>
                <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} className="h-11 w-full rounded-lg border border-[var(--color-border)] bg-warm-card px-3 text-sm font-medium uppercase outline-none focus:border-accent" />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Client</span>
                <select
                  value={form.client_id}
                  onChange={(event) => {
                    const clientId = event.target.value;
                    const selectedClient = clientOptions.find((client) => client.id === clientId);
                    setForm({ ...form, client_id: clientId, client_name: selectedClient?.client_name || 'Internal' });
                  }}
                  className="h-11 w-full rounded-lg border border-[var(--color-border)] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent"
                >
                  <option value="">Internal project</option>
                  {clientOptions.map((client) => (
                    <option key={client.id} value={client.id}>{client.client_name} ({label(client.status)})</option>
                  ))}
                </select>
                {clientOptions.length === 0 && <span className="block text-xs text-gray-400">Add external clients in Client Onboarding first.</span>}
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Status</span>
                <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })} className="h-11 w-full rounded-lg border border-[var(--color-border)] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent">
                  {STATUS_OPTIONS.filter((option) => option !== 'all').map((option) => <option key={option} value={option}>{label(option)}</option>)}
                </select>
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Start Date</span>
                <input type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value })} className="h-11 w-full rounded-lg border border-[var(--color-border)] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent" />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">End Date</span>
                <input type="date" value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} className="h-11 w-full rounded-lg border border-[var(--color-border)] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent" />
              </label>
              <label className="space-y-1.5 md:col-span-2">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Description</span>
                <textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} className="min-h-[92px] w-full rounded-lg border border-[var(--color-border)] bg-warm-card px-3 py-3 text-sm font-medium outline-none focus:border-accent" />
              </label>
            </div>
            {error && (
              <div className="mx-6 mb-1 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-3 border-t border-[var(--color-border)] px-6 py-4">
              <Button variant="ghost" onClick={() => { setFormOpen(false); setError(''); }} disabled={saving}>Cancel</Button>
              <Button onClick={submitProject} disabled={saving}>{saving ? 'Saving...' : 'Save Project'}</Button>
            </div>
          </Card>
        </div>
      )}

      <AssignEmployeeModal
        open={assignOpen}
        project={selectedProject}
        user={user}
        allocation={editingAllocation}
        projects={projects}
        mode={allocationMode}
        onClose={() => {
          setAssignOpen(false);
          setEditingAllocation(null);
          setAllocationMode('assign');
        }}
        onAssigned={() => {
          showToast({ message: editingAllocation ? 'Assignment updated.' : 'Employee assigned to project.' });
          setEditingAllocation(null);
          setAllocationMode('assign');
          refreshAfterAllocationChange();
        }}
      />

      {confirmAllocationAction && (
        <div className="fixed inset-0 z-[95] flex items-center justify-center bg-[var(--color-brand-navy)]/45 px-4 py-8 backdrop-blur-sm">
          <Card className="w-full max-w-md overflow-hidden shadow-[0_24px_80px_rgba(15,23,42,0.28)]">
            <div className="border-b border-[var(--color-border)] px-6 py-5">
              <h2 className="text-lg font-bold text-[var(--color-brand-navy)]">
                {confirmAllocationAction.type === 'remove' ? 'Remove Assignment' : 'End Assignment'}
              </h2>
              <p className="mt-1 text-sm leading-6 text-gray-500">
                {confirmAllocationAction.type === 'remove'
                  ? 'This will mark the assignment as cancelled and remove it from active allocation views.'
                  : 'This will end the assignment today and keep the allocation history for audit and reporting.'}
              </p>
            </div>
            <div className="px-6 py-5">
              <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg p-4">
                <div className="text-sm font-bold text-[var(--color-brand-navy)]">
                  {confirmAllocationAction.allocation.employee_name || confirmAllocationAction.allocation.employee_email}
                </div>
                <div className="mt-1 text-sm text-gray-600">
                  {confirmAllocationAction.allocation.project_name || selectedProject?.name} · {confirmAllocationAction.allocation.allocation_percentage}%
                </div>
                <div className="mt-1 text-xs font-semibold text-gray-400">
                  {formatDate(confirmAllocationAction.allocation.start_date)} - {formatDate(confirmAllocationAction.allocation.end_date)}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 border-t border-[var(--color-border)] px-6 py-4">
              <Button
                variant="ghost"
                onClick={() => setConfirmAllocationAction(null)}
                disabled={allocationActionSaving}
              >
                Cancel
              </Button>
              <Button
                onClick={runAllocationAction}
                disabled={allocationActionSaving}
              >
                {allocationActionSaving
                  ? 'Saving...'
                  : confirmAllocationAction.type === 'remove'
                    ? 'Remove Assignment'
                    : 'End Assignment'}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

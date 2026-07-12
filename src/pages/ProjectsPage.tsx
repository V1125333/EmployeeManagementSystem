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
  client_name: string | null;
  start_date: string | null;
  end_date: string | null;
  status: string;
  allocation_count: number;
  active_allocation_count: number;
}

interface AllocationRecord {
  id: string;
  employee_id: string;
  employee_name: string | null;
  employee_email: string | null;
  project_id: string | null;
  project_name: string | null;
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

const STATUS_OPTIONS = ['all', 'planning', 'active', 'on_hold', 'completed', 'cancelled'];
const statusVariant: Record<string, 'olive' | 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  planning: 'info',
  active: 'success',
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

function label(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').toUpperCase().slice(0, 2) || 'U';
}

function emptyForm() {
  return {
    name: '',
    code: '',
    client_name: '',
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

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set('search', search.trim());
      if (status !== 'all') params.set('status', status);
      const res = await fetch(`${API_BASE}/projects/?${params.toString()}`, { headers });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || 'Could not load projects.');
      const rows = payload.projects || [];
      setProjects(rows);
      if (isEmployeeAllocationsView) {
        const allocationsRes = await fetch(`${API_BASE}/projects/my-allocations`, { headers });
        const allocationsPayload = await allocationsRes.json().catch(() => []);
        if (!allocationsRes.ok) throw new Error(allocationsPayload.detail || 'Could not load your allocations.');
        setMyAllocations(allocationsPayload);
      } else {
        setMyAllocations([]);
      }
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

  useEffect(() => {
    const timeout = window.setTimeout(() => loadProjects(), 200);
    return () => window.clearTimeout(timeout);
  }, [loadProjects]);

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
        client_name: form.client_name.trim() || null,
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

  const activeProjects = projects.filter((project) => project.status === 'active').length;
  const totalActiveAssignments = isEmployeeAllocationsView
    ? myAllocations.length
    : projects.reduce((sum, project) => sum + (project.active_allocation_count || 0), 0);
  const pageTitle = isEmployeeAllocationsView ? 'My Allocations' : 'Projects';
  const pageDescription = isEmployeeAllocationsView
    ? 'View your active project allocations and assignment details.'
    : 'Manage projects and employee assignments.';

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#2F3437]">{pageTitle}</h1>
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

      <div className="mb-5 grid gap-4 md:grid-cols-3">
        <Card className="p-5">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{isEmployeeAllocationsView ? 'My Projects' : 'Total Projects'}</div>
          <div className="mt-2 text-2xl font-bold text-[#2F3437]">{projects.length}</div>
        </Card>
        <Card className="p-5">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Active Projects</div>
          <div className="mt-2 text-2xl font-bold text-[#2F3437]">{activeProjects}</div>
        </Card>
        <Card className="p-5">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{isEmployeeAllocationsView ? 'Active Allocations' : 'Active Assignments'}</div>
          <div className="mt-2 text-2xl font-bold text-[#2F3437]">{totalActiveAssignments}</div>
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
              className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card pl-10 pr-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent"
            />
          </div>
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={17} className="text-gray-400" />
            <select value={status} onChange={(event) => setStatus(event.target.value)} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-semibold text-gray-600 outline-none focus:border-accent">
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>{option === 'all' ? 'All statuses' : label(option)}</option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
        <Card className="overflow-visible">
          {loading ? (
            <div className="px-6 py-16 text-center text-sm text-gray-500">Loading projects...</div>
          ) : projects.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-accent-light text-accent">
                <Briefcase size={20} />
              </div>
              <div className="text-[15px] font-semibold text-[#2F3437]">
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
                <tbody className="divide-y divide-[#E5E7EB]">
                  {projects.map((project) => (
                    <tr
                      key={project.id}
                      onClick={() => setSelectedProject(project)}
                      className={cn('cursor-pointer text-sm text-[#2F3437] hover:bg-hover-bg/60', selectedProject?.id === project.id && 'bg-accent-light/50')}
                    >
                      <td className="px-5 py-4">
                        <div className="font-bold">{project.name}</div>
                        <div className="text-xs font-semibold text-gray-400">{project.code}</div>
                      </td>
                      <td className="px-4 py-4 text-gray-600">{project.client_name || '-'}</td>
                      {isEmployeeAllocationsView ? (
                        <>
                          <td className="px-4 py-4 text-gray-600">{allocationByProjectId.get(project.id)?.allocation_role || '-'}</td>
                          <td className="px-4 py-4 font-bold text-[#2F3437]">{allocationByProjectId.get(project.id)?.allocation_percentage ?? 0}%</td>
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
              <div className="border-b border-[#E5E7EB] px-5 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <StatusDot color="#66785F" />
                      <h2 className="text-base font-bold text-[#2F3437]">{selectedProject.name}</h2>
                    </div>
                    <div className="mt-1 text-xs font-semibold text-gray-400">{selectedProject.code}</div>
                  </div>
                  <Badge variant={statusVariant[selectedProject.status] || 'neutral'}>{label(selectedProject.status)}</Badge>
                </div>
                {selectedProject.description && <p className="mt-3 text-sm leading-6 text-gray-600">{selectedProject.description}</p>}
              </div>

              <div className="grid grid-cols-2 gap-3 px-5 py-4 text-sm">
                <div className="rounded-xl border border-[#E5E7EB] bg-warm-bg p-3">
                  <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Client</div>
                  <div className="mt-1 font-semibold text-[#2F3437]">{selectedProject.client_name || '-'}</div>
                </div>
                <div className="rounded-xl border border-[#E5E7EB] bg-warm-bg p-3">
                  <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">
                    {isEmployeeAllocationsView ? 'My Allocation' : 'Active Assignments'}
                  </div>
                  <div className="mt-1 font-semibold text-[#2F3437]">
                    {isEmployeeAllocationsView ? `${allocationByProjectId.get(selectedProject.id)?.allocation_percentage ?? 0}%` : selectedProject.active_allocation_count}
                  </div>
                </div>
                <div className="col-span-2 rounded-xl border border-[#E5E7EB] bg-warm-bg p-3">
                  <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-gray-400">
                    <Calendar size={13} /> Timeline
                  </div>
                  <div className="mt-1 font-semibold text-[#2F3437]">{formatDate(selectedProject.start_date)} - {formatDate(selectedProject.end_date)}</div>
                </div>
              </div>

              <div className="border-t border-[#E5E7EB] px-5 py-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-sm font-bold text-[#2F3437]">{isEmployeeAllocationsView ? 'My Assignment' : 'Assignments'}</div>
                  {canEditAllocations && <Button size="sm" variant="soft" onClick={openAssignModal} icon={<UserPlus size={13} />}>Assign</Button>}
                </div>
                {detailLoading ? (
                  <div className="py-8 text-center text-sm text-gray-500">Loading assignments...</div>
                ) : allocations.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[#DADDE2] px-4 py-8 text-center text-sm text-gray-500">No employees assigned yet.</div>
                ) : (
                  <div className="space-y-2">
                    {allocations.map((allocation) => (
                      <div key={allocation.id} className="relative flex items-center gap-3 rounded-xl border border-[#E5E7EB] bg-warm-card px-3 py-3">
                        <Avatar initials={initials(allocation.employee_name || allocation.employee_email || 'Employee')} size="sm" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-bold text-[#2F3437]">{allocation.employee_name || allocation.employee_email}</div>
                          <div className="mt-0.5 truncate text-[11px] font-medium text-gray-400">
                            {formatDate(allocation.start_date)} - {formatDate(allocation.end_date)}
                          </div>
                          <div className="truncate text-xs text-gray-500">{allocation.allocation_role} · {allocation.manager_name || 'No manager'}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-bold text-[#2F3437]">{allocation.allocation_percentage}%</div>
                          <Badge variant={statusVariant[allocation.status] || 'neutral'}>{allocation.status}</Badge>
                        </div>
                        {canEditAllocations && (
                          <div className="relative">
                            <button
                              type="button"
                              onClick={() => setOpenAllocationMenu((current) => current === allocation.id ? '' : allocation.id)}
                              className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg hover:text-[#2F3437]"
                              aria-label="Open assignment actions"
                            >
                              <MoreVertical size={16} />
                            </button>
                            {openAllocationMenu === allocation.id && (
                              <div className="absolute right-0 top-9 z-20 w-52 overflow-hidden rounded-xl border border-[#E5E7EB] bg-white py-1 shadow-[0_18px_45px_rgba(15,23,42,0.16)]">
                                <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-[#2F3437] hover:bg-hover-bg" onClick={() => openAllocationModal(allocation, 'edit')}>
                                  <Edit3 size={14} /> Edit Allocation
                                </button>
                                <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-[#2F3437] hover:bg-hover-bg" onClick={() => openAllocationModal(allocation, 'change')}>
                                  <ArrowRightLeft size={14} /> Change Project
                                </button>
                                <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-[#2F3437] hover:bg-hover-bg" onClick={() => openAllocationModal(allocation, 'extend')}>
                                  <CalendarPlus size={14} /> Extend Assignment
                                </button>
                                <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-[#2F3437] hover:bg-hover-bg" onClick={() => { setOpenAllocationMenu(''); setConfirmAllocationAction({ type: 'end', allocation }); }}>
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

      {formOpen && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-[#111827]/35 px-4 py-8 backdrop-blur-sm">
          <Card className="w-full max-w-2xl overflow-hidden shadow-[0_24px_70px_rgba(15,23,42,0.25)]">
            <div className="border-b border-[#E5E7EB] px-6 py-5">
              <h2 className="text-lg font-bold text-[#2F3437]">{editingProject ? 'Edit Project' : 'Add Project'}</h2>
              <p className="mt-1 text-sm text-gray-500">Project information used for allocation and timesheets.</p>
            </div>
            <div className="grid max-h-[70vh] gap-4 overflow-y-auto px-6 py-5 md:grid-cols-2">
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Project Name</span>
                <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent" />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Code</span>
                <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium uppercase outline-none focus:border-accent" />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Client</span>
                <input value={form.client_name} onChange={(event) => setForm({ ...form, client_name: event.target.value })} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent" />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Status</span>
                <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent">
                  {STATUS_OPTIONS.filter((option) => option !== 'all').map((option) => <option key={option} value={option}>{label(option)}</option>)}
                </select>
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Start Date</span>
                <input type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value })} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent" />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">End Date</span>
                <input type="date" value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent" />
              </label>
              <label className="space-y-1.5 md:col-span-2">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Description</span>
                <textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} className="min-h-[92px] w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 py-3 text-sm font-medium outline-none focus:border-accent" />
              </label>
            </div>
            {error && (
              <div className="mx-6 mb-1 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-3 border-t border-[#E5E7EB] px-6 py-4">
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
        <div className="fixed inset-0 z-[95] flex items-center justify-center bg-[#111827]/45 px-4 py-8 backdrop-blur-sm">
          <Card className="w-full max-w-md overflow-hidden shadow-[0_24px_80px_rgba(15,23,42,0.28)]">
            <div className="border-b border-[#E5E7EB] px-6 py-5">
              <h2 className="text-lg font-bold text-[#2F3437]">
                {confirmAllocationAction.type === 'remove' ? 'Remove Assignment' : 'End Assignment'}
              </h2>
              <p className="mt-1 text-sm leading-6 text-gray-500">
                {confirmAllocationAction.type === 'remove'
                  ? 'This will mark the assignment as cancelled and remove it from active allocation views.'
                  : 'This will end the assignment today and keep the allocation history for audit and reporting.'}
              </p>
            </div>
            <div className="px-6 py-5">
              <div className="rounded-xl border border-[#E5E7EB] bg-warm-bg p-4">
                <div className="text-sm font-bold text-[#2F3437]">
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
            <div className="flex justify-end gap-3 border-t border-[#E5E7EB] px-6 py-4">
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

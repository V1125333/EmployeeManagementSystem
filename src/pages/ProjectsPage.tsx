import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Briefcase, Calendar, Edit3, Plus, Search, SlidersHorizontal, UserPlus, Users } from 'lucide-react';
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
  manager_name: string | null;
  allocation_percentage: number;
  allocation_role: string;
  billing_type: string;
  status: string;
  start_date: string;
  end_date: string | null;
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

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': normalizeRole(user?.role),
  }), [user]);

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
      setSelectedProject((current) => {
        if (!current) return rows[0] || null;
        return rows.find((row: ProjectRecord) => row.id === current.id) || rows[0] || null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load projects.');
    } finally {
      setLoading(false);
    }
  }, [headers, search, status]);

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
    setFormOpen(true);
  };

  const openEdit = (project: ProjectRecord) => {
    setEditingProject(project);
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

  const activeProjects = projects.filter((project) => project.status === 'active').length;
  const totalActiveAssignments = projects.reduce((sum, project) => sum + (project.active_allocation_count || 0), 0);

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#2F3437]">Projects</h1>
          <p className="mt-1 text-sm text-gray-500">Manage projects and employee assignments.</p>
        </div>
        <div className="flex gap-2">
          {canManageProjects(user?.role) && (
            <Button onClick={openCreate} icon={<Plus size={15} />}>Add Project</Button>
          )}
          {selectedProject && canAssign(user?.role) && (
            <Button variant="soft" onClick={() => setAssignOpen(true)} icon={<UserPlus size={15} />}>Assign Employee</Button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}

      <div className="mb-5 grid gap-4 md:grid-cols-3">
        <Card className="p-5">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Total Projects</div>
          <div className="mt-2 text-2xl font-bold text-[#2F3437]">{projects.length}</div>
        </Card>
        <Card className="p-5">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Active Projects</div>
          <div className="mt-2 text-2xl font-bold text-[#2F3437]">{activeProjects}</div>
        </Card>
        <Card className="p-5">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Active Assignments</div>
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
              placeholder="Search projects, clients, or codes..."
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
        <Card className="overflow-hidden">
          {loading ? (
            <div className="px-6 py-16 text-center text-sm text-gray-500">Loading projects...</div>
          ) : projects.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-accent-light text-accent">
                <Briefcase size={20} />
              </div>
              <div className="text-[15px] font-semibold text-[#2F3437]">No projects found</div>
              <div className="mt-1 text-sm text-gray-500">Create a project or adjust the filters.</div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left">
                <thead className="bg-warm-bg text-[11px] font-bold uppercase tracking-wide text-gray-400">
                  <tr>
                    <th className="px-5 py-3">Project</th>
                    <th className="px-4 py-3">Client</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Assignments</th>
                    <th className="px-4 py-3">Dates</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
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
                        {canManageProjects(user?.role) && (
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="overflow-hidden">
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
                  <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Active Assignments</div>
                  <div className="mt-1 font-semibold text-[#2F3437]">{selectedProject.active_allocation_count}</div>
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
                  <div className="text-sm font-bold text-[#2F3437]">Assignments</div>
                  {canAssign(user?.role) && <Button size="sm" variant="soft" onClick={() => setAssignOpen(true)} icon={<UserPlus size={13} />}>Assign</Button>}
                </div>
                {detailLoading ? (
                  <div className="py-8 text-center text-sm text-gray-500">Loading assignments...</div>
                ) : allocations.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[#DADDE2] px-4 py-8 text-center text-sm text-gray-500">No employees assigned yet.</div>
                ) : (
                  <div className="space-y-2">
                    {allocations.map((allocation) => (
                      <div key={allocation.id} className="flex items-center gap-3 rounded-xl border border-[#E5E7EB] bg-warm-card px-3 py-3">
                        <Avatar initials={initials(allocation.employee_name || allocation.employee_email || 'Employee')} size="sm" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-bold text-[#2F3437]">{allocation.employee_name || allocation.employee_email}</div>
                          <div className="truncate text-xs text-gray-500">{allocation.allocation_role} · {allocation.manager_name || 'No manager'}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-bold text-[#2F3437]">{allocation.allocation_percentage}%</div>
                          <Badge variant={statusVariant[allocation.status] || 'neutral'}>{allocation.status}</Badge>
                        </div>
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
            <div className="flex justify-end gap-3 border-t border-[#E5E7EB] px-6 py-4">
              <Button variant="ghost" onClick={() => setFormOpen(false)} disabled={saving}>Cancel</Button>
              <Button onClick={submitProject} disabled={saving}>{saving ? 'Saving...' : 'Save Project'}</Button>
            </div>
          </Card>
        </div>
      )}

      <AssignEmployeeModal
        open={assignOpen}
        project={selectedProject}
        user={user}
        onClose={() => setAssignOpen(false)}
        onAssigned={() => {
          showToast({ message: 'Employee assigned to project' });
          if (selectedProject) loadAllocations(selectedProject.id);
          loadProjects();
        }}
      />
    </div>
  );
}

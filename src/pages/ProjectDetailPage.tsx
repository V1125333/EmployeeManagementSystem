import { useCallback, useEffect, useMemo, useState } from 'react';
import type React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  Edit3,
  FileText,
  History,
  Layers,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  UserCog,
  Users,
  X,
} from 'lucide-react';
import { AssignEmployeeModal } from '@/components/projects/AssignEmployeeModal';
import { Avatar, Badge, Button, Card } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

type TabKey = 'overview' | 'team' | 'allocations' | 'documents' | 'audit';

interface ProjectRecord {
  id: string;
  name: string;
  code: string;
  description: string | null;
  client_name: string | null;
  start_date: string | null;
  end_date: string | null;
  status: string;
  project_manager_id: string | null;
  project_manager_name: string | null;
  allocation_count: number;
  active_allocation_count: number;
  active_employee_count: number;
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

interface EmployeeOption {
  id: string;
  name: string;
  work_email: string;
  role: string;
  department: string;
}

interface ProjectDocument {
  id: string;
  original_file_name: string;
  file_extension: string | null;
  mime_type: string | null;
  file_size_bytes: number | null;
  document_type: string;
  uploaded_by_id: string;
  uploaded_by_name: string | null;
  created_at: string;
}

interface AuditLog {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  created_at: string | null;
  actor_name?: string | null;
  actor_role?: string | null;
  metadata_json?: Record<string, unknown> | null;
  changed_fields?: string[] | null;
}

const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode }> = [
  { key: 'overview', label: 'Overview', icon: <Layers size={15} /> },
  { key: 'team', label: 'Team & Assignments', icon: <Users size={15} /> },
  { key: 'allocations', label: 'Allocations', icon: <UserCog size={15} /> },
  { key: 'documents', label: 'Documents', icon: <FileText size={15} /> },
  { key: 'audit', label: 'Audit History', icon: <History size={15} /> },
];

const statusVariant: Record<string, 'olive' | 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  planning: 'info',
  active: 'success',
  upcoming: 'info',
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

function label(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').toUpperCase().slice(0, 2) || 'U';
}

function formatBytes(bytes?: number | null) {
  if (!bytes) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectDetailPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [allocations, setAllocations] = useState<AllocationRecord[]>([]);
  const [documents, setDocuments] = useState<ProjectDocument[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [tabLoading, setTabLoading] = useState(false);
  const [error, setError] = useState('');
  const [assignOpen, setAssignOpen] = useState(false);
  const [editingAllocation, setEditingAllocation] = useState<AllocationRecord | null>(null);
  const [managerOpen, setManagerOpen] = useState(false);
  const [managerOptions, setManagerOptions] = useState<EmployeeOption[]>([]);
  const [selectedManagerId, setSelectedManagerId] = useState('');
  const [uploadType, setUploadType] = useState('OTHER');
  const [uploading, setUploading] = useState(false);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': normalizeRole(user?.role),
  }), [user]);

  const fileHeaders = useMemo(() => ({
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': normalizeRole(user?.role),
  }), [user]);

  const loadProject = useCallback(async () => {
    if (!projectId) return;
    setError('');
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}`, { headers });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || 'Could not load project.');
      setProject(payload);
      setSelectedManagerId(payload.project_manager_id || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load project.');
    }
  }, [headers, projectId]);

  const loadAllocations = useCallback(async () => {
    if (!projectId) return;
    const res = await fetch(`${API_BASE}/projects/${projectId}/allocations`, { headers });
    const payload = await res.json().catch(() => []);
    if (!res.ok) throw new Error(payload.detail || 'Could not load assignments.');
    setAllocations(payload);
  }, [headers, projectId]);

  const loadDocuments = useCallback(async () => {
    if (!projectId) return;
    const res = await fetch(`${API_BASE}/projects/${projectId}/documents`, { headers });
    const payload = await res.json().catch(() => []);
    if (!res.ok) throw new Error(payload.detail || 'Could not load documents.');
    setDocuments(payload);
  }, [headers, projectId]);

  const loadAudit = useCallback(async () => {
    if (!projectId || !canManageProjects(user?.role)) return;
    const res = await fetch(`${API_BASE}/audit-logs/entity/project/${projectId}`, { headers });
    const payload = await res.json().catch(() => []);
    if (!res.ok) throw new Error(payload.detail || 'Could not load audit history.');
    setAuditLogs(Array.isArray(payload) ? payload : payload.items || []);
  }, [headers, projectId, user?.role]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([loadProject(), loadAllocations()]);
    } finally {
      setLoading(false);
    }
  }, [loadAllocations, loadProject]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const loadTab = async () => {
      setTabLoading(true);
      setError('');
      try {
        if (activeTab === 'documents') await loadDocuments();
        if (activeTab === 'audit') await loadAudit();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load tab data.');
      } finally {
        setTabLoading(false);
      }
    };
    loadTab();
  }, [activeTab, loadAudit, loadDocuments]);

  const loadManagers = async () => {
    try {
      const res = await fetch(`${API_BASE}/projects/assignable-employees?limit=250`, { headers });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || 'Could not load managers.');
      setManagerOptions(payload.managers || []);
      setManagerOpen(true);
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not load managers.' });
    }
  };

  const saveManager = async () => {
    if (!projectId) return;
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/manager`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ manager_employee_id: selectedManagerId || null }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || 'Could not update project manager.');
      setProject(payload);
      setManagerOpen(false);
      showToast({ message: 'Project manager updated' });
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not update manager.' });
    }
  };

  const deleteAllocation = async (allocation: AllocationRecord) => {
    if (!window.confirm(`Remove ${allocation.employee_name || 'this employee'} from ${project?.name}?`)) return;
    try {
      const res = await fetch(`${API_BASE}/allocations/${allocation.id}`, { method: 'DELETE', headers });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || 'Could not remove assignment.');
      showToast({ message: 'Assignment removed' });
      await Promise.all([loadAllocations(), loadProject()]);
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not remove assignment.' });
    }
  };

  const uploadDocument = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !projectId) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('document_type', uploadType);
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/projects/${projectId}/documents`, {
        method: 'POST',
        headers: fileHeaders,
        body: formData,
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || 'Could not upload document.');
      showToast({ message: 'Document uploaded' });
      await loadDocuments();
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not upload document.' });
    } finally {
      setUploading(false);
    }
  };

  const downloadDocument = async (doc: ProjectDocument) => {
    if (!projectId) return;
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/documents/${doc.id}/download`, { headers: fileHeaders });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.detail || 'Could not download document.');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = doc.original_file_name;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not download document.' });
    }
  };

  const deleteDocument = async (doc: ProjectDocument) => {
    if (!projectId || !window.confirm(`Delete ${doc.original_file_name}?`)) return;
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/documents/${doc.id}`, { method: 'DELETE', headers });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || 'Could not delete document.');
      showToast({ message: 'Document deleted' });
      await loadDocuments();
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not delete document.' });
    }
  };

  const totalAllocation = allocations
    .filter((allocation) => ['active', 'upcoming'].includes(allocation.status))
    .reduce((sum, allocation) => sum + Number(allocation.allocation_percentage || 0), 0);
  const activeAssignments = allocations.filter((allocation) => allocation.status === 'active').length;

  if (loading) {
    return <div className="p-6 lg:p-8 text-sm text-gray-500">Loading project...</div>;
  }

  if (!project) {
    return (
      <div className="p-6 lg:p-8">
        <Button variant="ghost" onClick={() => navigate('/projects')} icon={<ArrowLeft size={15} />}>Back to Projects</Button>
        <Card className="mt-5 px-6 py-16 text-center text-sm text-gray-500">Project not found.</Card>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <Button variant="ghost" size="sm" onClick={() => navigate('/projects')} icon={<ArrowLeft size={14} />}>Projects</Button>
          <div className="mt-4 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-light text-accent">
              <Layers size={20} />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-[#2F3437]">{project.name}</h1>
                <Badge variant={statusVariant[project.status] || 'neutral'}>{label(project.status)}</Badge>
              </div>
              <p className="mt-1 text-sm text-gray-500">{project.code} {project.client_name ? `· ${project.client_name}` : ''}</p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={refresh} icon={<RefreshCw size={15} />}>Refresh</Button>
          {canAssign(user?.role) && <Button variant="soft" onClick={() => setAssignOpen(true)} icon={<Plus size={15} />}>Add Employee</Button>}
          {canManageProjects(user?.role) && <Button onClick={loadManagers} icon={<UserCog size={15} />}>Assign PM</Button>}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}

      <Card className="mb-5 overflow-hidden">
        <div className="flex gap-1 overflow-x-auto border-b border-[#E5E7EB] px-3 py-2">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-gray-500 transition hover:bg-hover-bg hover:text-[#2F3437]',
                activeTab === tab.key && 'bg-accent-light text-accent',
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'overview' && (
          <div className="grid gap-5 p-5 lg:grid-cols-[1fr_0.8fr]">
            <div className="space-y-4">
              <div>
                <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Description</div>
                <p className="mt-2 text-sm leading-6 text-gray-600">{project.description || 'No description provided.'}</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Metric label="Timeline" value={`${formatDate(project.start_date)} - ${formatDate(project.end_date)}`} />
                <Metric label="Project Manager" value={project.project_manager_name || 'Not assigned'} />
                <Metric label="Active Assignments" value={`${activeAssignments}`} />
                <Metric label="Total Allocation" value={`${totalAllocation}%`} />
              </div>
            </div>
            <div className="rounded-xl border border-[#E5E7EB] bg-warm-bg p-4">
              <div className="mb-3 text-sm font-bold text-[#2F3437]">Assignment Snapshot</div>
              <div className="space-y-3">
                {allocations.slice(0, 5).map((allocation) => (
                  <AssignmentMini key={allocation.id} allocation={allocation} />
                ))}
                {allocations.length === 0 && <div className="py-8 text-center text-sm text-gray-500">No assignments yet.</div>}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'team' && (
          <div className="p-5">
            <AssignmentsTable
              allocations={allocations}
              canEdit={canManageProjects(user?.role)}
              onEdit={(allocation) => setEditingAllocation(allocation)}
              onDelete={deleteAllocation}
            />
          </div>
        )}

        {activeTab === 'allocations' && (
          <div className="space-y-5 p-5">
            <div className="grid gap-4 md:grid-cols-4">
              <Metric label="Active Employees" value={`${activeAssignments}`} />
              <Metric label="Total Allocation" value={`${totalAllocation}%`} />
              <Metric label="Billable Assignments" value={`${allocations.filter((item) => item.billing_type === 'billable').length}`} />
              <Metric label="Completed" value={`${allocations.filter((item) => item.status === 'completed').length}`} />
            </div>
            <AssignmentsTable
              allocations={allocations}
              canEdit={canManageProjects(user?.role)}
              onEdit={(allocation) => setEditingAllocation(allocation)}
              onDelete={deleteAllocation}
            />
          </div>
        )}

        {activeTab === 'documents' && (
          <div className="p-5">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-bold text-[#2F3437]">Project Documents</div>
                <div className="text-sm text-gray-500">Contracts, SOWs, reports, and related files.</div>
              </div>
              {canManageProjects(user?.role) && (
                <div className="flex gap-2">
                  <select value={uploadType} onChange={(event) => setUploadType(event.target.value)} className="h-10 rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-semibold outline-none focus:border-accent">
                    {['CONTRACT', 'SOW', 'NDA', 'INVOICE', 'REPORT', 'OTHER'].map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-btn bg-accent px-4 py-2 text-[13px] font-semibold text-white shadow-sm hover:bg-accent-dark">
                    <Upload size={15} />
                    {uploading ? 'Uploading...' : 'Upload'}
                    <input type="file" className="hidden" onChange={uploadDocument} disabled={uploading} />
                  </label>
                </div>
              )}
            </div>
            {tabLoading ? (
              <div className="py-12 text-center text-sm text-gray-500">Loading documents...</div>
            ) : documents.length === 0 ? (
              <EmptyState icon={<FileText size={22} />} title="No documents uploaded" text="Project files will appear here after upload." />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-[#E5E7EB]">
                <table className="w-full min-w-[780px] text-left">
                  <thead className="bg-warm-bg text-[11px] font-bold uppercase tracking-wide text-gray-400">
                    <tr>
                      <th className="px-4 py-3">Document</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Uploaded By</th>
                      <th className="px-4 py-3">Size</th>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB]">
                    {documents.map((doc) => (
                      <tr key={doc.id} className="text-sm">
                        <td className="px-4 py-3 font-semibold text-[#2F3437]">{doc.original_file_name}</td>
                        <td className="px-4 py-3"><Badge variant="olive">{doc.document_type}</Badge></td>
                        <td className="px-4 py-3 text-gray-600">{doc.uploaded_by_name || '-'}</td>
                        <td className="px-4 py-3 text-gray-600">{formatBytes(doc.file_size_bytes)}</td>
                        <td className="px-4 py-3 text-gray-600">{formatDateTime(doc.created_at)}</td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-2">
                            <Button size="sm" variant="ghost" onClick={() => downloadDocument(doc)} icon={<Download size={13} />}>Download</Button>
                            {(canManageProjects(user?.role) || doc.uploaded_by_id === user?.id) && (
                              <Button size="sm" variant="ghost" onClick={() => deleteDocument(doc)} icon={<Trash2 size={13} />}>Delete</Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="p-5">
            {!canManageProjects(user?.role) ? (
              <EmptyState icon={<History size={22} />} title="Audit history is restricted" text="Only HR Admin and Super Admin can view project audit history." />
            ) : tabLoading ? (
              <div className="py-12 text-center text-sm text-gray-500">Loading audit history...</div>
            ) : auditLogs.length === 0 ? (
              <EmptyState icon={<History size={22} />} title="No audit events" text="Project changes will appear here." />
            ) : (
              <div className="space-y-3">
                {auditLogs.map((log) => (
                  <div key={log.id} className="rounded-xl border border-[#E5E7EB] bg-warm-card p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="font-bold text-[#2F3437]">{label(log.action)}</div>
                      <div className="text-xs font-semibold text-gray-400">{formatDateTime(log.created_at)}</div>
                    </div>
                    <div className="mt-1 text-sm text-gray-500">By {log.actor_name || 'System'}{log.actor_role ? ` · ${label(log.actor_role)}` : ''}</div>
                    {log.metadata_json && (
                      <pre className="mt-3 max-h-32 overflow-auto rounded-lg bg-warm-bg p-3 text-xs text-gray-600">
                        {JSON.stringify(log.metadata_json, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Card>

      <AssignEmployeeModal
        open={assignOpen || Boolean(editingAllocation)}
        project={project}
        user={user}
        allocation={editingAllocation}
        onClose={() => {
          setAssignOpen(false);
          setEditingAllocation(null);
        }}
        onAssigned={async () => {
          showToast({ message: editingAllocation ? 'Assignment updated' : 'Employee assigned to project' });
          setEditingAllocation(null);
          setAssignOpen(false);
          await Promise.all([loadAllocations(), loadProject()]);
        }}
      />

      {managerOpen && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-[#111827]/45 px-4 py-8 backdrop-blur-sm">
          <Card className="w-full max-w-lg overflow-hidden shadow-[0_24px_80px_rgba(15,23,42,0.28)]">
            <div className="flex items-start justify-between border-b border-[#E5E7EB] px-6 py-5">
              <div>
                <h2 className="text-lg font-bold text-[#2F3437]">Assign Project Manager</h2>
                <p className="mt-1 text-sm text-gray-500">{project.name}</p>
              </div>
              <button onClick={() => setManagerOpen(false)} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg hover:text-[#2F3437]">
                <X size={18} />
              </button>
            </div>
            <div className="px-6 py-5">
              <label className="space-y-1.5">
                <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Project Manager</span>
                <select value={selectedManagerId} onChange={(event) => setSelectedManagerId(event.target.value)} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium outline-none focus:border-accent">
                  <option value="">No manager assigned</option>
                  {managerOptions.map((manager) => (
                    <option key={manager.id} value={manager.id}>{manager.name || manager.work_email}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex justify-end gap-3 border-t border-[#E5E7EB] px-6 py-4">
              <Button variant="ghost" onClick={() => setManagerOpen(false)}>Cancel</Button>
              <Button onClick={saveManager}>Save Manager</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#E5E7EB] bg-warm-card p-4">
      <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{label}</div>
      <div className="mt-2 text-lg font-bold text-[#2F3437]">{value}</div>
    </div>
  );
}

function AssignmentMini({ allocation }: { allocation: AllocationRecord }) {
  const name = allocation.employee_name || allocation.employee_email || 'Employee';
  return (
    <div className="flex items-center gap-3 rounded-xl border border-[#E5E7EB] bg-warm-card px-3 py-3">
      <Avatar initials={initials(name)} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-bold text-[#2F3437]">{name}</div>
        <div className="truncate text-xs text-gray-500">{allocation.allocation_role}</div>
      </div>
      <div className="text-sm font-bold text-[#2F3437]">{allocation.allocation_percentage}%</div>
    </div>
  );
}

function AssignmentsTable({
  allocations,
  canEdit,
  onEdit,
  onDelete,
}: {
  allocations: AllocationRecord[];
  canEdit: boolean;
  onEdit: (allocation: AllocationRecord) => void;
  onDelete: (allocation: AllocationRecord) => void;
}) {
  if (allocations.length === 0) {
    return <EmptyState icon={<Users size={22} />} title="No employees assigned" text="Add employees to start tracking project staffing." />;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[#E5E7EB]">
      <table className="w-full min-w-[900px] text-left">
        <thead className="bg-warm-bg text-[11px] font-bold uppercase tracking-wide text-gray-400">
          <tr>
            <th className="px-4 py-3">Employee</th>
            <th className="px-4 py-3">Role</th>
            <th className="px-4 py-3">Manager</th>
            <th className="px-4 py-3">Allocation</th>
            <th className="px-4 py-3">Billing</th>
            <th className="px-4 py-3">Dates</th>
            <th className="px-4 py-3">Status</th>
            {canEdit && <th className="px-4 py-3 text-right">Actions</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-[#E5E7EB]">
          {allocations.map((allocation) => {
            const name = allocation.employee_name || allocation.employee_email || 'Employee';
            return (
              <tr key={allocation.id} className="text-sm text-[#2F3437]">
                <td className="px-4 py-4">
                  <div className="flex items-center gap-3">
                    <Avatar initials={initials(name)} size="sm" />
                    <div>
                      <div className="font-bold">{name}</div>
                      <div className="text-xs text-gray-500">{allocation.employee_email || '-'}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-4 font-semibold">{allocation.allocation_role}</td>
                <td className="px-4 py-4 text-gray-600">{allocation.manager_name || '-'}</td>
                <td className="px-4 py-4 font-bold">{allocation.allocation_percentage}%</td>
                <td className="px-4 py-4 text-gray-600">{label(allocation.billing_type)}</td>
                <td className="px-4 py-4 text-gray-600">{formatDate(allocation.start_date)} - {formatDate(allocation.end_date)}</td>
                <td className="px-4 py-4"><Badge variant={statusVariant[allocation.status] || 'neutral'}>{label(allocation.status)}</Badge></td>
                {canEdit && (
                  <td className="px-4 py-4">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" onClick={() => onEdit(allocation)} icon={<Edit3 size={13} />}>Edit</Button>
                      <Button size="sm" variant="ghost" onClick={() => onDelete(allocation)} icon={<Trash2 size={13} />}>Remove</Button>
                    </div>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-[#DADDE2] bg-warm-bg px-6 py-12 text-center">
      <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-accent-light text-accent">{icon}</div>
      <div className="text-sm font-bold text-[#2F3437]">{title}</div>
      <div className="mt-1 text-sm text-gray-500">{text}</div>
    </div>
  );
}

import { useEffect, useMemo, useState, type ElementType } from 'react';
import { useNavigate } from 'react-router-dom';
import { BriefcaseBusiness, Filter, Plus, SearchX, UsersRound } from 'lucide-react';
import { Badge, Button, Card } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { StaffingRequestDrawer, type StaffingRequestFormOptions, type StaffingRequestPayload } from '@/components/staffing/StaffingRequestDrawer';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface StaffingRequestSummary {
  id: string;
  project_name: string;
  project_id?: string | null;
  role_needed: string;
  allocation_percentage: number;
  headcount_needed: number;
  headcount_fulfilled: number;
  start_date: string;
  end_date?: string | null;
  priority: string;
  status: string;
  requested_by_name: string;
  hiring_manager_name: string;
  created_at: string;
}

function normalizeRole(role?: string) {
  return (role || '').toLowerCase().replace(/\s+/g, '_');
}

function canUseStaffing(role?: string) {
  return ['super_admin', 'admin', 'hr_admin', 'global_access', 'manager'].includes(normalizeRole(role));
}

function isHr(role?: string) {
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalizeRole(role));
}

function formatDate(value?: string | null) {
  if (!value) return 'Open-ended';
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function titleCase(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusVariant(status: string): 'olive' | 'success' | 'warning' | 'error' | 'neutral' | 'info' {
  if (status === 'fulfilled') return 'success';
  if (status === 'partially_fulfilled') return 'info';
  if (status === 'in_review') return 'warning';
  if (status === 'cancelled' || status === 'rejected') return 'error';
  return 'olive';
}

function priorityVariant(priority: string): 'olive' | 'success' | 'warning' | 'error' | 'neutral' | 'info' {
  if (priority === 'urgent') return 'error';
  if (priority === 'high') return 'warning';
  if (priority === 'low') return 'neutral';
  return 'olive';
}

export function StaffingRequestsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [rows, setRows] = useState<StaffingRequestSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [options, setOptions] = useState<StaffingRequestFormOptions | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [priority, setPriority] = useState('all');
  const [department, setDepartment] = useState('all');

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': normalizeRole(user?.role),
  }), [user]);

  const loadOptions = async () => {
    const res = await fetch(`${API_BASE}/staffing-requests/options`, { headers });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Unable to load staffing options.');
    setOptions(data);
  };

  const loadRows = async () => {
    if (!canUseStaffing(user?.role)) return;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ page: String(page), per_page: '25' });
      if (status !== 'all') params.set('status', status);
      if (priority !== 'all') params.set('priority', priority);
      if (department !== 'all') params.set('department', department);
      if (search.trim()) params.set('project_name', search.trim());
      const res = await fetch(`${API_BASE}/staffing-requests?${params.toString()}`, { headers });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Unable to load staffing requests.');
      setRows(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setRows([]);
      setTotal(0);
      setError(err instanceof Error ? err.message : 'Unable to load staffing requests.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!canUseStaffing(user?.role)) return;
    loadOptions().catch((err) => setError(err instanceof Error ? err.message : 'Unable to load options.'));
  }, [headers, user?.role]);

  useEffect(() => {
    loadRows();
  }, [headers, page, status, priority, department, search, user?.role]);

  const metrics = useMemo(() => {
    const open = rows.filter((row) => row.status === 'open').length;
    const review = rows.filter((row) => row.status === 'in_review').length;
    const fulfilled = rows.filter((row) => row.status === 'fulfilled').length;
    const headcount = rows.reduce((sum, row) => sum + Math.max(0, row.headcount_needed - row.headcount_fulfilled), 0);
    return { open, review, fulfilled, headcount };
  }, [rows]);

  const submitRequest = async (payload: StaffingRequestPayload) => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/staffing-requests`, { method: 'POST', headers, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Unable to create staffing request.');
      showToast({ message: 'Staffing request created.' });
      setDrawerOpen(false);
      navigate(`/staffing-requests/${data.id}`);
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Unable to create staffing request.' });
    } finally {
      setSaving(false);
    }
  };

  const cancelRequest = async (requestId: string) => {
    if (!window.confirm('Cancel this staffing request?')) return;
    try {
      const res = await fetch(`${API_BASE}/staffing-requests/${requestId}`, { method: 'DELETE', headers });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Unable to cancel staffing request.');
      showToast({ message: 'Staffing request cancelled.' });
      loadRows();
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Unable to cancel staffing request.' });
    }
  };

  if (!canUseStaffing(user?.role)) {
    return (
      <div>
        <h1 className="mb-1 text-2xl font-bold text-[var(--color-brand-navy)]">Staffing Requests</h1>
        <p className="mb-6 text-sm text-gray-500">Request project staffing and review candidate matches.</p>
        <Card className="p-10 text-center">
          <div className="text-[15px] font-semibold text-[var(--color-brand-navy)]">Access restricted</div>
          <div className="mt-1 text-sm text-gray-500">Only managers, HR, and admins can access staffing requests.</div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <h1 className="mb-1 text-2xl font-bold text-[var(--color-brand-navy)]">Staffing Requests</h1>
          <p className="text-sm text-gray-500">Capture resource demand and match available employees to projects.</p>
        </div>
        <Button icon={<Plus size={16} />} onClick={() => setDrawerOpen(true)}>New Request</Button>
      </div>

      <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-4">
        {([
          ['Open Requests', metrics.open, BriefcaseBusiness],
          ['In Review', metrics.review, Filter],
          ['Fulfilled', metrics.fulfilled, UsersRound],
          ['Open Headcount', metrics.headcount, UsersRound],
        ] as Array<[string, number, ElementType]>).map(([label, value, Icon]) => (
          <Card key={label} className="p-4">
            <Icon size={18} className="mb-4 text-olive" />
            <div className="text-2xl font-bold text-[var(--color-brand-navy)]">{value}</div>
            <div className="text-xs font-semibold text-gray-500">{label}</div>
          </Card>
        ))}
      </div>

      <Card className="mb-5 p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_170px_170px_190px]">
          <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search project name..." className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-sm outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10" />
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-sm outline-none">
            <option value="all">All status</option>
            {['open', 'in_review', 'partially_fulfilled', 'fulfilled', 'cancelled', 'rejected'].map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}
          </select>
          <select value={priority} onChange={(event) => { setPriority(event.target.value); setPage(1); }} className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-sm outline-none">
            <option value="all">All priority</option>
            {['low', 'medium', 'high', 'urgent'].map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}
          </select>
          <select value={department} onChange={(event) => { setDepartment(event.target.value); setPage(1); }} className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-sm outline-none">
            <option value="all">All departments</option>
            {(options?.departments || []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <div className="text-sm font-bold text-[var(--color-brand-navy)]">Demand Pipeline</div>
            <div className="text-xs text-gray-500">{total} request{total === 1 ? '' : 's'}</div>
          </div>
        </div>

        {loading ? (
          <div className="divide-y divide-[var(--color-border)]">
            {Array.from({ length: 5 }).map((_, index) => <div key={index} className="h-20 animate-pulse bg-gray-50/60" />)}
          </div>
        ) : error ? (
          <div className="px-6 py-16 text-center text-sm text-status-error">{error}</div>
        ) : rows.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <SearchX size={24} className="mx-auto mb-3 text-olive" />
            <div className="font-semibold text-[var(--color-brand-navy)]">No staffing requests found</div>
            <div className="mt-1 text-sm text-gray-500">Create a new request or adjust your filters.</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px] text-left">
              <thead className="bg-warm-bg">
                <tr className="text-[11px] font-bold uppercase tracking-wide text-gray-400">
                  <th className="px-5 py-3">Project / Role</th>
                  <th className="px-4 py-3">Manager</th>
                  <th className="px-4 py-3">Need</th>
                  <th className="px-4 py-3">Dates</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t border-[var(--color-border)] text-sm">
                    <td className="px-5 py-4">
                      <div className="font-bold text-[var(--color-brand-navy)]">{row.project_name}</div>
                      <div className="text-xs text-gray-500">{row.role_needed} • {row.allocation_percentage}% allocation</div>
                    </td>
                    <td className="px-4 py-4 text-gray-600">{row.hiring_manager_name}</td>
                    <td className="px-4 py-4">
                      <div className="font-semibold text-[var(--color-brand-navy)]">{row.headcount_fulfilled}/{row.headcount_needed}</div>
                      <div className="mt-1 h-1.5 w-24 rounded-full bg-hover-bg">
                        <div className="h-full rounded-full bg-olive" style={{ width: `${Math.min(100, (row.headcount_fulfilled / row.headcount_needed) * 100)}%` }} />
                      </div>
                    </td>
                    <td className="px-4 py-4 text-gray-600">{formatDate(row.start_date)} - {formatDate(row.end_date)}</td>
                    <td className="px-4 py-4"><Badge variant={priorityVariant(row.priority)}>{titleCase(row.priority)}</Badge></td>
                    <td className="px-4 py-4"><Badge variant={statusVariant(row.status)}>{titleCase(row.status)}</Badge></td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => navigate(`/staffing-requests/${row.id}`)}>View</Button>
                        <Button variant="soft" size="sm" onClick={() => navigate(`/staffing-requests/${row.id}?tab=candidates`)}>Candidates</Button>
                        {(row.status === 'open' || isHr(user?.role)) && (
                          <Button variant="ghost" size="sm" onClick={() => cancelRequest(row.id)} className={cn(row.status !== 'open' && !isHr(user?.role) && 'hidden')}>Cancel</Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-[var(--color-border)] px-5 py-3">
          <div className="text-xs text-gray-500">Page {page}</div>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</Button>
            <Button variant="ghost" size="sm" disabled={page * 25 >= total} onClick={() => setPage((current) => current + 1)}>Next</Button>
          </div>
        </div>
      </Card>

      <StaffingRequestDrawer
        open={drawerOpen}
        mode="create"
        options={options}
        currentUserId={user?.id}
        saving={saving}
        onClose={() => setDrawerOpen(false)}
        onSubmit={submitRequest}
      />
    </div>
  );
}

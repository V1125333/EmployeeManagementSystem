import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, ShieldCheck } from 'lucide-react';
import { Badge, Button, Card } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = 'http://localhost:8000/api/v1';

interface AuditLogRow {
  id: string;
  created_at: string;
  actor_name?: string | null;
  actor_role?: string | null;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  changed_fields?: Record<string, unknown> | null;
  reason?: string | null;
  source: string;
  metadata_json?: Record<string, unknown> | null;
}

function formatDateTime(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function labelize(value?: string | null) {
  return (value || '-').replace(/[._-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function changedFieldsLabel(changedFields?: Record<string, unknown> | null) {
  const keys = Object.keys(changedFields || {});
  if (!keys.length) return '-';
  return keys.slice(0, 4).join(', ') + (keys.length > 4 ? ` +${keys.length - 4}` : '');
}

function sourceVariant(source: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'olive' {
  if (source === 'admin') return 'olive';
  if (source === 'system') return 'info';
  if (source === 'user') return 'success';
  return 'neutral';
}

export function AuditTrailPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState<AuditLogRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({
    search: '',
    actor: '',
    entity_type: '',
    action: '',
    source: '',
    sensitive_only: false,
  });

  const role = (user?.role || '').toLowerCase().replace(/\s+/g, '_');
  const canView = ['super_admin', 'hr_admin', 'global_access'].includes(role);
  const perPage = 25;
  const totalPages = Math.max(1, Math.ceil(total / perPage));

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const loadLogs = useCallback(async () => {
    if (!user || !canView) return;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ page: String(page), per_page: String(perPage) });
      Object.entries(filters).forEach(([key, value]) => {
        if (typeof value === 'boolean') {
          if (value) params.set(key, 'true');
        } else if (value.trim()) {
          params.set(key, value.trim());
        }
      });
      const res = await fetch(`${API_BASE}/audit-logs?${params.toString()}`, { headers });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail || 'Could not load audit logs.');
      setRows(body.items || []);
      setTotal(body.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load audit logs.');
    } finally {
      setLoading(false);
    }
  }, [canView, filters, headers, page, user]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    setPage(1);
  }, [filters]);

  if (!canView) {
    return (
      <div className="animate-fade-up">
        <h1 className="mb-1 text-2xl font-bold tracking-tight text-[#2F3437]">Audit Trail</h1>
        <p className="mb-6 text-sm text-gray-500">Global audit trail access is restricted.</p>
        <Card className="p-6 text-sm text-status-error">Only Super Admin and HR Admin can view audit logs.</Card>
      </div>
    );
  }

  return (
    <div className="animate-fade-up">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[#2F3437]">Audit Trail</h1>
          <p className="text-sm text-gray-500">Review append-only business, security, and compliance events across Reknew Orbit.</p>
        </div>
        <Button variant="ghost" onClick={loadLogs} disabled={loading}>Refresh</Button>
      </div>

      {error && <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      <Card className="mb-4 p-4">
        <div className="grid gap-3 xl:grid-cols-[1.4fr_1fr_1fr_1fr_1fr_auto]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
            <input
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Search actor, entity, field, reason..."
              className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-bg pl-9 pr-3 text-sm outline-none focus:border-olive"
            />
          </label>
          <input value={filters.actor} onChange={(event) => setFilters((current) => ({ ...current, actor: event.target.value }))} placeholder="Actor" className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm outline-none focus:border-olive" />
          <input value={filters.entity_type} onChange={(event) => setFilters((current) => ({ ...current, entity_type: event.target.value }))} placeholder="Entity type" className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm outline-none focus:border-olive" />
          <input value={filters.action} onChange={(event) => setFilters((current) => ({ ...current, action: event.target.value }))} placeholder="Action" className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm outline-none focus:border-olive" />
          <select value={filters.source} onChange={(event) => setFilters((current) => ({ ...current, source: event.target.value }))} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm outline-none focus:border-olive">
            <option value="">Source: All</option>
            <option value="admin">Admin</option>
            <option value="user">User</option>
            <option value="system">System</option>
            <option value="api">API</option>
          </select>
          <label className="flex h-11 items-center gap-2 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm font-semibold text-[#5F6F5A]">
            <input type="checkbox" checked={filters.sensitive_only} onChange={(event) => setFilters((current) => ({ ...current, sensitive_only: event.target.checked }))} className="h-4 w-4 accent-olive" />
            Sensitive
          </label>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-4">
          <div className="flex items-center gap-2 font-bold text-[#2F3437]"><ShieldCheck size={17} className="text-olive" /> Audit Events</div>
          <div className="text-xs font-semibold text-gray-400">{total} records</div>
        </div>
        {loading ? (
          <div className="p-8 text-center text-sm text-gray-500">Loading audit logs...</div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center text-sm text-gray-500">No audit events match the current filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1120px] text-sm">
              <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="px-5 py-3 text-left">Date/Time</th>
                  <th className="px-5 py-3 text-left">Actor</th>
                  <th className="px-5 py-3 text-left">Role</th>
                  <th className="px-5 py-3 text-left">Action</th>
                  <th className="px-5 py-3 text-left">Entity</th>
                  <th className="px-5 py-3 text-left">Changed Fields</th>
                  <th className="px-5 py-3 text-left">Reason</th>
                  <th className="px-5 py-3 text-left">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB]">
                {rows.map((row) => (
                  <tr key={row.id} className="align-top">
                    <td className="px-5 py-3 whitespace-nowrap text-gray-600">{formatDateTime(row.created_at)}</td>
                    <td className="px-5 py-3 font-semibold text-[#2F3437]">{row.actor_name || 'System'}</td>
                    <td className="px-5 py-3 text-gray-600">{labelize(row.actor_role)}</td>
                    <td className="px-5 py-3"><span className="font-mono text-xs text-[#2F3437]">{row.action}</span></td>
                    <td className="px-5 py-3">
                      <div className="font-semibold text-[#2F3437]">{row.entity_type}</div>
                      <div className="max-w-[180px] truncate text-xs text-gray-400">{row.entity_id || '-'}</div>
                    </td>
                    <td className="px-5 py-3 text-gray-600">{changedFieldsLabel(row.changed_fields)}</td>
                    <td className="max-w-[260px] px-5 py-3 text-gray-600"><div className="line-clamp-2">{row.reason || '-'}</div></td>
                    <td className="px-5 py-3"><Badge variant={sourceVariant(row.source)}>{labelize(row.source)}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-[#E5E7EB] px-5 py-3 text-sm text-gray-500">
          <span>Page {page} of {totalPages}</span>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button>
            <Button size="sm" variant="ghost" disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>Next</Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

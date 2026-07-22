import { useCallback, useEffect, useMemo, useState } from 'react';
import { Copy, Download, FileSearch, Search, ShieldCheck } from 'lucide-react';
import { Badge, Button, Card, Avatar } from '@/components/ui';
import { Drawer } from '@/components/ui/Drawer';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';
import type { AuditFilters, AuditLogPage, AuditLogRow } from '@/types/audit';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const PER_PAGE = 25;

const entityRoutes: Record<string, string> = {
  employee: '/employees',
  leave: '/time-off',
  leave_request: '/time-off',
  timesheet: '/timesheets',
  allocation: '/team-allocation',
  staffing_request: '/staffing-requests',
};

const defaultFilters: AuditFilters = {
  search: '',
  actor: '',
  entity_type: '',
  action: '',
  source: '',
  sensitive_only: false,
  date_from: '',
  date_to: '',
};

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

function initials(name?: string | null) {
  return (name || 'System').split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'SY';
}

function sourceVariant(source: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'olive' {
  if (source === 'admin') return 'olive';
  if (source === 'system') return 'info';
  if (source === 'user') return 'success';
  if (source === 'api') return 'warning';
  return 'neutral';
}

function changedFieldsLabel(changedFields?: AuditLogRow['changed_fields']) {
  const keys = Object.keys(changedFields || {});
  if (!keys.length) return '-';
  return keys.slice(0, 4).join(', ') + (keys.length > 4 ? ` +${keys.length - 4}` : '');
}

function stringifyValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function isMasked(value: unknown) {
  return typeof value === 'string' && /^\[(REDACTED|SENSITIVE|.*_CHANGED)/.test(value);
}

function buildParams(filters: AuditFilters, includePaging: boolean, page: number) {
  const params = new URLSearchParams();
  if (includePaging) {
    params.set('page', String(page));
    params.set('per_page', String(PER_PAGE));
  }
  Object.entries(filters).forEach(([key, value]) => {
    if (typeof value === 'boolean') {
      if (value) params.set(key, 'true');
    } else if (value.trim()) {
      params.set(key, value.trim());
    }
  });
  return params;
}

function KpiCard({ label, value, tone }: { label: string; value: number; tone: 'neutral' | 'error' | 'olive' | 'info' }) {
  const toneClass = {
    neutral: 'text-[var(--color-brand-navy)]',
    error: 'text-status-error',
    olive: 'text-accent',
    info: 'text-status-info',
  }[tone];
  return (
    <Card className="p-4">
      <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{label}</div>
      <div className={cn('mt-2 text-2xl font-bold', toneClass)}>{value}</div>
    </Card>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  const [open, setOpen] = useState(false);
  const { showToast } = useToast();
  const text = JSON.stringify(value || {}, null, 2);
  return (
    <div className="rounded-lg border border-[var(--color-border)]">
      <button className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-bold text-[var(--color-brand-navy)]" onClick={() => setOpen((value) => !value)}>
        {title}
        <span className="text-xs text-gray-400">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && (
        <div className="border-t border-[var(--color-border)] p-3">
          <div className="mb-2 flex justify-end">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                navigator.clipboard.writeText(text);
                showToast({ message: `${title} copied.` });
              }}
            >
              <Copy size={14} /> Copy
            </Button>
          </div>
          <pre className="max-h-64 overflow-auto rounded-lg bg-warm-bg p-3 text-xs text-gray-700">{text}</pre>
        </div>
      )}
    </div>
  );
}

function AuditDetailDrawer({ row, onClose }: { row: AuditLogRow | null; onClose: () => void }) {
  if (!row) return null;
  const route = entityRoutes[row.entity_type];
  const changed = Object.entries(row.changed_fields || {});
  return (
    <Drawer
      open={!!row}
      onClose={onClose}
      title={row.action}
      subtitle={`${labelize(row.entity_type)} ${row.entity_id || ''}`}
      width="w-[760px] max-w-[calc(100vw-32px)]"
      footer={route ? (
        <div className="flex justify-end">
          <Button variant="ghost" onClick={() => { window.location.href = route; }}>View Entity</Button>
        </div>
      ) : undefined}
    >
      <div className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Card className="p-4">
            <div className="mb-3 flex items-center gap-3">
              <Avatar initials={initials(row.actor_name)} size="md" />
              <div>
                <div className="font-bold text-[var(--color-brand-navy)]">{row.actor_name || 'System'}</div>
                <div className="text-xs text-gray-500">{labelize(row.actor_role)}</div>
              </div>
            </div>
            <div className="text-xs text-gray-500">{formatDateTime(row.created_at)}</div>
          </Card>
          <Card className="space-y-2 p-4 text-sm">
            <div className="flex justify-between gap-4"><span className="text-gray-400">Source</span><Badge variant={sourceVariant(row.source)}>{labelize(row.source)}</Badge></div>
            <div className="flex justify-between gap-4"><span className="text-gray-400">IP address</span><span>{row.ip_address || '-'}</span></div>
            <div className="flex justify-between gap-4"><span className="text-gray-400">User agent</span><span className="max-w-[260px] truncate" title={row.user_agent || ''}>{row.user_agent || '-'}</span></div>
          </Card>
        </div>

        {changed.length > 0 && (
          <Card className="overflow-hidden">
            <div className="border-b border-[var(--color-border)] px-4 py-3 text-sm font-bold text-[var(--color-brand-navy)]">Changed Fields</div>
            <div className="divide-y divide-[var(--color-border)]">
              {changed.map(([field, diff]) => (
                <div key={field} className="grid gap-3 p-4 lg:grid-cols-[180px_1fr_1fr]">
                  <div className="text-sm font-bold text-[var(--color-brand-navy)]">{labelize(field)}</div>
                  <pre className="min-h-12 whitespace-pre-wrap rounded-lg bg-status-error/5 p-3 text-xs text-status-error">{isMasked(diff.old) ? 'Lock ' : '- '}{stringifyValue(diff.old)}</pre>
                  <pre className="min-h-12 whitespace-pre-wrap rounded-lg bg-status-success/5 p-3 text-xs text-status-success">{isMasked(diff.new) ? 'Lock ' : '+ '}{stringifyValue(diff.new)}</pre>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card className="p-4">
          <div className="mb-2 text-sm font-bold text-[var(--color-brand-navy)]">Reason / Notes</div>
          <div className="text-sm text-gray-600">{row.reason || 'No reason recorded.'}</div>
        </Card>

        <JsonBlock title="Old Values" value={row.old_values} />
        <JsonBlock title="New Values" value={row.new_values} />
        <JsonBlock title="Metadata" value={row.metadata_json} />
      </div>
    </Drawer>
  );
}

function SkeletonRows() {
  return (
    <div className="divide-y divide-[var(--color-border)]">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="grid grid-cols-8 gap-4 px-5 py-4">
          {Array.from({ length: 8 }).map((__, cell) => (
            <div key={cell} className="h-4 animate-pulse rounded bg-gray-100" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function AuditTrailPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [rows, setRows] = useState<AuditLogRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [jumpPage, setJumpPage] = useState('1');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<AuditLogRow | null>(null);
  const [filters, setFilters] = useState<AuditFilters>(defaultFilters);

  const role = (user?.role || '').toLowerCase().replace(/\s+/g, '_');
  const canView = ['super_admin', 'hr_admin', 'global_access'].includes(role);
  const canExport = role === 'super_admin';
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': user?.role || '',
    'x-user-name': user?.name || '',
  }), [user]);

  const loadLogs = useCallback(async () => {
    if (!user || !canView) return;
    setLoading(true);
    setError('');
    try {
      const params = buildParams(filters, true, page);
      const res = await fetch(`${API_BASE}/audit-logs?${params.toString()}`, { headers });
      const body: AuditLogPage | null = await res.json().catch(() => null);
      if (!res.ok) throw new Error((body as { detail?: string } | null)?.detail || 'Could not load audit logs.');
      setRows(body?.items || []);
      setTotal(body?.total || 0);
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

  useEffect(() => {
    setJumpPage(String(page));
  }, [page]);

  const kpis = useMemo(() => ({
    security: rows.filter((row) => row.metadata_json?.security_event === true || row.action.includes('.denied')).length,
    admin: rows.filter((row) => row.source === 'admin').length,
    diff: rows.filter((row) => Object.keys(row.changed_fields || {}).length > 0).length,
  }), [rows]);

  const activeFilterCount = Object.entries(filters).filter(([, value]) => typeof value === 'boolean' ? value : value.trim()).length;
  const from = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
  const to = Math.min(total, page * PER_PAGE);

  async function exportCsv() {
    if (!canExport) return;
    setExporting(true);
    try {
      const params = buildParams(filters, false, page);
      const res = await fetch(`${API_BASE}/audit-logs/export?${params.toString()}`, { headers });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || 'Could not export audit logs.');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `audit-export-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      showToast({ message: 'Audit log exported' });
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not export audit logs.' });
    } finally {
      setExporting(false);
    }
  }

  if (!canView) {
    return (
      <div className="animate-fade-up">
        <h1 className="mb-1 text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Audit Trail</h1>
        <p className="mb-6 text-sm text-gray-500">Global audit trail access is restricted.</p>
        <Card className="p-6 text-sm text-status-error">Only Super Admin and HR Admin can view audit logs.</Card>
      </div>
    );
  }

  return (
    <div className="animate-fade-up">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Audit Trail</h1>
          <p className="text-sm text-gray-500">Review append-only business, security, and compliance events across Reknew Orbit.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={loadLogs} disabled={loading}>Refresh</Button>
          {canExport && <Button variant="ghost" onClick={exportCsv} disabled={exporting}><Download size={16} /> {exporting ? 'Exporting...' : 'Export CSV'}</Button>}
        </div>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <KpiCard label="Total events" value={total} tone="neutral" />
        <KpiCard label="Security events" value={kpis.security} tone="error" />
        <KpiCard label="Admin actions" value={kpis.admin} tone="olive" />
        <KpiCard label="Changes with diff" value={kpis.diff} tone="info" />
      </div>

      {error && <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      <Card className="mb-4 p-4">
        <div className="grid gap-3 2xl:grid-cols-[1.4fr_0.8fr_0.8fr_1fr_1fr_1fr_1fr_auto]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
            <input value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="Search actor, entity, field, reason..." className="h-11 w-full rounded-lg border border-[var(--color-border)] bg-warm-bg pl-9 pr-3 text-sm outline-none focus:border-accent" />
          </label>
          <input type="date" value={filters.date_from} onChange={(event) => setFilters((current) => ({ ...current, date_from: event.target.value }))} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-accent" aria-label="From date" />
          <input type="date" value={filters.date_to} onChange={(event) => setFilters((current) => ({ ...current, date_to: event.target.value }))} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-accent" aria-label="To date" />
          <input value={filters.actor} onChange={(event) => setFilters((current) => ({ ...current, actor: event.target.value }))} placeholder="Actor" className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-accent" />
          <input value={filters.entity_type} onChange={(event) => setFilters((current) => ({ ...current, entity_type: event.target.value }))} placeholder="Entity type" className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-accent" />
          <input value={filters.action} onChange={(event) => setFilters((current) => ({ ...current, action: event.target.value }))} placeholder="Action" className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-accent" />
          <select value={filters.source} onChange={(event) => setFilters((current) => ({ ...current, source: event.target.value }))} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-accent">
            <option value="">Source: All</option>
            <option value="admin">Admin</option>
            <option value="user">User</option>
            <option value="system">System</option>
            <option value="api">API</option>
          </select>
          <label className="flex h-11 items-center gap-2 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm font-semibold text-accent">
            <input type="checkbox" checked={filters.sensitive_only} onChange={(event) => setFilters((current) => ({ ...current, sensitive_only: event.target.checked }))} className="h-4 w-4 accent-[var(--color-brand-orange)]" />
            Sensitive
          </label>
        </div>
        {activeFilterCount > 0 && (
          <button className="mt-3 text-sm font-semibold text-status-error" onClick={() => setFilters(defaultFilters)}>Clear filters</button>
        )}
      </Card>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div className="flex items-center gap-2 font-bold text-[var(--color-brand-navy)]"><ShieldCheck size={17} className="text-accent" /> Audit Events</div>
          <div className="text-xs font-semibold text-gray-400">{total} records</div>
        </div>
        {loading ? (
          <SkeletonRows />
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-center">
            <FileSearch size={34} className="mb-3 text-gray-300" />
            <div className="font-bold text-[var(--color-brand-navy)]">No audit events match the current filters.</div>
            <p className="mt-1 text-sm text-gray-500">Try a wider date range or clear the filters.</p>
            <Button className="mt-4" variant="ghost" onClick={() => setFilters(defaultFilters)}>Clear filters</Button>
          </div>
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
              <tbody className="divide-y divide-[var(--color-border)]">
                {rows.map((row) => (
                  <tr key={row.id} className="cursor-pointer align-top transition hover:bg-accent-light/30" onClick={() => setSelected(row)}>
                    <td className="whitespace-nowrap px-5 py-3 text-gray-600">{formatDateTime(row.created_at)}</td>
                    <td className="px-5 py-3 font-semibold text-[var(--color-brand-navy)]">{row.actor_name || 'System'}</td>
                    <td className="px-5 py-3 text-gray-600">{labelize(row.actor_role)}</td>
                    <td className="px-5 py-3"><span className="font-mono text-xs text-[var(--color-brand-navy)]">{row.action}</span></td>
                    <td className="px-5 py-3"><div className="font-semibold text-[var(--color-brand-navy)]">{row.entity_type}</div><div className="max-w-[180px] truncate text-xs text-gray-400">{row.entity_id || '-'}</div></td>
                    <td className="px-5 py-3 text-gray-600">{changedFieldsLabel(row.changed_fields)}</td>
                    <td className="max-w-[260px] px-5 py-3 text-gray-600"><div className="line-clamp-2">{row.reason || '-'}</div></td>
                    <td className="px-5 py-3"><Badge variant={sourceVariant(row.source)}>{labelize(row.source)}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border)] px-5 py-3 text-sm text-gray-500">
          <span>Showing {from}-{to} of {total} records</span>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button>
            <label className="flex items-center gap-2 text-xs font-semibold text-gray-400">
              Page
              <input
                value={jumpPage}
                onChange={(event) => setJumpPage(event.target.value)}
                onBlur={() => {
                  const value = Number(jumpPage);
                  setPage(Number.isFinite(value) ? Math.min(totalPages, Math.max(1, value)) : page);
                }}
                className="h-8 w-16 rounded-lg border border-[var(--color-border)] bg-warm-bg px-2 text-sm text-[var(--color-brand-navy)] outline-none focus:border-accent"
              />
              of {totalPages}
            </label>
            <Button size="sm" variant="ghost" disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>Next</Button>
          </div>
        </div>
      </Card>
      <AuditDetailDrawer row={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

import { useEffect, useMemo, useState } from 'react';
import { CheckCircle, Copy, LockKeyhole, RefreshCw, ShieldCheck, X } from 'lucide-react';
import { Badge, Button, Card, CardHeader } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

type LockedAccount = {
  id: string;
  name: string;
  email: string;
  department?: string;
  locked_at?: string;
  locked_reason?: string;
  failed_login_attempts: number;
};

type UnlockRequest = {
  id: string;
  employee_name: string;
  employee_email?: string;
  requested_by: string;
  reason: string;
  status: string;
  created_at?: string;
  reviewed_by?: string;
  admin_notes?: string;
};

type UnlockIntent = {
  url: string;
  title: string;
  employeeName: string;
  defaultNotes: string;
  destructive?: boolean;
} | null;

type UnlockResult = {
  message: string;
  temporaryPassword?: string;
} | null;

function formatDateTime(value?: string) {
  if (!value) return '-';
  return new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function SecurityCenterPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<'locked' | 'requests'>('locked');
  const [lockedAccounts, setLockedAccounts] = useState<LockedAccount[]>([]);
  const [unlockRequests, setUnlockRequests] = useState<UnlockRequest[]>([]);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [unlockIntent, setUnlockIntent] = useState<UnlockIntent>(null);
  const [adminNotes, setAdminNotes] = useState('');
  const [unlockResult, setUnlockResult] = useState<UnlockResult>(null);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user?.id, user?.email]);

  async function loadData() {
    setLoading(true);
    setError('');
    try {
      const [lockedRes, requestRes] = await Promise.all([
        fetch(`${API_BASE}/admin/security/locked-accounts`, { headers }),
        fetch(`${API_BASE}/admin/security/unlock-requests?status=${statusFilter}`, { headers }),
      ]);
      if (!lockedRes.ok || !requestRes.ok) throw new Error('Could not load security data.');
      const lockedData = await lockedRes.json();
      const requestData = await requestRes.json();
      setLockedAccounts(lockedData.items || []);
      setUnlockRequests(requestData.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load security data.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  function openUnlockModal(intent: NonNullable<UnlockIntent>) {
    setUnlockResult(null);
    setAdminNotes(intent.defaultNotes);
    setUnlockIntent(intent);
  }

  function closeUnlockModal() {
    if (actionLoading) return;
    setUnlockIntent(null);
    setUnlockResult(null);
    setAdminNotes('');
  }

  async function submitAction() {
    if (!unlockIntent) return;
    setMessage('');
    setError('');
    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE}${unlockIntent.url}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ admin_notes: adminNotes.trim() || unlockIntent.defaultNotes }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.detail || data.message || 'Action failed.');
      const nextResult = {
        message: data.message || 'Action completed.',
        temporaryPassword: data.temporary_password || undefined,
      };
      setUnlockResult(nextResult);
      if (!nextResult.temporaryPassword) {
        setMessage(nextResult.message);
        setUnlockIntent(null);
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed.');
    } finally {
      setActionLoading(false);
    }
  }

  async function copyTemporaryPassword() {
    if (!unlockResult?.temporaryPassword) return;
    await navigator.clipboard.writeText(unlockResult.temporaryPassword);
    setMessage('Temporary password copied.');
  }

  function actionIntent(url: string, title: string, employeeName: string, defaultNotes: string, destructive = false): NonNullable<UnlockIntent> {
    return { url, title, employeeName, defaultNotes, destructive };
  }

  function UnlockModal() {
    if (!unlockIntent) return null;
    const hasTemporaryPassword = Boolean(unlockResult?.temporaryPassword);
    return (
      <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/45 px-4">
        <div className="w-full max-w-[520px] rounded-2xl border border-[var(--color-border)] bg-white shadow-[0_28px_90px_rgba(17,24,39,0.24)]">
          <div className="flex items-start justify-between border-b border-[var(--color-border)] px-6 py-5">
            <div>
              <div className="text-lg font-bold text-[var(--color-brand-navy)]">{hasTemporaryPassword ? 'Account unlocked' : unlockIntent.title}</div>
              <div className="mt-1 text-sm text-gray-500">{unlockIntent.employeeName}</div>
            </div>
            <button type="button" onClick={closeUnlockModal} className="rounded-lg p-1.5 text-gray-400 transition hover:bg-hover-bg hover:text-[var(--color-brand-navy)]" aria-label="Close">
              <X size={18} />
            </button>
          </div>

          {hasTemporaryPassword ? (
            <div className="space-y-4 px-6 py-5">
              <div className="flex items-start gap-3 rounded-xl border border-status-success/20 bg-status-success/5 px-4 py-3 text-status-success">
                <CheckCircle size={18} className="mt-0.5 shrink-0" />
                <div className="text-sm font-semibold">{unlockResult?.message}</div>
              </div>
              <div>
                <div className="mb-2 text-[12px] font-bold uppercase tracking-wide text-gray-400">Temporary password</div>
                <div className="flex items-center gap-2 rounded-xl border border-[var(--color-border)] bg-warm-bg p-3">
                  <code className="min-w-0 flex-1 select-all truncate text-[15px] font-bold text-[var(--color-brand-navy)]">{unlockResult?.temporaryPassword}</code>
                  <Button size="sm" variant="ghost" icon={<Copy size={14} />} onClick={copyTemporaryPassword}>Copy</Button>
                </div>
                <p className="mt-2 text-xs leading-5 text-gray-500">
                  Share this temporary password securely. The employee will be required to create a new password on next login.
                </p>
              </div>
              <div className="flex justify-end">
                <Button onClick={closeUnlockModal}>Done</Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4 px-6 py-5">
              <label className="block">
                <span className="mb-2 block text-[13px] font-semibold text-[var(--color-brand-navy)]">Admin notes for audit trail</span>
                <textarea
                  value={adminNotes}
                  onChange={(event) => setAdminNotes(event.target.value.slice(0, 500))}
                  className="min-h-[112px] w-full resize-none rounded-xl border border-[var(--color-border)] bg-warm-bg px-3.5 py-3 text-sm font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10"
                  placeholder="Example: Direct admin unlock after identity verification"
                  autoFocus
                />
              </label>
              <div className="rounded-xl bg-warm-bg px-4 py-3 text-xs leading-5 text-gray-500">
                {unlockIntent.destructive
                  ? 'Rejecting keeps the account locked and stores your notes for audit history.'
                  : 'Unlocking generates a temporary password and forces the employee to change it before accessing the app.'}
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={closeUnlockModal} disabled={actionLoading}>Cancel</Button>
                <Button onClick={submitAction} disabled={actionLoading}>
                  {actionLoading ? 'Processing...' : unlockIntent.destructive ? 'Reject Request' : 'Unlock & Generate Password'}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-brand-navy)]">Security Center</h1>
          <p className="mt-1 text-sm text-gray-500">Review locked accounts and account unlock requests.</p>
        </div>
        <Button variant="ghost" icon={<RefreshCw size={15} />} onClick={loadData} disabled={loading}>
          {loading ? 'Refreshing' : 'Refresh'}
        </Button>
      </div>

      {(message || error) && (
        <div className={`rounded-xl border px-4 py-3 text-sm font-semibold ${error ? 'border-status-error/20 bg-status-error/5 text-status-error' : 'border-status-success/20 bg-status-success/5 text-status-success'}`}>
          {error || message}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-5"><div className="text-xs font-bold uppercase tracking-wide text-gray-400">Locked Accounts</div><div className="mt-2 text-3xl font-bold">{lockedAccounts.length}</div></Card>
        <Card className="p-5"><div className="text-xs font-bold uppercase tracking-wide text-gray-400">Pending Requests</div><div className="mt-2 text-3xl font-bold">{unlockRequests.filter((row) => row.status === 'pending').length}</div></Card>
        <Card className="p-5"><div className="text-xs font-bold uppercase tracking-wide text-gray-400">Policy</div><div className="mt-2 text-sm font-semibold text-gray-600">3 failed password attempts lock account</div></Card>
      </div>

      <div className="flex gap-2">
        <Button variant={tab === 'locked' ? 'primary' : 'ghost'} icon={<LockKeyhole size={15} />} onClick={() => setTab('locked')}>Locked Accounts</Button>
        <Button variant={tab === 'requests' ? 'primary' : 'ghost'} icon={<ShieldCheck size={15} />} onClick={() => setTab('requests')}>Unlock Requests</Button>
      </div>

      {tab === 'locked' ? (
        <Card className="overflow-hidden">
          <CardHeader title="Locked Accounts" icon={<LockKeyhole size={16} />} />
          {lockedAccounts.length === 0 ? <div className="px-5 py-10 text-center text-sm text-gray-500">No locked accounts.</div> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-sm">
                <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
                  <tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Department</th><th className="px-5 py-3 text-left">Locked At</th><th className="px-5 py-3 text-left">Reason</th><th className="px-5 py-3 text-left">Attempts</th><th className="px-5 py-3 text-right">Action</th></tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {lockedAccounts.map((row) => (
                    <tr key={row.id}>
                      <td className="px-5 py-3"><div className="font-bold">{row.name}</div><div className="text-xs text-gray-500">{row.email}</div></td>
                      <td className="px-5 py-3">{row.department || '-'}</td>
                      <td className="px-5 py-3">{formatDateTime(row.locked_at)}</td>
                      <td className="px-5 py-3">{row.locked_reason || '-'}</td>
                      <td className="px-5 py-3">{row.failed_login_attempts}</td>
                      <td className="px-5 py-3 text-right"><Button size="sm" onClick={() => openUnlockModal(actionIntent(`/admin/security/locked-accounts/${row.id}/unlock`, 'Unlock account', row.name, 'Direct admin unlock'))}>Unlock</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <CardHeader title="Unlock Requests" action={<select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm"><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="all">All</option></select>} />
          {unlockRequests.length === 0 ? <div className="px-5 py-10 text-center text-sm text-gray-500">No unlock requests found.</div> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-sm">
                <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
                  <tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Requested By</th><th className="px-5 py-3 text-left">Reason</th><th className="px-5 py-3 text-left">Created</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-right">Action</th></tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {unlockRequests.map((row) => (
                    <tr key={row.id}>
                      <td className="px-5 py-3"><div className="font-bold">{row.employee_name}</div><div className="text-xs text-gray-500">{row.employee_email}</div></td>
                      <td className="px-5 py-3">{row.requested_by}</td>
                      <td className="max-w-[320px] px-5 py-3 text-gray-600">{row.reason}</td>
                      <td className="px-5 py-3">{formatDateTime(row.created_at)}</td>
                      <td className="px-5 py-3"><Badge variant={row.status === 'pending' ? 'warning' : row.status === 'approved' ? 'success' : 'error'}>{row.status}</Badge></td>
                      <td className="px-5 py-3 text-right">
                        {row.status === 'pending' ? <div className="flex justify-end gap-2"><Button size="sm" onClick={() => openUnlockModal(actionIntent(`/admin/security/unlock-requests/${row.id}/approve`, 'Approve unlock request', row.employee_name, 'Approved unlock request'))}>Approve</Button><Button size="sm" variant="ghost" onClick={() => openUnlockModal(actionIntent(`/admin/security/unlock-requests/${row.id}/reject`, 'Reject unlock request', row.employee_name, 'Rejected unlock request', true))}>Reject</Button></div> : <span className="text-xs text-gray-400">Reviewed</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
      <UnlockModal />
    </div>
  );
}

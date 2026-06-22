import { useEffect, useMemo, useState } from 'react';
import { LockKeyhole, RefreshCw, ShieldCheck } from 'lucide-react';
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
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

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

  async function postAction(url: string, defaultReason: string) {
    const admin_notes = window.prompt('Add admin notes for audit trail:', defaultReason);
    if (admin_notes === null) return;
    setMessage('');
    setError('');
    try {
      const res = await fetch(`${API_BASE}${url}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ admin_notes }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.detail || data.message || 'Action failed.');
      setMessage(data.message || 'Action completed.');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed.');
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#2F3437]">Security Center</h1>
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
                <tbody className="divide-y divide-[#E5E7EB]">
                  {lockedAccounts.map((row) => (
                    <tr key={row.id}>
                      <td className="px-5 py-3"><div className="font-bold">{row.name}</div><div className="text-xs text-gray-500">{row.email}</div></td>
                      <td className="px-5 py-3">{row.department || '-'}</td>
                      <td className="px-5 py-3">{formatDateTime(row.locked_at)}</td>
                      <td className="px-5 py-3">{row.locked_reason || '-'}</td>
                      <td className="px-5 py-3">{row.failed_login_attempts}</td>
                      <td className="px-5 py-3 text-right"><Button size="sm" onClick={() => postAction(`/admin/security/locked-accounts/${row.id}/unlock`, 'Direct admin unlock')}>Unlock</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <CardHeader title="Unlock Requests" action={<select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm"><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="all">All</option></select>} />
          {unlockRequests.length === 0 ? <div className="px-5 py-10 text-center text-sm text-gray-500">No unlock requests found.</div> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-sm">
                <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
                  <tr><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Requested By</th><th className="px-5 py-3 text-left">Reason</th><th className="px-5 py-3 text-left">Created</th><th className="px-5 py-3 text-left">Status</th><th className="px-5 py-3 text-right">Action</th></tr>
                </thead>
                <tbody className="divide-y divide-[#E5E7EB]">
                  {unlockRequests.map((row) => (
                    <tr key={row.id}>
                      <td className="px-5 py-3"><div className="font-bold">{row.employee_name}</div><div className="text-xs text-gray-500">{row.employee_email}</div></td>
                      <td className="px-5 py-3">{row.requested_by}</td>
                      <td className="max-w-[320px] px-5 py-3 text-gray-600">{row.reason}</td>
                      <td className="px-5 py-3">{formatDateTime(row.created_at)}</td>
                      <td className="px-5 py-3"><Badge variant={row.status === 'pending' ? 'warning' : row.status === 'approved' ? 'success' : 'error'}>{row.status}</Badge></td>
                      <td className="px-5 py-3 text-right">
                        {row.status === 'pending' ? <div className="flex justify-end gap-2"><Button size="sm" onClick={() => postAction(`/admin/security/unlock-requests/${row.id}/approve`, 'Approved unlock request')}>Approve</Button><Button size="sm" variant="ghost" onClick={() => postAction(`/admin/security/unlock-requests/${row.id}/reject`, 'Rejected unlock request')}>Reject</Button></div> : <span className="text-xs text-gray-400">Reviewed</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

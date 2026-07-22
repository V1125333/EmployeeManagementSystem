import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, CheckCircle2, RefreshCw, UserCheck, UserRoundX } from 'lucide-react';
import { Avatar, Badge, Button, Card } from '@/components/ui';
import { AuditTimeline } from '@/components/audit/AuditTimeline';
import { useToast } from '@/components/ui/Toast';
import { Drawer } from '@/components/ui/Drawer';
import { StaffingRequestDrawer, type StaffingRequestFormOptions, type StaffingRequestPayload } from '@/components/staffing/StaffingRequestDrawer';
import { useAuth } from '@/hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface Candidate {
  id: string;
  employee_id: string;
  allocation_id?: string | null;
  employee_name: string;
  department?: string | null;
  designation?: string | null;
  profile_image_url?: string | null;
  match_status: string;
  available_capacity_percentage: number;
  current_allocation_percentage: number;
  next_available_date?: string | null;
  suggested_by: string;
  notes?: string | null;
  created_at: string;
}

interface StaffingRequest {
  id: string;
  project_name: string;
  project_id?: string | null;
  requested_by_name: string;
  hiring_manager_id: string;
  hiring_manager_name: string;
  department?: string | null;
  role_needed: string;
  designation_needed?: string | null;
  skills_required: string[];
  allocation_percentage: number;
  headcount_needed: number;
  headcount_fulfilled: number;
  start_date: string;
  end_date?: string | null;
  priority: string;
  status: string;
  reason?: string | null;
  notes?: string | null;
  rejection_reason?: string | null;
  fulfilled_allocation_ids: string[];
  fulfilled_at?: string | null;
  fulfilled_by?: string | null;
  fulfilled_by_name?: string | null;
  candidates: Candidate[];
  created_at: string;
  updated_at?: string | null;
}

interface Allocation {
  id: string;
  employee_id: string;
  project_name?: string | null;
  manager_id: string;
  manager_name?: string | null;
  allocation_percentage: number;
  allocation_role: string;
  billing_type: string;
  status: string;
  start_date: string;
  end_date?: string | null;
}

interface CapacityCheck {
  is_valid: boolean;
  current_overlapping_total: number;
  requested: number;
  projected_total: number;
  overlapping_allocations: Array<{
    allocation_id: string;
    project_name?: string | null;
    allocation_percentage: number;
    allocation_role?: string | null;
    status?: string | null;
    start_date?: string | null;
    end_date?: string | null;
  }>;
}

function normalizeRole(role?: string) {
  return (role || '').toLowerCase().replace(/\s+/g, '_');
}

function isHr(role?: string) {
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalizeRole(role));
}

function canCreateStaffingAllocation(role?: string) {
  return ['super_admin', 'hr_admin', 'global_access'].includes(normalizeRole(role));
}

function titleCase(value?: string | null) {
  return value ? value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) : '-';
}

function formatDate(value?: string | null) {
  if (!value) return 'Open-ended';
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
}

function statusVariant(status: string): 'olive' | 'success' | 'warning' | 'error' | 'neutral' | 'info' {
  if (status === 'fulfilled' || status === 'selected') return 'success';
  if (status === 'partially_fulfilled' || status === 'shortlisted') return 'info';
  if (status === 'in_review' || status === 'suggested') return 'warning';
  if (status === 'cancelled' || status === 'rejected') return 'error';
  return 'olive';
}

function inputClass() {
  return 'mt-1 w-full rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10';
}

function CreateAllocationDrawer({
  open,
  request,
  candidate,
  options,
  headers,
  saving,
  onClose,
  onCreated,
}: {
  open: boolean;
  request: StaffingRequest;
  candidate: Candidate | null;
  options: StaffingRequestFormOptions | null;
  headers: HeadersInit;
  saving: boolean;
  onClose: () => void;
  onCreated: (data: { staffing_request: StaffingRequest }) => void;
}) {
  const { showToast } = useToast();
  const [role, setRole] = useState(request.role_needed);
  const [allocationPercentage, setAllocationPercentage] = useState(request.allocation_percentage);
  const [startDate, setStartDate] = useState(request.start_date);
  const [endDate, setEndDate] = useState(request.end_date || '');
  const [openEnded, setOpenEnded] = useState(!request.end_date);
  const [managerId, setManagerId] = useState('');
  const [billingType, setBillingType] = useState<'billable' | 'non_billable' | 'internal'>('billable');
  const [notes, setNotes] = useState('');
  const [capacity, setCapacity] = useState<CapacityCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [inlineError, setInlineError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setRole(request.role_needed);
    setAllocationPercentage(request.allocation_percentage);
    setStartDate(request.start_date);
    setEndDate(request.end_date || '');
    setOpenEnded(!request.end_date);
    setManagerId(request.hiring_manager_id || '');
    setBillingType('billable');
    setNotes(`Created from Staffing Request ${request.id}`);
    setCapacity(null);
    setInlineError('');
  }, [open, request]);

  useEffect(() => {
    if (!open || !candidate || !startDate || !allocationPercentage) return;
    const timer = window.setTimeout(async () => {
      setChecking(true);
      setInlineError('');
      try {
        const params = new URLSearchParams({
          allocation_percentage: String(allocationPercentage),
          start_date: startDate,
        });
        if (!openEnded && endDate) params.set('end_date', endDate);
        const res = await fetch(`${API_BASE}/allocations/employee/${candidate.employee_id}/capacity-check?${params.toString()}`, { headers });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Unable to check capacity.');
        setCapacity(data);
      } catch (err) {
        setInlineError(err instanceof Error ? err.message : 'Unable to check capacity.');
      } finally {
        setChecking(false);
      }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [open, candidate?.employee_id, allocationPercentage, startDate, endDate, openEnded, headers]);

  if (!candidate) return null;

  const selectedManagerId = managerId || request.hiring_manager_id || (options?.managers.find((item) => item.name === request.hiring_manager_name)?.id || '');
  const capacityBlocked = capacity ? !capacity.is_valid : false;
  const hasWarning = capacity && capacity.is_valid && capacity.overlapping_allocations.length > 0;

  const submit = async () => {
    if (!selectedManagerId) return setInlineError('Manager is required.');
    if (!role.trim()) return setInlineError('Role is required.');
    if (!startDate) return setInlineError('Start date is required.');
    if (!openEnded && endDate && endDate < startDate) return setInlineError('End date must be on or after start date.');
    if (allocationPercentage < 1 || allocationPercentage > 100) return setInlineError('Allocation percentage must be between 1 and 100.');
    if (capacityBlocked) return;

    setSubmitting(true);
    setInlineError('');
    try {
      const res = await fetch(`${API_BASE}/staffing-requests/${request.id}/create-allocation`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          employee_id: candidate.employee_id,
          overrides: {
            allocation_percentage: allocationPercentage,
            allocation_role: role.trim(),
            start_date: startDate,
            end_date: openEnded ? null : endDate || null,
            manager_id: selectedManagerId,
            billing_type: billingType,
            notes: notes.trim() || null,
          },
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (typeof data.detail === 'object' && data.detail?.projected_total) {
          setCapacity({
            is_valid: false,
            current_overlapping_total: data.detail.current_total,
            requested: data.detail.requested,
            projected_total: data.detail.projected_total,
            overlapping_allocations: data.detail.overlapping_allocations || [],
          });
          return;
        }
        throw new Error(data.detail || 'Unable to create allocation.');
      }
      showToast({ message: 'Allocation created successfully.' });
      if (data.staffing_request?.status === 'fulfilled') showToast({ message: 'Staffing request is now fully fulfilled.' });
      onCreated(data);
    } catch (err) {
      setInlineError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Create Allocation"
      subtitle={`Staffing Request: ${request.project_name} - ${request.role_needed}`}
      width="w-[680px] max-w-[calc(100vw-1.5rem)]"
      footer={(
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs text-status-error">{inlineError}</div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={submit} disabled={saving || submitting || checking || capacityBlocked}>
              {submitting ? 'Creating...' : 'Create Allocation'}
            </Button>
          </div>
        </div>
      )}
    >
      <div className="space-y-4">
        {checking && <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-4 py-3 text-sm text-gray-500">Checking capacity...</div>}
        {capacityBlocked && capacity && (
          <div className="rounded-xl border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
            <div className="flex items-center gap-2 font-bold"><AlertTriangle size={16} /> Cannot create allocation</div>
            <div className="mt-1">Total would reach {capacity.projected_total}% for the selected period. Reduce allocation % or adjust dates.</div>
          </div>
        )}
        {hasWarning && capacity && (
          <div className="rounded-xl border border-status-warning/25 bg-status-warning/10 px-4 py-3 text-sm text-[var(--color-brand-orange)]">
            <div className="font-bold">This employee already has overlapping allocations.</div>
            <div className="mt-2 space-y-1">
              {capacity.overlapping_allocations.map((item) => (
                <div key={item.allocation_id}>{item.project_name || 'Project'} - {item.allocation_percentage}% - {formatDate(item.start_date)} to {formatDate(item.end_date)}</div>
              ))}
            </div>
            <div className="mt-2 font-semibold">Total during overlap: {capacity.current_overlapping_total}% + {allocationPercentage}% = {capacity.projected_total}%</div>
          </div>
        )}

        <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-4 py-3">
          <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Employee</div>
          <div className="mt-2 flex items-center gap-3">
            <Avatar initials={initials(candidate.employee_name)} src={candidate.profile_image_url} variant="filled" />
            <div>
              <div className="font-bold text-[var(--color-brand-navy)]">{candidate.employee_name}</div>
              <div className="text-xs text-gray-500">{candidate.designation || '-'} • {candidate.available_capacity_percentage}% available</div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="text-[12px] font-bold text-gray-500">Project<input value={request.project_name} readOnly className={inputClass()} /></label>
          <label className="text-[12px] font-bold text-gray-500">Role<input value={role} onChange={(event) => setRole(event.target.value)} className={inputClass()} /></label>
          <label className="text-[12px] font-bold text-gray-500">Allocation %<input type="number" min={1} max={100} value={allocationPercentage} onChange={(event) => setAllocationPercentage(Number(event.target.value))} className={inputClass()} /></label>
          <label className="text-[12px] font-bold text-gray-500">Manager
            <select value={selectedManagerId} onChange={(event) => setManagerId(event.target.value)} className={inputClass()}>
              <option value="">Select manager</option>
              {(options?.managers || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label className="text-[12px] font-bold text-gray-500">Start Date<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className={inputClass()} /></label>
          <div>
            <label className="text-[12px] font-bold text-gray-500">End Date<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} disabled={openEnded} className={inputClass()} /></label>
            <label className="mt-2 flex items-center gap-2 text-xs font-semibold text-gray-500"><input type="checkbox" checked={openEnded} onChange={(event) => setOpenEnded(event.target.checked)} /> Open-ended</label>
          </div>
        </div>

        <div>
          <div className="mb-2 text-[12px] font-bold text-gray-500">Billing Type</div>
          <div className="grid grid-cols-3 gap-2">
            {(['billable', 'non_billable', 'internal'] as const).map((item) => (
              <button key={item} onClick={() => setBillingType(item)} className={`rounded-xl border px-3 py-2 text-sm font-bold ${billingType === item ? 'border-olive bg-olive text-white' : 'border-[var(--color-border)] bg-warm-bg text-gray-600'}`}>
                {titleCase(item)}
              </button>
            ))}
          </div>
        </div>

        <label className="text-[12px] font-bold text-gray-500">Notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} className={inputClass()} /></label>
      </div>
    </Drawer>
  );
}

export function StaffingRequestDetailPage() {
  const { requestId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [request, setRequest] = useState<StaffingRequest | null>(null);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [loadingAllocations, setLoadingAllocations] = useState(false);
  const [options, setOptions] = useState<StaffingRequestFormOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [allocationDrawerCandidate, setAllocationDrawerCandidate] = useState<Candidate | null>(null);
  const [candidateFilter, setCandidateFilter] = useState('all');
  const [manualEmployeeId, setManualEmployeeId] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const activeTab = searchParams.get('tab') || 'overview';

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': normalizeRole(user?.role),
  }), [user]);

  const load = async () => {
    if (!requestId) return;
    setLoading(true);
    try {
      const [requestRes, optionsRes] = await Promise.all([
        fetch(`${API_BASE}/staffing-requests/${requestId}`, { headers }),
        fetch(`${API_BASE}/staffing-requests/options`, { headers }),
      ]);
      const requestData = await requestRes.json();
      if (!requestRes.ok) throw new Error(requestData.detail || 'Unable to load staffing request.');
      setRequest(requestData);
      if (optionsRes.ok) setOptions(await optionsRes.json());
      setLoadingAllocations(true);
      const allocationsRes = await fetch(`${API_BASE}/staffing-requests/${requestId}/allocations`, { headers });
      if (allocationsRes.ok) setAllocations(await allocationsRes.json());
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Unable to load staffing request.' });
    } finally {
      setLoading(false);
      setLoadingAllocations(false);
    }
  };

  useEffect(() => {
    load();
  }, [headers, requestId]);

  const action = async (path: string, method = 'POST', body?: Record<string, unknown>) => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Action failed.');
      setRequest(data);
      showToast({ message: 'Updated successfully.' });
      load();
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Action failed.' });
    } finally {
      setSaving(false);
    }
  };

  const saveRequest = async (payload: StaffingRequestPayload) => {
    if (!requestId) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/staffing-requests/${requestId}`, { method: 'PATCH', headers, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Unable to update staffing request.');
      setRequest(data);
      setDrawerOpen(false);
      showToast({ message: 'Staffing request updated.' });
      load();
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Unable to update staffing request.' });
    } finally {
      setSaving(false);
    }
  };

  const filteredCandidates = useMemo(() => {
    if (!request) return [];
    if (candidateFilter === 'all') return request.candidates;
    return request.candidates.filter((item) => item.match_status === candidateFilter);
  }, [request, candidateFilter]);

  if (loading && !request) {
    return <Card className="p-10 text-center text-sm text-gray-500">Loading staffing request...</Card>;
  }

  if (!request) {
    return <Card className="p-10 text-center text-sm text-gray-500">Staffing request not found.</Card>;
  }

  const selected = request.candidates.find((item) => item.match_status === 'selected');

  return (
    <div>
      <div className="mb-5 flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
        <div>
          <Button variant="ghost" size="sm" icon={<ArrowLeft size={14} />} onClick={() => navigate('/staffing-requests')}>Back</Button>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold text-[var(--color-brand-navy)]">{request.project_name}</h1>
            <Badge variant={statusVariant(request.status)}>{titleCase(request.status)}</Badge>
          </div>
          <p className="mt-1 text-sm text-gray-500">{request.role_needed} • {request.allocation_percentage}% allocation • {request.headcount_fulfilled}/{request.headcount_needed} fulfilled</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => setDrawerOpen(true)}>Edit</Button>
          {isHr(user?.role) && request.status === 'open' && <Button variant="soft" onClick={() => action(`/staffing-requests/${request.id}/status`, 'PATCH', { status: 'in_review' })}>Move to Review</Button>}
          {isHr(user?.role) && ['open', 'in_review'].includes(request.status) && (
            <Button variant="ghost" onClick={() => {
              const reason = rejectionReason || window.prompt('Rejection reason') || '';
              setRejectionReason(reason);
              if (reason.trim()) action(`/staffing-requests/${request.id}/status`, 'PATCH', { status: 'rejected', rejection_reason: reason });
            }}>Reject</Button>
          )}
        </div>
      </div>

      <div className="mb-5 flex gap-2 border-b border-[var(--color-border)]">
        {['overview', 'candidates', 'activity'].map((tab) => (
          <button
            key={tab}
            onClick={() => setSearchParams(tab === 'overview' ? {} : { tab })}
            className={`px-4 py-3 text-sm font-bold ${activeTab === tab ? 'border-b-2 border-olive text-olive' : 'text-gray-500 hover:text-[var(--color-brand-navy)]'}`}
          >
            {titleCase(tab)}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_360px]">
          <Card className="p-5">
            <div className="mb-4 text-sm font-bold text-[var(--color-brand-navy)]">Request Details</div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {[
                ['Requested By', request.requested_by_name],
                ['Hiring Manager', request.hiring_manager_name],
                ['Department', request.department || 'Any department'],
                ['Designation Needed', request.designation_needed || 'Any designation'],
                ['Start Date', formatDate(request.start_date)],
                ['End Date', formatDate(request.end_date)],
                ['Priority', titleCase(request.priority)],
                ['Skills', request.skills_required.length ? request.skills_required.join(', ') : 'No specific skills'],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-4 py-3">
                  <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{label}</div>
                  <div className="mt-1 text-sm font-semibold text-[var(--color-brand-navy)]">{value}</div>
                </div>
              ))}
            </div>
            <div className="mt-4 grid gap-4">
              <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-4 py-3">
                <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Reason</div>
                <div className="mt-1 text-sm text-[var(--color-brand-navy)]">{request.reason || 'No reason provided.'}</div>
              </div>
              <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-4 py-3">
                <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Notes</div>
                <div className="mt-1 text-sm text-[var(--color-brand-navy)]">{request.notes || 'No notes provided.'}</div>
              </div>
            </div>
          </Card>
          <Card className="p-5">
            <div className="mb-4 text-sm font-bold text-[var(--color-brand-navy)]">Fulfillment</div>
            <div className="text-3xl font-bold text-olive">{request.headcount_fulfilled} / {request.headcount_needed} <span className="text-lg text-[var(--color-brand-navy)]">Filled</span></div>
            <div className="mt-2 h-2 rounded-full bg-hover-bg">
              <div className="h-full rounded-full bg-olive" style={{ width: `${Math.min(100, (request.headcount_fulfilled / request.headcount_needed) * 100)}%` }} />
            </div>
            <div className="mt-3"><Badge variant={statusVariant(request.status)}>{titleCase(request.status)}</Badge></div>
            {request.fulfilled_at && (
              <div className="mt-2 text-xs text-gray-500">Fulfilled on {formatDateTime(request.fulfilled_at)} by {request.fulfilled_by_name || 'HR'}</div>
            )}
            {selected ? (
              <div className="mt-5 rounded-xl border border-[var(--color-border)] bg-olive/5 p-4">
                <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Selected Candidate</div>
                <div className="mt-2 font-bold text-[var(--color-brand-navy)]">{selected.employee_name}</div>
                <div className="mt-1 text-sm text-gray-500">{selected.designation || '-'} • {selected.available_capacity_percentage}% available</div>
                {canCreateStaffingAllocation(user?.role) && <Button className="mt-4" onClick={() => setAllocationDrawerCandidate(selected)}>Create Allocation</Button>}
              </div>
            ) : (
              <div className="mt-5 text-sm text-gray-500">Select candidates from the Candidate Matches tab to fulfill this request.</div>
            )}
          </Card>
          <Card className="p-5 xl:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <div className="text-sm font-bold text-[var(--color-brand-navy)]">Created Allocations</div>
              <Badge variant="neutral">{allocations.length}</Badge>
            </div>
            {loadingAllocations ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, index) => <div key={index} className="h-12 animate-pulse rounded-xl bg-gray-100" />)}
              </div>
            ) : allocations.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-warm-bg px-5 py-8 text-center text-sm text-gray-500">
                No allocations created yet. Select a candidate from the Candidate Matches tab to create an allocation.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-left">
                  <thead className="bg-warm-bg text-[11px] font-bold uppercase tracking-wide text-gray-400">
                    <tr>
                      <th className="px-4 py-3">Employee</th>
                      <th className="px-4 py-3">Role</th>
                      <th className="px-4 py-3">Allocation %</th>
                      <th className="px-4 py-3">Start</th>
                      <th className="px-4 py-3">End</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allocations.map((allocation) => {
                      const candidate = request.candidates.find((item) => item.employee_id === allocation.employee_id);
                      const name = candidate?.employee_name || allocation.employee_id;
                      return (
                        <tr key={allocation.id} className="border-t border-[var(--color-border)] text-sm">
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <Avatar initials={initials(name)} src={candidate?.profile_image_url} variant="filled" />
                              <span className="font-semibold text-[var(--color-brand-navy)]">{name}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-gray-600">{allocation.allocation_role}</td>
                          <td className="px-4 py-3">
                            <div className="font-bold text-[var(--color-brand-navy)]">{allocation.allocation_percentage}%</div>
                            <div className="mt-1 h-1.5 w-24 rounded-full bg-hover-bg">
                              <div className="h-full rounded-full bg-olive" style={{ width: `${allocation.allocation_percentage}%` }} />
                            </div>
                          </td>
                          <td className="px-4 py-3 text-gray-600">{formatDate(allocation.start_date)}</td>
                          <td className="px-4 py-3 text-gray-600">{formatDate(allocation.end_date)}</td>
                          <td className="px-4 py-3"><Badge variant={statusVariant(allocation.status)}>{titleCase(allocation.status)}</Badge></td>
                          <td className="px-4 py-3 text-right"><Button size="sm" variant="ghost" onClick={() => navigate(`/profile?employee_id=${allocation.employee_id}`)}>View Profile</Button></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'candidates' && (
        <Card>
          <div className="flex flex-col justify-between gap-3 border-b border-[var(--color-border)] px-5 py-4 lg:flex-row lg:items-center">
            <div>
              <div className="text-sm font-bold text-[var(--color-brand-navy)]">Candidate Matches</div>
              <div className="text-xs text-gray-500">Suggested using allocation capacity and availability.</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <select value={candidateFilter} onChange={(event) => setCandidateFilter(event.target.value)} className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2 text-sm">
                {['all', 'suggested', 'shortlisted', 'selected', 'rejected'].map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}
              </select>
                  {isHr(user?.role) && (
                <>
                  <select value={manualEmployeeId} onChange={(event) => setManualEmployeeId(event.target.value)} className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2 text-sm">
                    <option value="">Add manual candidate</option>
                    {(options?.employees || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                  <Button variant="ghost" icon={<UserCheck size={14} />} disabled={!manualEmployeeId || saving} onClick={() => action(`/staffing-requests/${request.id}/candidates/${manualEmployeeId}/shortlist`)}>Shortlist</Button>
                  <Button variant="soft" icon={<RefreshCw size={14} />} disabled={saving} onClick={() => action(`/staffing-requests/${request.id}/candidates/refresh`)}>Refresh</Button>
                </>
              )}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-left">
              <thead className="bg-warm-bg">
                <tr className="text-[11px] font-bold uppercase tracking-wide text-gray-400">
                  <th className="px-5 py-3">Candidate</th>
                  <th className="px-4 py-3">Department</th>
                  <th className="px-4 py-3">Current</th>
                  <th className="px-4 py-3">Available</th>
                  <th className="px-4 py-3">Next Available</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCandidates.map((candidate) => (
                  <tr key={candidate.id} className="border-t border-[var(--color-border)] text-sm">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <Avatar initials={initials(candidate.employee_name)} src={candidate.profile_image_url} variant="filled" />
                        <div>
                          <div className="font-bold text-[var(--color-brand-navy)]">{candidate.employee_name}</div>
                          <div className="text-xs text-gray-500">{candidate.designation || '-'}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-gray-600">{candidate.department || '-'}</td>
                    <td className="px-4 py-4 font-semibold">{candidate.current_allocation_percentage}%</td>
                    <td className="px-4 py-4 font-semibold text-olive">{candidate.available_capacity_percentage}%</td>
                    <td className="px-4 py-4 text-gray-600">{formatDate(candidate.next_available_date)}</td>
                    <td className="px-4 py-4"><Badge variant={statusVariant(candidate.match_status)}>{titleCase(candidate.match_status)}</Badge></td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="ghost" onClick={() => navigate(`/profile?employee_id=${candidate.employee_id}`)}>Profile</Button>
                        {candidate.match_status === 'allocated' && (
                          <Badge variant="success">Allocated</Badge>
                        )}
                        {candidate.match_status === 'allocated' && candidate.allocation_id && (
                          <Button size="sm" variant="ghost" onClick={() => setSearchParams({ tab: 'overview' })}>View Allocation</Button>
                        )}
                        {candidate.match_status === 'rejected' && <Badge variant="error">Rejected</Badge>}
                        {canCreateStaffingAllocation(user?.role) && candidate.match_status === 'selected' && (
                          <Button size="sm" icon={<CheckCircle2 size={14} />} onClick={() => setAllocationDrawerCandidate(candidate)}>Create Allocation</Button>
                        )}
                        {isHr(user?.role) && candidate.match_status === 'shortlisted' && (
                          <Button size="sm" variant="soft" icon={<CheckCircle2 size={14} />} onClick={() => action(`/staffing-requests/${request.id}/candidates/${candidate.employee_id}/select`)}>Select</Button>
                        )}
                        {isHr(user?.role) && candidate.match_status === 'suggested' && (
                          <Button size="sm" variant="ghost" onClick={() => action(`/staffing-requests/${request.id}/candidates/${candidate.employee_id}/shortlist`)}>Shortlist</Button>
                        )}
                        {isHr(user?.role) && ['suggested', 'shortlisted'].includes(candidate.match_status) && (
                          <Button size="sm" variant="ghost" icon={<UserRoundX size={14} />} onClick={() => action(`/staffing-requests/${request.id}/candidates/${candidate.employee_id}/reject`)}>Reject</Button>
                        )}
                        {isHr(user?.role) && candidate.match_status === 'selected' && (
                          <span title="Deselect first to reject" className="inline-flex items-center rounded-btn border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-gray-300">Reject</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredCandidates.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-6 py-14 text-center text-sm text-gray-500">No candidate matches in this status.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {activeTab === 'activity' && (
        <AuditTimeline entityType="staffing_request" entityId={request.id} maxItems={15} />
      )}

      <StaffingRequestDrawer
        open={drawerOpen}
        mode="edit"
        options={options}
        initial={request}
        currentUserId={user?.id}
        saving={saving}
        onClose={() => setDrawerOpen(false)}
        onSubmit={saveRequest}
      />
      <CreateAllocationDrawer
        open={Boolean(allocationDrawerCandidate)}
        request={request}
        candidate={allocationDrawerCandidate}
        options={options}
        headers={headers}
        saving={saving}
        onClose={() => setAllocationDrawerCandidate(null)}
        onCreated={(data) => {
          setRequest(data.staffing_request);
          setAllocationDrawerCandidate(null);
          load();
        }}
      />
    </div>
  );
}

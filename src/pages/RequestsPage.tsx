import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Banknote,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Copy,
  GitBranch,
  Eye,
  FileText,
  FileX,
  Home,
  Loader2,
  MessageSquare,
  RefreshCw,
  Send,
  Trash2,
  UserRound,
  X,
} from 'lucide-react';
import { Badge, Button, Card, CardHeader } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const MAX_RECEIPT_BYTES = 10 * 1024 * 1024;

type RequestType = 'wfh' | 'short_permission' | 'overtime' | 'expense';
type RequestStatus = 'draft' | 'pending' | 'approved' | 'rejected' | 'cancelled' | 'paid';

interface EmployeeRequest {
  id: string;
  employee_name: string;
  ticket_number?: string | null;
  request_type: RequestType;
  request_type_label: string;
  title: string;
  status: RequestStatus;
  start_date?: string | null;
  end_date?: string | null;
  request_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  duration_minutes?: number | null;
  hours?: number | null;
  amount?: number | null;
  currency?: string | null;
  category?: string | null;
  reason?: string | null;
  approver_name?: string | null;
  current_owner_id?: string | null;
  current_owner_name?: string | null;
  submitted_to_id?: string | null;
  submitted_to_name?: string | null;
  pending_since?: string | null;
  days_pending?: number | null;
  approved_by_name?: string | null;
  approved_at?: string | null;
  rejected_by_name?: string | null;
  rejected_at?: string | null;
  rejection_reason?: string | null;
  submitted_at?: string | null;
  created_at: string;
  updated_at: string;
  warning?: string | null;
  expense?: {
    date?: string | null;
    category?: string | null;
    amount?: number | null;
    currency?: string | null;
    description?: string | null;
    paid_at?: string | null;
    paid_by_id?: string | null;
  } | null;
  can_edit: boolean;
  can_submit: boolean;
  can_cancel: boolean;
  can_decide: boolean;
  can_reassign?: boolean;
  attachments?: Array<{
    id: string;
    request_id: string;
    original_file_name: string;
    file_extension?: string | null;
    mime_type?: string | null;
    file_size_bytes?: number | null;
    document_type: string;
    storage_provider: string;
    uploaded_by_name?: string | null;
    created_at: string;
  }>;
  comments?: Array<{ id: string; body?: string; comment?: string; is_internal: boolean; created_by_name: string; created_at: string }>;
  history?: Array<{ id: string; action: string; old_status?: string | null; new_status: string; reason?: string | null; performed_by_name: string; performed_at: string }>;
}

interface EmployeeOption {
  id: string;
  name: string;
  work_email?: string;
  role?: string;
}

interface ListResponse {
  items: EmployeeRequest[];
  total: number;
  page: number;
  per_page: number;
}

interface FormState {
  request_type: RequestType;
  start_date: string;
  end_date: string;
  request_date: string;
  start_time: string;
  end_time: string;
  duration_minutes: string;
  hours: string;
  amount: string;
  currency: string;
  category: string;
  reason: string;
  action: 'draft' | 'submit';
  attachment: File | null;
}

const requestTypes: Array<{ type: RequestType; label: string; description: string; icon: React.ReactNode }> = [
  { type: 'wfh', label: 'Work From Home', description: 'Remote work for one or more days.', icon: <Home size={18} /> },
  { type: 'short_permission', label: 'Short Permission', description: 'Short time away during the day.', icon: <Clock3 size={18} /> },
  { type: 'overtime', label: 'Overtime', description: 'Extra work hours that need approval.', icon: <BriefcaseBusiness size={18} /> },
  { type: 'expense', label: 'Expense Reimbursement', description: 'Submit receipts for business expenses.', icon: <Banknote size={18} /> },
];

function roleKey(role?: string) {
  return (role || '').toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_');
}

function statusVariant(status: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'olive' {
  if (status === 'approved' || status === 'paid') return 'success';
  if (status === 'pending') return 'warning';
  if (status === 'rejected') return 'error';
  if (status === 'draft') return 'neutral';
  return 'info';
}

function labelize(value?: string | null) {
  if (!value) return '-';
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function summarize(row: EmployeeRequest) {
  if (row.request_type === 'wfh') return `${formatDate(row.start_date)} - ${formatDate(row.end_date)}`;
  if (row.request_type === 'short_permission') return `${formatDate(row.request_date)} • ${row.duration_minutes || 0} min`;
  if (row.request_type === 'overtime') return `${formatDate(row.request_date)} • ${row.hours || 0}h`;
  return `${formatDate(row.request_date)} • ${row.currency || 'USD'} ${row.amount || 0}`;
}

function emptyForm(type: RequestType = 'wfh'): FormState {
  return {
    request_type: type,
    start_date: '',
    end_date: '',
    request_date: '',
    start_time: '',
    end_time: '',
    duration_minutes: '',
    hours: '',
    amount: '',
    currency: 'USD',
    category: '',
    reason: '',
    action: 'submit',
    attachment: null,
  };
}

function isPrivilegedPayer(role?: string) {
  return ['hr_admin', 'super_admin'].includes(roleKey(role));
}

function isPrivilegedAdmin(role?: string) {
  return ['hr_admin', 'super_admin', 'admin', 'global_access'].includes(roleKey(role));
}

function pendingTone(days?: number | null) {
  if (days == null) return 'text-gray-500';
  if (days >= 5) return 'text-status-error';
  if (days >= 2) return 'text-status-warning';
  return 'text-status-success';
}

async function copyText(value?: string | null) {
  if (!value) return;
  await navigator.clipboard?.writeText(value);
}

function formatFileSize(bytes?: number | null) {
  if (!bytes) return '-';
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function SkeletonRows() {
  return (
    <Card className="overflow-hidden">
      <div className="space-y-3 p-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="grid grid-cols-6 gap-4">
            {Array.from({ length: 6 }).map((__, cell) => (
              <div key={cell} className="h-9 animate-pulse rounded-lg bg-gray-100" />
            ))}
          </div>
        ))}
      </div>
    </Card>
  );
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="animate-fade-up">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[#2F3437]">Requests</h1>
          <p className="text-sm text-gray-500">Raise work-from-home, short permission, overtime, and reimbursement requests.</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function RequestTypeCards({ onCreate }: { onCreate: (type: RequestType) => void }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
      {requestTypes.map((item) => (
        <button key={item.type} onClick={() => onCreate(item.type)} className="text-left">
          <Card className="h-full p-5 transition-all hover:-translate-y-0.5 hover:shadow-card-md">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-olive/10 text-olive">{item.icon}</div>
            <div className="text-sm font-bold text-[#2F3437]">{item.label}</div>
            <div className="mt-1 text-xs leading-5 text-gray-500">{item.description}</div>
          </Card>
        </button>
      ))}
    </div>
  );
}

function RequestsTable({
  title,
  rows,
  empty,
  canCreate,
  canReassign,
  onCreate,
  onView,
  onAction,
  onReassign,
}: {
  title: string;
  rows: EmployeeRequest[];
  empty: string;
  canCreate?: boolean;
  canReassign?: boolean;
  onCreate?: () => void;
  onView: (row: EmployeeRequest) => void;
  onAction: (row: EmployeeRequest, action: 'submit' | 'cancel' | 'approve' | 'reject') => void;
  onReassign?: (row: EmployeeRequest) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader title={title} icon={<Send size={17} />} />
      {rows.length === 0 ? (
        <div className="px-5 py-16 text-center text-sm text-gray-500">
          {canCreate ? <FileX className="mx-auto mb-3 h-10 w-10 text-gray-300" /> : <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-gray-300" />}
          <p>{empty}</p>
          {canCreate && onCreate && <Button size="sm" className="mt-4" onClick={onCreate}>Create your first request</Button>}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1120px] text-sm">
            <thead className="bg-warm-bg text-[11px] uppercase tracking-wide text-gray-400">
              <tr>
                <th className="px-5 py-3 text-left">Ticket</th>
                <th className="px-5 py-3 text-left">Request</th>
                <th className="px-5 py-3 text-left">Employee</th>
                <th className="px-5 py-3 text-left">Details</th>
                <th className="px-5 py-3 text-left">Current Owner</th>
                <th className="px-5 py-3 text-left">Pending</th>
                <th className="px-5 py-3 text-left">Status</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="px-5 py-4">
                    <button
                      type="button"
                      title="Copy ticket number"
                      onClick={() => copyText(row.ticket_number)}
                      className="inline-flex items-center gap-1 rounded-md bg-gray-50 px-2 py-1 font-mono text-xs font-bold text-olive hover:bg-hover-bg"
                    >
                      {row.ticket_number || 'Pending ID'}
                      <Copy size={12} />
                    </button>
                  </td>
                  <td className="px-5 py-4">
                    <div className="font-bold text-[#2F3437]">{row.request_type_label}</div>
                    <div className="text-xs text-gray-500">{row.title}</div>
                  </td>
                  <td className="px-5 py-4 font-semibold">{row.employee_name}</td>
                  <td className="px-5 py-4 text-gray-600">{summarize(row)}</td>
                  <td className="px-5 py-4 text-gray-600">{row.current_owner_name || (row.status === 'pending' ? row.approver_name : '-')}</td>
                  <td className={`px-5 py-4 font-semibold ${pendingTone(row.days_pending)}`}>
                    {row.status === 'pending' ? `${row.days_pending ?? 0} day${(row.days_pending ?? 0) === 1 ? '' : 's'}` : '-'}
                  </td>
                  <td className="px-5 py-4"><Badge variant={statusVariant(row.status)}>{labelize(row.status)}</Badge></td>
                  <td className="px-5 py-4">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" icon={<Eye size={13} />} onClick={() => onView(row)}>View</Button>
                      {row.can_submit && <Button size="sm" variant="soft" icon={<Send size={13} />} onClick={() => onAction(row, 'submit')}>Submit</Button>}
                      {row.can_cancel && <Button size="sm" variant="ghost" icon={<Trash2 size={13} />} onClick={() => onAction(row, 'cancel')}>Cancel</Button>}
                      {row.can_decide && <Button size="sm" variant="soft" icon={<CheckCircle2 size={13} />} onClick={() => onAction(row, 'approve')}>Approve</Button>}
                      {row.can_decide && <Button size="sm" variant="ghost" icon={<X size={13} />} onClick={() => onAction(row, 'reject')}>Reject</Button>}
                      {canReassign && row.can_reassign && onReassign && <Button size="sm" variant="ghost" icon={<GitBranch size={13} />} onClick={() => onReassign(row)}>Reassign</Button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function RequestModal({ initialType, lockedType = true, onClose, onSave }: { initialType: RequestType; lockedType?: boolean; onClose: () => void; onSave: (form: FormState) => Promise<void> }) {
  const [form, setForm] = useState<FormState>(() => emptyForm(initialType));
  const [saving, setSaving] = useState(false);
  const [fileError, setFileError] = useState('');

  const setField = (field: keyof FormState, value: string | File | null) => setForm((prev) => ({ ...prev, [field]: value }));
  const previewUrl = useMemo(() => form.attachment && form.attachment.type.startsWith('image/') ? URL.createObjectURL(form.attachment) : '', [form.attachment]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const submit = async (action: 'draft' | 'submit') => {
    setSaving(true);
    try {
      await onSave({ ...form, action });
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/35 p-6 backdrop-blur-sm">
      <Card className="max-h-[90vh] w-full max-w-2xl overflow-hidden shadow-[0_24px_80px_rgba(31,41,55,0.24)]">
        <div className="flex items-start justify-between border-b border-[#E5E7EB] px-6 py-5">
          <div>
            <h2 className="text-lg font-bold text-[#2F3437]">New {requestTypes.find((item) => item.type === form.request_type)?.label || 'Request'} Request</h2>
            <p className="mt-1 text-sm text-gray-500">Complete the required fields and submit for approval.</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg"><X size={18} /></button>
        </div>
        <div className="max-h-[calc(90vh-150px)] overflow-y-auto p-6">
          <div className="grid gap-4 md:grid-cols-2">
            {!lockedType && (
              <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">
                Request Type
                <select value={form.request_type} onChange={(event) => setForm(emptyForm(event.target.value as RequestType))} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive">
                  {requestTypes.map((item) => <option key={item.type} value={item.type}>{item.label}</option>)}
                </select>
              </label>
            )}
            {form.request_type === 'expense' && (
              <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">
                Category
                <input value={form.category} onChange={(event) => setField('category', event.target.value)} placeholder="Travel, meal, software..." className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" />
              </label>
            )}
            {form.request_type === 'wfh' ? (
              <>
                <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">From Date<input type="date" value={form.start_date} onChange={(event) => setField('start_date', event.target.value)} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">To Date<input type="date" value={form.end_date} onChange={(event) => setField('end_date', event.target.value)} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
              </>
            ) : (
              <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">
                Date
                <input type="date" value={form.request_date} onChange={(event) => setField('request_date', event.target.value)} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" />
              </label>
            )}
            {form.request_type === 'short_permission' && (
              <>
                <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">Start Time<input type="time" value={form.start_time} onChange={(event) => setField('start_time', event.target.value)} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">End Time<input type="time" value={form.end_time} onChange={(event) => setField('end_time', event.target.value)} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
              </>
            )}
            {form.request_type === 'overtime' && (
              <>
                <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">Start Time<input type="time" value={form.start_time} onChange={(event) => setField('start_time', event.target.value)} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">End Time<input type="time" value={form.end_time} onChange={(event) => setField('end_time', event.target.value)} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
              </>
            )}
            {form.request_type === 'expense' && (
              <>
                <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">Amount<input type="number" min="0.01" step="0.01" value={form.amount} onChange={(event) => setField('amount', event.target.value)} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[#2F3437]">Currency<input value={form.currency} onChange={(event) => setField('currency', event.target.value.toUpperCase())} className="h-11 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[#2F3437] md:col-span-2">
                  Receipt
                  <div className="rounded-lg border border-dashed border-[#D9DED3] bg-warm-bg p-3 text-sm text-gray-500">
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx"
                      onChange={(event) => {
                        const file = event.target.files?.[0] || null;
                        setFileError('');
                        if (file && file.size > MAX_RECEIPT_BYTES) {
                          setField('attachment', null);
                          setFileError('File size exceeds 10MB.');
                          event.target.value = '';
                          return;
                        }
                        setField('attachment', file);
                      }}
                    />
                    {fileError && <div className="mt-2 rounded-lg bg-status-error/10 px-3 py-2 text-xs text-status-error">{fileError}</div>}
                    {form.attachment && (
                      <div className="mt-3 flex items-center justify-between gap-3 rounded-lg bg-white p-3">
                        <div className="flex items-center gap-3">
                          {previewUrl ? <img src={previewUrl} className="h-12 w-12 rounded-lg object-cover" /> : <FileText size={24} className="text-olive" />}
                          <div>
                            <div className="font-semibold text-[#2F3437]">{form.attachment.name}</div>
                            <div className="text-xs text-gray-400">{formatFileSize(form.attachment.size)}</div>
                          </div>
                        </div>
                        <button type="button" onClick={() => setField('attachment', null)} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg"><X size={16} /></button>
                      </div>
                    )}
                  </div>
                </label>
              </>
            )}
            <label className="grid gap-1 text-sm font-semibold text-[#2F3437] md:col-span-2">
              Reason
              <textarea value={form.reason} maxLength={500} onChange={(event) => setField('reason', event.target.value)} placeholder="Add enough context for your manager..." className="min-h-[96px] rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-3 outline-none focus:border-olive" />
              <span className="text-right text-xs text-gray-400">{form.reason.length}/500</span>
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-3 border-t border-[#E5E7EB] px-6 py-4">
          <Button variant="ghost" disabled={saving} onClick={() => submit('draft')}>{saving ? 'Saving...' : 'Save Draft'}</Button>
          <Button disabled={saving} icon={saving ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} onClick={() => submit('submit')}>Submit Request</Button>
        </div>
      </Card>
    </div>,
    document.body
  );
}

function WorkflowProgressTracker({ request }: { request: EmployeeRequest }) {
  const steps = [
    { key: 'created', label: 'Created', complete: true },
    { key: 'submitted', label: 'Submitted', complete: Boolean(request.submitted_at) || request.status !== 'draft' },
    { key: 'manager', label: request.submitted_to_name ? `Manager: ${request.submitted_to_name}` : 'Manager Review', complete: ['approved', 'paid'].includes(request.status) },
    { key: 'final', label: request.status === 'paid' ? 'Paid' : request.status === 'rejected' ? 'Rejected' : request.status === 'cancelled' ? 'Cancelled' : 'Finalized', complete: ['paid', 'rejected', 'cancelled'].includes(request.status) },
  ];
  return (
    <Card className="mt-4 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-bold text-[#2F3437]"><GitBranch size={15} className="text-olive" /> Workflow</div>
      <div className="grid gap-3">
        {steps.map((step, index) => (
          <div key={step.key} className="flex items-center gap-3">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${step.complete ? 'bg-olive text-white' : 'bg-gray-100 text-gray-400'}`}>{index + 1}</span>
            <span className={`text-sm ${step.complete ? 'font-semibold text-[#2F3437]' : 'text-gray-500'}`}>{step.label}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function DetailDrawer({ request, userRole, employees, onClose, onRefresh, onAction, onMarkPaid, onReassign, headers }: { request: EmployeeRequest; userRole?: string; employees: EmployeeOption[]; onClose: () => void; onRefresh: (id: string) => Promise<void>; onAction: (row: EmployeeRequest, action: 'submit' | 'cancel' | 'approve' | 'reject') => void; onMarkPaid: (row: EmployeeRequest) => Promise<void>; onReassign: (row: EmployeeRequest, ownerId: string, reason: string) => Promise<void>; headers: Record<string, string> }) {
  const { showToast } = useToast();
  const [comment, setComment] = useState('');
  const [internal, setInternal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [newOwnerId, setNewOwnerId] = useState('');
  const [reassignReason, setReassignReason] = useState('');
  const [reassigning, setReassigning] = useState(false);

  const postComment = async () => {
    if (!comment.trim()) return;
    const res = await fetch(`${API_BASE}/requests/${request.id}/comments`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ body: comment.trim(), is_internal: internal }),
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      showToast({ message: body?.detail || 'Could not add comment.' });
      return;
    }
    setComment('');
    await onRefresh(request.id);
  };

  const uploadReceipt = async (file: File | null) => {
    if (!file) return;
    if (file.size > MAX_RECEIPT_BYTES) {
      showToast({ message: 'File size exceeds 10MB.' });
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('document_type', 'EXPENSE_RECEIPT');
      const uploadHeaders = { 'x-user-id': headers['x-user-id'], 'x-user-email': headers['x-user-email'] };
      const res = await fetch(`${API_BASE}/requests/${request.id}/attachments`, { method: 'POST', headers: uploadHeaders, body: formData });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        showToast({ message: body?.detail || 'Could not upload receipt.' });
        return;
      }
      showToast({ message: 'Receipt uploaded.' });
      await onRefresh(request.id);
    } finally {
      setUploading(false);
    }
  };

  const downloadAttachment = async (attachmentId: string, fileName: string) => {
    const res = await fetch(`${API_BASE}/requests/${request.id}/attachments/${attachmentId}/download`, { headers });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      showToast({ message: body?.detail || 'Download failed.' });
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const deleteAttachment = async (attachmentId: string) => {
    const res = await fetch(`${API_BASE}/requests/${request.id}/attachments/${attachmentId}`, { method: 'DELETE', headers });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      showToast({ message: body?.detail || 'Could not delete attachment.' });
      return;
    }
    showToast({ message: 'Attachment deleted.' });
    await onRefresh(request.id);
  };

  const timeline = useMemo(() => {
    const events = [
      ...(request.history || []).map((item) => ({
        id: `history-${item.id}`,
        at: item.performed_at,
        title: `${labelize(item.action)} to ${labelize(item.new_status)}`,
        detail: `${item.performed_by_name}${item.reason ? ` - ${item.reason}` : ''}`,
      })),
      ...(request.comments || []).map((item) => ({
        id: `comment-${item.id}`,
        at: item.created_at,
        title: item.is_internal ? 'Internal comment added' : 'Comment added',
        detail: `${item.created_by_name}: ${item.body || item.comment || ''}`,
      })),
      ...(request.attachments || []).map((item) => ({
        id: `attachment-${item.id}`,
        at: item.created_at,
        title: 'Attachment uploaded',
        detail: `${item.original_file_name} by ${item.uploaded_by_name || 'Unknown'}`,
      })),
    ];
    return events.sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  }, [request.attachments, request.comments, request.history]);

  const submitReassign = async () => {
    if (!newOwnerId || !reassignReason.trim()) {
      showToast({ message: 'Select a new owner and add a reassignment reason.' });
      return;
    }
    setReassigning(true);
    try {
      await onReassign(request, newOwnerId, reassignReason.trim());
      setReassignOpen(false);
      setReassignReason('');
      setNewOwnerId('');
    } finally {
      setReassigning(false);
    }
  };

  return createPortal(
    <>
      <div className="fixed inset-0 z-[1000] flex justify-end bg-black/25 backdrop-blur-sm">
      <Card className="h-full w-full max-w-xl overflow-hidden rounded-none border-y-0 border-r-0 shadow-[0_24px_80px_rgba(31,41,55,0.28)]">
        <div className="flex items-start justify-between border-b border-[#E5E7EB] px-6 py-5">
          <div>
            <div className="mb-2"><Badge variant={statusVariant(request.status)}>{labelize(request.status)}</Badge></div>
            <h2 className="text-lg font-bold text-[#2F3437]">{request.request_type_label}</h2>
            <p className="text-sm text-gray-500">{summarize(request)}</p>
            <button
              type="button"
              onClick={() => copyText(request.ticket_number)}
              className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-1.5 font-mono text-xs font-bold text-olive hover:bg-hover-bg"
            >
              {request.ticket_number || 'Pending ID'} <Copy size={12} />
            </button>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg"><X size={18} /></button>
        </div>
        <div className="h-[calc(100%-88px)] overflow-y-auto p-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <Info label="Employee" value={request.employee_name} />
            <Info label="Current Owner" value={request.current_owner_name || (request.status === 'pending' ? request.approver_name || '-' : '-')} />
            <Info label="Submitted To" value={request.submitted_to_name || '-'} />
            <Info label="Pending Since" value={request.pending_since ? `${formatDateTime(request.pending_since)} (${request.days_pending ?? 0} days)` : '-'} />
            <Info label="Submitted" value={formatDateTime(request.submitted_at)} />
            <Info label="Updated" value={formatDateTime(request.updated_at)} />
            {request.status === 'paid' && <Info label="Paid On" value={formatDateTime(request.expense?.paid_at)} />}
          </div>
          <WorkflowProgressTracker request={request} />
          {request.can_reassign && isPrivilegedAdmin(userRole) && request.status === 'pending' && (
            <Card className="mt-4 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-bold text-[#2F3437]"><UserRound size={15} className="text-olive" /> Ownership</div>
                <Button size="sm" variant="ghost" icon={<GitBranch size={13} />} onClick={() => setReassignOpen((value) => !value)}>{reassignOpen ? 'Close' : 'Reassign'}</Button>
              </div>
              <div className="text-sm text-gray-600">Current owner: <span className="font-semibold text-[#2F3437]">{request.current_owner_name || '-'}</span></div>
              {reassignOpen && (
                <div className="mt-4 grid gap-3">
                  <select value={newOwnerId} onChange={(event) => setNewOwnerId(event.target.value)} className="h-10 rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 text-sm outline-none focus:border-olive">
                    <option value="">Select new owner</option>
                    {employees.map((employee) => (
                      <option key={employee.id} value={employee.id}>{employee.name} {employee.role ? `(${labelize(employee.role)})` : ''}</option>
                    ))}
                  </select>
                  <textarea value={reassignReason} onChange={(event) => setReassignReason(event.target.value)} placeholder="Reason for reassignment..." className="min-h-[72px] rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2 text-sm outline-none focus:border-olive" />
                  <Button size="sm" disabled={reassigning} icon={reassigning ? <Loader2 size={13} className="animate-spin" /> : <GitBranch size={13} />} onClick={submitReassign}>Reassign Request</Button>
                </div>
              )}
            </Card>
          )}
          <Card className="mt-4 p-4">
            <div className="mb-1 text-xs font-bold uppercase tracking-wide text-gray-400">Reason</div>
            <p className="text-sm leading-6 text-[#2F3437]">{request.reason || '-'}</p>
            {request.rejection_reason && <p className="mt-3 rounded-lg bg-status-error/10 px-3 py-2 text-sm text-status-error">{request.rejection_reason}</p>}
          </Card>
          <Card className="mt-4 overflow-hidden">
            <CardHeader title="Attachments" icon={<FileText size={15} />} />
            {(request.attachments || []).length === 0 ? (
              <div className="px-5 py-5 text-sm text-gray-500">No attachments.</div>
            ) : (
              (request.attachments || []).map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-3 border-b border-[#E5E7EB] px-5 py-3 last:border-b-0">
                  <div>
                    <div className="text-sm font-bold text-[#2F3437]">{item.original_file_name}</div>
                    <div className="text-xs text-gray-500">{formatFileSize(item.file_size_bytes)} • {formatDateTime(item.created_at)}</div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" onClick={() => downloadAttachment(item.id, item.original_file_name)}>Download</Button>
                    {request.status !== 'approved' && request.status !== 'paid' && <Button size="sm" variant="ghost" icon={<Trash2 size={13} />} onClick={() => deleteAttachment(item.id)}>Delete</Button>}
                  </div>
                </div>
              ))
            )}
            {request.request_type === 'expense' && ['draft', 'pending'].includes(request.status) && (
              <div className="border-t border-[#E5E7EB] p-4">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[#E5E7EB] px-3 py-2 text-sm font-semibold text-olive hover:bg-hover-bg">
                  {uploading ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
                  Upload Receipt
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx" className="hidden" disabled={uploading} onChange={(event) => uploadReceipt(event.target.files?.[0] || null)} />
                </label>
              </div>
            )}
          </Card>
          <Card className="mt-4 overflow-hidden">
            <CardHeader title="Comments" icon={<MessageSquare size={15} />} />
            {(request.comments || []).map((item) => (
              <div key={item.id} className="border-b border-[#E5E7EB] px-5 py-3 last:border-b-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold">{item.created_by_name}</span>
                  <span className="text-xs text-gray-400">{formatDateTime(item.created_at)}</span>
                </div>
                <p className="mt-1 text-sm text-gray-600">{item.body || item.comment}</p>
                {item.is_internal && <Badge variant="neutral">Internal</Badge>}
              </div>
            ))}
            <div className="grid gap-2 border-t border-[#E5E7EB] p-4">
              <textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add a comment..." className="min-h-[78px] rounded-lg border border-[#E5E7EB] bg-warm-bg px-3 py-2 text-sm outline-none focus:border-olive" />
              <label className="flex items-center gap-2 text-xs font-semibold text-gray-500"><input type="checkbox" checked={internal} onChange={(event) => setInternal(event.target.checked)} className="accent-olive" /> Internal note</label>
              <Button size="sm" variant="soft" onClick={postComment}>Add Comment</Button>
            </div>
          </Card>
          <Card className="mt-4 overflow-hidden">
            <CardHeader title="Timeline" icon={<CalendarDays size={15} />} />
            {timeline.length === 0 ? (
              <div className="px-5 py-5 text-sm text-gray-500">No timeline events yet.</div>
            ) : (
              timeline.map((item) => (
                <div key={item.id} className="border-b border-[#E5E7EB] px-5 py-3 text-sm last:border-b-0">
                  <div className="font-semibold text-[#2F3437]">{item.title}</div>
                  <div className="mt-1 text-xs leading-5 text-gray-500">{item.detail}</div>
                  <div className="mt-1 text-[11px] text-gray-400">{formatDateTime(item.at)}</div>
                </div>
              ))
            )}
          </Card>
          <Card className="mt-4 overflow-hidden">
            <CardHeader title="History" icon={<CalendarDays size={15} />} />
            {(request.history || []).map((item) => (
              <div key={item.id} className="border-b border-[#E5E7EB] px-5 py-3 text-sm last:border-b-0">
                <div className="font-semibold text-[#2F3437]">{labelize(item.action)} to {labelize(item.new_status)}</div>
                <div className="text-xs text-gray-500">{item.performed_by_name} • {formatDateTime(item.performed_at)}</div>
              </div>
            ))}
          </Card>
          <div className="sticky bottom-0 mt-4 flex flex-wrap justify-end gap-2 bg-warm-bg/95 py-3">
            {request.can_submit && <Button size="sm" icon={<Send size={13} />} onClick={() => onAction(request, 'submit')}>Submit</Button>}
            {request.can_cancel && <Button size="sm" variant="ghost" icon={<Trash2 size={13} />} onClick={() => onAction(request, 'cancel')}>Cancel</Button>}
            {request.can_decide && <Button size="sm" icon={<CheckCircle2 size={13} />} onClick={() => onAction(request, 'approve')}>Approve</Button>}
            {request.can_decide && <Button size="sm" variant="ghost" icon={<X size={13} />} onClick={() => onAction(request, 'reject')}>Reject</Button>}
            {request.request_type === 'expense' && request.status === 'approved' && isPrivilegedPayer(userRole) && <Button size="sm" icon={<Banknote size={13} />} onClick={() => onMarkPaid(request)}>Mark as Paid</Button>}
          </div>
        </div>
      </Card>
      </div>
    </>,
    document.body
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-xl border border-[#E5E7EB] bg-warm-bg p-3">
      <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{label}</div>
      <div className="mt-1 text-sm font-bold text-[#2F3437]">{value || '-'}</div>
    </div>
  );
}

export function RequestsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [myRequests, setMyRequests] = useState<EmployeeRequest[]>([]);
  const [queue, setQueue] = useState<EmployeeRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modalType, setModalType] = useState<RequestType | null>(null);
  const [detail, setDetail] = useState<EmployeeRequest | null>(null);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const role = roleKey(user?.role);
  const canReview = ['manager', 'super_admin', 'admin', 'hr_admin', 'global_access'].includes(role);
  const canReassign = isPrivilegedAdmin(user?.role);
  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (typeFilter !== 'all') params.set('request_type', typeFilter);
      if (search.trim()) params.set('search', search.trim());
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      const [myRes, queueRes] = await Promise.all([
        fetch(`${API_BASE}/requests/my?${params.toString()}`, { headers }),
        canReview ? fetch(`${API_BASE}/requests/queue?${params.toString()}`, { headers }) : Promise.resolve(null),
      ]);
      const myBody = await myRes.json().catch(() => null);
      if (!myRes.ok) throw new Error(myBody?.detail || 'Could not load requests.');
      setMyRequests((myBody as ListResponse).items || []);
      if (queueRes) {
        const queueBody = await queueRes.json().catch(() => null);
        if (queueRes.ok) setQueue((queueBody as ListResponse).items || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load requests.');
    } finally {
      setLoading(false);
    }
  }, [canReview, dateFrom, dateTo, headers, search, statusFilter, typeFilter, user]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!user || !canReassign) return;
    const controller = new AbortController();
    const loadEmployees = async () => {
      const res = await fetch(`${API_BASE}/employees/?per_page=100`, { headers, signal: controller.signal });
      const body = await res.json().catch(() => null);
      if (!res.ok) return;
      const rows = Array.isArray(body) ? body : body?.employees || body?.items || [];
      setEmployees(rows.map((item: any) => ({
        id: item.id,
        name: `${item.first_name || ''} ${item.last_name || ''}`.trim() || item.work_email || item.id,
        work_email: item.work_email,
        role: item.role,
      })));
    };
    loadEmployees().catch(() => undefined);
    return () => controller.abort();
  }, [canReassign, headers, user]);

  const refreshDetail = async (id: string) => {
    const res = await fetch(`${API_BASE}/requests/${id}`, { headers });
    const body = await res.json().catch(() => null);
    if (res.ok) setDetail(body);
  };

  const createFromForm = async (form: FormState) => {
    const shouldSubmit = form.action === 'submit';
    const payload: Record<string, unknown> = {
      request_type: form.request_type,
      submit_immediately: shouldSubmit && !form.attachment,
    };
    if (form.request_type === 'wfh') {
      payload.wfh = {
        from_date: form.start_date,
        to_date: form.end_date,
        reason: form.reason,
      };
    }
    if (form.request_type === 'short_permission') {
      payload.short_permission = {
        date: form.request_date,
        start_time: form.start_time,
        end_time: form.end_time,
        reason: form.reason,
      };
    }
    if (form.request_type === 'overtime') {
      payload.overtime = {
        date: form.request_date,
        start_time: form.start_time,
        end_time: form.end_time,
        reason: form.reason,
      };
    }
    if (form.request_type === 'expense') {
      payload.expense = {
        date: form.request_date,
        category: form.category,
        amount: form.amount ? Number(form.amount) : undefined,
        currency: form.currency || 'USD',
        description: form.reason,
      };
    }
    const res = await fetch(`${API_BASE}/requests`, { method: 'POST', headers, body: JSON.stringify(payload) });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      showToast({ message: body?.detail || 'Could not save request.' });
      return;
    }
    let finalBody = body as EmployeeRequest;
    if (form.attachment) {
      const uploadData = new FormData();
      uploadData.append('file', form.attachment);
      uploadData.append('document_type', 'EXPENSE_RECEIPT');
      const uploadHeaders = { 'x-user-id': headers['x-user-id'], 'x-user-email': headers['x-user-email'] };
      const uploadRes = await fetch(`${API_BASE}/requests/${body.id}/attachments`, {
        method: 'POST',
        headers: uploadHeaders,
        body: uploadData,
      });
      const uploadBody = await uploadRes.json().catch(() => null);
      if (!uploadRes.ok) {
        showToast({ message: uploadBody?.detail || 'Request saved, but receipt upload failed.' });
        await load();
        return;
      }
      if (shouldSubmit) {
        const submitRes = await fetch(`${API_BASE}/requests/${body.id}/submit`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ reason: null }),
        });
        const submitBody = await submitRes.json().catch(() => null);
        if (!submitRes.ok) {
          showToast({ message: submitBody?.detail || 'Receipt uploaded, but request could not be submitted.' });
          await load();
          return;
        }
        finalBody = submitBody;
      }
    }
    setModalType(null);
    showToast({ message: form.action === 'submit' ? 'Request submitted.' : 'Request saved as draft.' });
    if (finalBody.warning) showToast({ message: finalBody.warning });
    await load();
  };

  const openDetail = async (row: EmployeeRequest) => {
    setDetail(row);
    await refreshDetail(row.id);
  };

  const runAction = async (row: EmployeeRequest, action: 'submit' | 'cancel' | 'approve' | 'reject') => {
    const reason = action === 'reject' || action === 'cancel' ? window.prompt(`${labelize(action)} reason:`) : null;
    if ((action === 'reject' || action === 'cancel') && !reason?.trim()) return;
    const payload = action === 'approve'
      ? { notes: null }
      : action === 'reject'
        ? { reason: reason?.trim() }
        : { reason: reason?.trim() || null };
    const res = await fetch(`${API_BASE}/requests/${row.id}/${action}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      showToast({ message: body?.detail || 'Action failed.' });
      return;
    }
    showToast({ message: `Request ${action}d.` });
    setDetail(body);
    await load();
  };

  const markPaid = async (row: EmployeeRequest) => {
    const confirmed = window.confirm('Mark this approved expense as paid?');
    if (!confirmed) return;
    const res = await fetch(`${API_BASE}/requests/${row.id}/mark-paid`, {
      method: 'POST',
      headers,
      body: JSON.stringify({}),
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      showToast({ message: body?.detail || 'Could not mark expense as paid.' });
      return;
    }
    showToast({ message: 'Expense marked as paid.' });
    setDetail(body);
    await load();
  };

  const reassign = async (row: EmployeeRequest, ownerId: string, reason: string) => {
    const res = await fetch(`${API_BASE}/requests/${row.id}/reassign`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ new_owner_id: ownerId, reason }),
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      showToast({ message: body?.detail || 'Could not reassign request.' });
      return;
    }
    showToast({ message: 'Request reassigned.' });
    setDetail(body);
    await load();
  };

  return (
    <PageShell>
      {error && <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}
      <RequestTypeCards onCreate={setModalType} />
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search requests..."
            className="h-10 min-w-[220px] rounded-lg border border-[#E5E7EB] bg-white px-3 text-sm outline-none focus:border-olive"
          />
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="h-10 rounded-lg border border-[#E5E7EB] bg-white px-3 text-sm outline-none focus:border-olive">
            {['all', 'draft', 'pending', 'approved', 'rejected', 'cancelled', 'paid'].map((item) => <option key={item} value={item}>Status: {labelize(item)}</option>)}
          </select>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="h-10 rounded-lg border border-[#E5E7EB] bg-white px-3 text-sm outline-none focus:border-olive">
            <option value="all">Type: All</option>
            {requestTypes.map((item) => <option key={item.type} value={item.type}>{item.label}</option>)}
          </select>
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="h-10 rounded-lg border border-[#E5E7EB] bg-white px-3 text-sm outline-none focus:border-olive" />
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="h-10 rounded-lg border border-[#E5E7EB] bg-white px-3 text-sm outline-none focus:border-olive" />
        </div>
        <Button variant="ghost" icon={<RefreshCw size={14} />} disabled={loading} onClick={load}>Refresh</Button>
      </div>
      <div className="mt-5 grid gap-5">
        {loading ? (
          <SkeletonRows />
        ) : (
          <>
            <RequestsTable title="My Requests" rows={myRequests} empty="You have not created any requests yet." canCreate onCreate={() => setModalType('wfh')} onView={openDetail} onAction={runAction} />
            {canReview && <RequestsTable title="Approval Queue" rows={queue} empty="No requests are waiting for your approval." canReassign={canReassign} onReassign={openDetail} onView={openDetail} onAction={runAction} />}
          </>
        )}
      </div>
      {modalType && <RequestModal initialType={modalType} onClose={() => setModalType(null)} onSave={createFromForm} />}
      {detail && <DetailDrawer request={detail} userRole={user?.role} employees={employees} onClose={() => setDetail(null)} onRefresh={refreshDetail} onAction={runAction} onMarkPaid={markPaid} onReassign={reassign} headers={headers} />}
    </PageShell>
  );
}

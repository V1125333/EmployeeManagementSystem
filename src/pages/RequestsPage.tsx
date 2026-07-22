import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  ArrowRight,
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
  Search,
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

type RequestType = 'wfh' | 'short_permission' | 'overtime' | 'expense' | 'application_issue';
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
  application_issue?: {
    category?: string | null;
    description?: string | null;
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

interface RequestPolicy {
  request_type: RequestType;
  label: string;
  allow_past_dates: boolean;
  allow_future_dates: boolean;
  allow_today: boolean;
  maximum_past_days?: number | null;
  maximum_future_days?: number | null;
  allow_dates_before_joining: boolean;
  maximum_pre_joining_days?: number | null;
  requires_manager_approval: boolean;
  requires_hr_approval: boolean;
  requires_finance_approval: boolean;
  requires_attachment: boolean;
  requires_comments: boolean;
  maximum_attachment_size: number;
  accepted_file_types: string[];
  min_date?: string | null;
  max_date?: string | null;
  invalid_past_message: string;
  invalid_future_message: string;
  past_window_message: string;
  future_window_message: string;
  pre_joining_message: string;
}

type RequestPolicyMap = Partial<Record<RequestType, RequestPolicy>>;

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

interface RequestActionIntent {
  row: EmployeeRequest;
  action: 'cancel' | 'reject';
}

const requestTypes: Array<{ type: RequestType; label: string; description: string; icon: React.ReactNode }> = [
  { type: 'wfh', label: 'Work From Home', description: 'Remote work for one or more days.', icon: <Home size={18} /> },
  { type: 'short_permission', label: 'Short Permission', description: 'Short time away during the day.', icon: <Clock3 size={18} /> },
  { type: 'overtime', label: 'Overtime', description: 'Extra work hours that need approval.', icon: <BriefcaseBusiness size={18} /> },
  { type: 'expense', label: 'Expense Reimbursement', description: 'Submit receipts for business expenses.', icon: <Banknote size={18} /> },
  { type: 'application_issue', label: 'Application Issue', description: 'Report UI, document, upload, or timesheet issues.', icon: <AlertCircle size={18} /> },
];

const applicationIssueCategories = [
  { value: 'font_issue', label: 'Font issue' },
  { value: 'improper_format', label: 'Improper format' },
  { value: 'document_upload_download', label: 'Unable to upload/download documents' },
  { value: 'timesheet_issue', label: 'Timesheet issue' },
  { value: 'application_navigation', label: 'Application navigation issue' },
  { value: 'other', label: 'Other' },
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
  if (row.request_type === 'short_permission') return `${formatDate(row.request_date)} - ${row.duration_minutes || 0} min`;
  if (row.request_type === 'overtime') return `${formatDate(row.request_date)} - ${row.hours || 0}h`;
  if (row.request_type === 'application_issue') return labelize(row.category || row.application_issue?.category);
  return `${formatDate(row.request_date)} - ${row.currency || 'USD'} ${row.amount || 0}`;
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
    <div className="-mx-[var(--layout-main-padding-x)] -my-[var(--layout-main-padding-y)] min-h-[calc(100vh-3.5rem)] animate-fade-up bg-[#f7f3ec] px-[var(--layout-main-padding-x)] py-[var(--layout-main-padding-y)]">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mb-1 text-[28px] font-bold tracking-tight text-[#1f2430]">Requests</h1>
          <p className="text-sm text-[#8a8371]">Raise work-from-home, short permission, overtime, reimbursement, and application issue requests.</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function RequestTypeCards({ onCreate }: { onCreate: (type: RequestType) => void }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
      {requestTypes.map((item) => (
        <button key={item.type} type="button" onClick={() => onCreate(item.type)} className="group text-left">
          <Card className="h-full min-h-[188px] border-[#ece5d8] p-5 transition-all group-hover:-translate-y-0.5 group-hover:border-[#d97a34]/40 group-hover:shadow-card-md">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#fbeee1] text-[#d97a34]">{item.icon}</div>
            <div className="text-base font-bold text-[#1f2430]">{item.label}</div>
            <div className="mt-1 min-h-10 text-sm leading-5 text-[#8a8371]">{item.description}</div>
            <div className="mt-4 inline-flex items-center gap-1 text-sm font-bold text-[#d06a21]">
              New request <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
            </div>
          </Card>
        </button>
      ))}
    </div>
  );
}

function RequestIcon({ type }: { type: RequestType }) {
  const item = requestTypes.find((requestType) => requestType.type === type);
  return <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#fbeee1] text-[#d97a34]">{item?.icon}</div>;
}

function RequestStatusBadge({ status }: { status: RequestStatus }) {
  return (
    <Badge variant={statusVariant(status)}>
      <span className="mr-1">●</span>{labelize(status)}
    </Badge>
  );
}

function MyRequestsCard({ rows, onCreate, onView }: {
  rows: EmployeeRequest[];
  onCreate: () => void;
  onView: (row: EmployeeRequest) => void;
}) {
  return (
    <Card className="overflow-hidden border-[#ece5d8]">
      <div className="flex items-center justify-between border-b border-[#ece5d8] px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#fbeee1] text-[#d97a34]"><Send size={18} /></div>
          <h2 className="text-lg font-bold text-[#1f2430]">My Requests</h2>
          <span className="rounded-full bg-[#f2ece0] px-2.5 py-1 text-xs font-bold text-[#8a8371]">{rows.length}</span>
        </div>
        {rows.length > 0 && <button type="button" onClick={() => rows[0] && onView(rows[0])} className="text-sm font-bold text-[#d06a21]">View latest <ArrowRight className="inline" size={14} /></button>}
      </div>
      {rows.length === 0 ? (
        <div className="m-6 rounded-2xl border border-dashed border-[#dfd2bc] px-5 py-14 text-center text-sm text-[#8a8371]">
          <FileX className="mx-auto mb-3 h-10 w-10 text-[#cbbfae]" />
          <p>You have not created any requests yet.</p>
          <Button size="sm" className="mt-4" onClick={onCreate}>Create your first request</Button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-sm">
            <thead className="text-[11px] uppercase tracking-wide text-[#a99e8a]">
              <tr>
                <th className="px-6 py-3 text-left">Request</th>
                <th className="px-5 py-3 text-left">Type</th>
                <th className="px-5 py-3 text-left">Dates / details</th>
                <th className="px-5 py-3 text-left">Status</th>
                <th className="px-6 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ece5d8]">
              {rows.map((row) => (
                <tr key={row.id} className="transition-colors hover:bg-[#fffaf3]">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <RequestIcon type={row.request_type} />
                      <div>
                        <div className="font-bold text-[#1f2430]">{row.title || row.request_type_label}</div>
                        <button type="button" onClick={() => copyText(row.ticket_number)} className="mt-0.5 inline-flex items-center gap-1 text-xs text-[#a99e8a] hover:text-[#d06a21]">
                          {row.ticket_number || 'Pending ID'} · raised {formatDate(row.created_at.slice(0, 10))}<Copy size={11} />
                        </button>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-[#5f5a4f]">{row.request_type_label}</td>
                  <td className="px-5 py-4 text-[#5f5a4f]">{summarize(row)}</td>
                  <td className="px-5 py-4"><RequestStatusBadge status={row.status} /></td>
                  <td className="px-6 py-4 text-right">
                    <button type="button" onClick={() => onView(row)} className="font-bold text-[#d06a21] hover:underline">{row.status === 'rejected' ? 'Details' : 'View'}</button>
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

function ApprovalQueueCard({ rows, canReassign, onView, onAction }: {
  rows: EmployeeRequest[];
  canReassign: boolean;
  onView: (row: EmployeeRequest) => void;
  onAction: (row: EmployeeRequest, action: 'submit' | 'cancel' | 'approve' | 'reject') => void;
}) {
  return (
    <Card className="overflow-hidden border-[#ece5d8]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#ece5d8] px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#fcecec] text-[#d64545]"><CheckCircle2 size={18} /></div>
          <h2 className="text-lg font-bold text-[#1f2430]">Approval Queue</h2>
          <span className="rounded-full bg-[#fcecec] px-2.5 py-1 text-xs font-bold text-[#c94c38]">{rows.length} waiting</span>
        </div>
        <a href="/employee/approvals" className="text-sm font-bold text-[#d06a21]">Go to Approvals <ArrowRight className="inline" size={14} /></a>
      </div>
      {rows.length === 0 ? (
        <div className="m-6 rounded-2xl border border-dashed border-[#dfd2bc] px-5 py-12 text-center text-sm text-[#8a8371]">
          <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-[#8fb18d]" />
          No requests are waiting for your approval.
        </div>
      ) : (
        <div className="space-y-3 p-6">
          {rows.map((row) => {
            const initials = row.employee_name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
            return (
              <div key={row.id} className="flex flex-wrap items-center gap-4 rounded-2xl border border-[#ece5d8] bg-[#fffaf3] px-5 py-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#2b3243] text-sm font-bold text-white">{initials || '—'}</div>
                <button type="button" onClick={() => onView(row)} className="min-w-[230px] flex-1 text-left">
                  <div className="font-bold text-[#1f2430]">{row.employee_name}</div>
                  <div className="mt-0.5 text-sm text-[#8a8371]">{row.request_type_label} · {row.title || row.reason || 'Approval requested'}</div>
                </button>
                <div className="min-w-[150px] text-right">
                  <div className="font-bold text-[#1f2430]">{summarize(row)}</div>
                  <div className={`mt-0.5 text-xs ${pendingTone(row.days_pending)}`}>{row.days_pending ? `waiting ${row.days_pending} day${row.days_pending === 1 ? '' : 's'}` : 'requested recently'}</div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={() => onAction(row, 'reject')}>Decline</Button>
                  <Button size="sm" onClick={() => onAction(row, 'approve')}>Approve</Button>
                  {canReassign && row.can_reassign && <Button size="sm" variant="ghost" icon={<GitBranch size={13} />} onClick={() => onView(row)}>More</Button>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function RequestModal({
  initialType,
  lockedType = true,
  policies,
  onClose,
  onSave,
}: {
  initialType: RequestType;
  lockedType?: boolean;
  policies: RequestPolicyMap;
  onClose: () => void;
  onSave: (form: FormState) => Promise<void>;
}) {
  const [form, setForm] = useState<FormState>(() => emptyForm(initialType));
  const [saving, setSaving] = useState(false);
  const [fileError, setFileError] = useState('');
  const [formError, setFormError] = useState('');
  const activePolicy = policies[form.request_type];
  const maxAttachmentBytes = activePolicy?.maximum_attachment_size || MAX_RECEIPT_BYTES;
  const acceptedFileTypes = activePolicy?.accepted_file_types?.join(',') || '.pdf,.jpg,.jpeg,.png,.webp,.doc,.docx';

  const setField = (field: keyof FormState, value: string | File | null) => {
    setFormError('');
    setForm((prev) => ({ ...prev, [field]: value }));
  };
  const previewUrl = useMemo(() => form.attachment && form.attachment.type.startsWith('image/') ? URL.createObjectURL(form.attachment) : '', [form.attachment]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const submit = async (action: 'draft' | 'submit') => {
    setFormError('');
    setSaving(true);
    try {
      await onSave({ ...form, action });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not save request. Please review and try again.');
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/35 p-6 backdrop-blur-sm">
      <Card className="max-h-[90vh] w-full max-w-2xl overflow-hidden shadow-[0_24px_80px_rgba(31,41,55,0.24)]">
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-6 py-5">
          <div>
            <h2 className="text-lg font-bold text-[var(--color-brand-navy)]">New {requestTypes.find((item) => item.type === form.request_type)?.label || 'Request'} Request</h2>
            <p className="mt-1 text-sm text-gray-500">Complete the required fields and submit for approval.</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg"><X size={18} /></button>
        </div>
        <div className="max-h-[calc(90vh-150px)] overflow-y-auto p-6">
          {formError && (
            <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{formError}</span>
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            {!lockedType && (
              <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">
                Request Type
                <select value={form.request_type} onChange={(event) => { setFormError(''); setForm(emptyForm(event.target.value as RequestType)); }} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive">
                  {requestTypes.map((item) => <option key={item.type} value={item.type}>{item.label}</option>)}
                </select>
              </label>
            )}
            {form.request_type === 'expense' && (
              <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">
                Category
                <input value={form.category} onChange={(event) => setField('category', event.target.value)} placeholder="Travel, meal, software..." className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" />
              </label>
            )}
            {form.request_type === 'application_issue' && (
              <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)] md:col-span-2">
                Issue Category
                <select value={form.category} onChange={(event) => setField('category', event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive">
                  <option value="">Select issue category</option>
                  {applicationIssueCategories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
            )}
            {form.request_type === 'wfh' ? (
              <>
                <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">From Date<input type="date" min={activePolicy?.min_date || undefined} max={activePolicy?.max_date || undefined} value={form.start_date} onChange={(event) => setField('start_date', event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">To Date<input type="date" min={form.start_date || activePolicy?.min_date || undefined} max={activePolicy?.max_date || undefined} value={form.end_date} onChange={(event) => setField('end_date', event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
              </>
            ) : form.request_type !== 'application_issue' ? (
              <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">
                Date
                <input type="date" min={activePolicy?.min_date || undefined} max={activePolicy?.max_date || undefined} value={form.request_date} onChange={(event) => setField('request_date', event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" />
              </label>
            ) : null}
            {form.request_type === 'short_permission' && (
              <>
                <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">Start Time<input type="time" value={form.start_time} onChange={(event) => setField('start_time', event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">End Time<input type="time" value={form.end_time} onChange={(event) => setField('end_time', event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
              </>
            )}
            {form.request_type === 'overtime' && (
              <>
                <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">Start Time<input type="time" value={form.start_time} onChange={(event) => setField('start_time', event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">End Time<input type="time" value={form.end_time} onChange={(event) => setField('end_time', event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
              </>
            )}
            {form.request_type === 'expense' && (
              <>
                <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">Amount<input type="number" min="0.01" step="0.01" value={form.amount} onChange={(event) => setField('amount', event.target.value)} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)]">Currency<input value={form.currency} onChange={(event) => setField('currency', event.target.value.toUpperCase())} className="h-11 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 outline-none focus:border-olive" /></label>
                <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)] md:col-span-2">
                  Receipt
                  <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-warm-bg p-3 text-sm text-gray-500">
                    <input
                      type="file"
                      accept={acceptedFileTypes}
                      onChange={(event) => {
                        const file = event.target.files?.[0] || null;
                        setFileError('');
                        if (file && file.size > maxAttachmentBytes) {
                          setField('attachment', null);
                          setFileError(`File size exceeds ${formatFileSize(maxAttachmentBytes)}.`);
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
                            <div className="font-semibold text-[var(--color-brand-navy)]">{form.attachment.name}</div>
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
            {activePolicy && form.request_type !== 'application_issue' && (
              <div className="rounded-lg border border-olive/15 bg-olive/5 px-3 py-2 text-xs leading-5 text-gray-600 md:col-span-2">
                Valid dates
                {activePolicy.min_date ? ` from ${formatDate(activePolicy.min_date)}` : ''}
                {activePolicy.max_date ? ` through ${formatDate(activePolicy.max_date)}` : ''}
                . Approval starts with your Reporting Manager{activePolicy.requires_hr_approval ? ', then moves to HR review.' : '.'}
              </div>
            )}
            {form.request_type === 'application_issue' && (
              <div className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs leading-5 text-[var(--color-brand-navy)] md:col-span-2">
                Application issues are sent to HR/application support for review. Include the page name, what you expected, and what actually happened.
              </div>
            )}
            <label className="grid gap-1 text-sm font-semibold text-[var(--color-brand-navy)] md:col-span-2">
              {form.request_type === 'application_issue' ? 'Issue Details' : 'Reason'}
              <textarea value={form.reason} maxLength={500} onChange={(event) => setField('reason', event.target.value)} placeholder={form.request_type === 'application_issue' ? 'Example: On Timesheets, the date column overlaps on small screens...' : 'Add enough context for your manager...'} className="min-h-[96px] rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-3 outline-none focus:border-olive" />
              <span className="text-right text-xs text-gray-400">{form.reason.length}/500</span>
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-3 border-t border-[var(--color-border)] px-6 py-4">
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
      <div className="mb-3 flex items-center gap-2 text-sm font-bold text-[var(--color-brand-navy)]"><GitBranch size={15} className="text-olive" /> Workflow</div>
      <div className="grid gap-3">
        {steps.map((step, index) => (
          <div key={step.key} className="flex items-center gap-3">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${step.complete ? 'bg-olive text-white' : 'bg-gray-100 text-gray-400'}`}>{index + 1}</span>
            <span className={`text-sm ${step.complete ? 'font-semibold text-[var(--color-brand-navy)]' : 'text-gray-500'}`}>{step.label}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ActionReasonModal({
  intent,
  submitting,
  error,
  onClose,
  onConfirm,
}: {
  intent: RequestActionIntent;
  submitting: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState('');
  const isReject = intent.action === 'reject';
  const title = isReject ? 'Reject request' : 'Cancel request';
  const helper = isReject
    ? 'This reason will be visible to the employee and saved in the request history.'
    : 'This reason is saved for audit history. Use a short, clear explanation.';
  const canSubmit = isReject ? reason.trim().length > 0 : true;

  return createPortal(
    <div className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/35 p-6 backdrop-blur-sm">
      <Card className="w-full max-w-lg overflow-hidden shadow-[0_24px_80px_rgba(31,41,55,0.24)]">
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-6 py-5">
          <div>
            <h2 className="text-lg font-bold text-[var(--color-brand-navy)]">{title}</h2>
            <p className="mt-1 text-sm text-gray-500">{intent.row.ticket_number || intent.row.request_type_label}</p>
          </div>
          <button onClick={onClose} disabled={submitting} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg disabled:cursor-not-allowed disabled:opacity-50">
            <X size={18} />
          </button>
        </div>
        <div className="p-6">
          <div className="mb-4 rounded-xl border border-[var(--color-border)] bg-warm-bg p-4">
            <div className="text-sm font-bold text-[var(--color-brand-navy)]">{intent.row.request_type_label}</div>
            <div className="mt-1 text-sm text-gray-500">{summarize(intent.row)}</div>
          </div>
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <label className="grid gap-2 text-sm font-semibold text-[var(--color-brand-navy)]">
            {isReject ? 'Rejection reason' : 'Cancellation reason'}
            <textarea
              value={reason}
              maxLength={500}
              onChange={(event) => setReason(event.target.value)}
              placeholder={isReject ? 'Explain why this request is being rejected.' : 'Optional: add why this request is being cancelled.'}
              className="min-h-[120px] rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-3 text-sm outline-none focus:border-olive"
              autoFocus
            />
          </label>
          <div className="mt-2 flex items-start justify-between gap-3 text-xs text-gray-500">
            <span>{helper}</span>
            <span>{reason.length}/500</span>
          </div>
        </div>
        <div className="flex justify-end gap-3 border-t border-[var(--color-border)] px-6 py-4">
          <Button variant="ghost" disabled={submitting} onClick={onClose}>Keep Request</Button>
          <Button
            disabled={submitting || !canSubmit}
            icon={submitting ? <Loader2 size={14} className="animate-spin" /> : isReject ? <X size={14} /> : <Trash2 size={14} />}
            onClick={() => onConfirm(reason.trim())}
          >
            {submitting ? 'Saving' : isReject ? 'Reject Request' : 'Cancel Request'}
          </Button>
        </div>
      </Card>
    </div>,
    document.body
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
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-6 py-5">
          <div>
            <div className="mb-2"><Badge variant={statusVariant(request.status)}>{labelize(request.status)}</Badge></div>
            <h2 className="text-lg font-bold text-[var(--color-brand-navy)]">{request.request_type_label}</h2>
            <p className="text-sm text-gray-500">{summarize(request)}</p>
            <button
              type="button"
              onClick={() => copyText(request.ticket_number)}
              className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-1.5 font-mono text-xs font-bold text-olive hover:bg-hover-bg"
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
                <div className="flex items-center gap-2 text-sm font-bold text-[var(--color-brand-navy)]"><UserRound size={15} className="text-olive" /> Ownership</div>
                <Button size="sm" variant="ghost" icon={<GitBranch size={13} />} onClick={() => setReassignOpen((value) => !value)}>{reassignOpen ? 'Close' : 'Reassign'}</Button>
              </div>
              <div className="text-sm text-gray-600">Current owner: <span className="font-semibold text-[var(--color-brand-navy)]">{request.current_owner_name || '-'}</span></div>
              {reassignOpen && (
                <div className="mt-4 grid gap-3">
                  <select value={newOwnerId} onChange={(event) => setNewOwnerId(event.target.value)} className="h-10 rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 text-sm outline-none focus:border-olive">
                    <option value="">Select new owner</option>
                    {employees.map((employee) => (
                      <option key={employee.id} value={employee.id}>{employee.name} {employee.role ? `(${labelize(employee.role)})` : ''}</option>
                    ))}
                  </select>
                  <textarea value={reassignReason} onChange={(event) => setReassignReason(event.target.value)} placeholder="Reason for reassignment..." className="min-h-[72px] rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2 text-sm outline-none focus:border-olive" />
                  <Button size="sm" disabled={reassigning} icon={reassigning ? <Loader2 size={13} className="animate-spin" /> : <GitBranch size={13} />} onClick={submitReassign}>Reassign Request</Button>
                </div>
              )}
            </Card>
          )}
          <Card className="mt-4 p-4">
            <div className="mb-1 text-xs font-bold uppercase tracking-wide text-gray-400">Reason</div>
            <p className="text-sm leading-6 text-[var(--color-brand-navy)]">{request.reason || '-'}</p>
            {request.rejection_reason && <p className="mt-3 rounded-lg bg-status-error/10 px-3 py-2 text-sm text-status-error">{request.rejection_reason}</p>}
          </Card>
          <Card className="mt-4 overflow-hidden">
            <CardHeader title="Attachments" icon={<FileText size={15} />} />
            {(request.attachments || []).length === 0 ? (
              <div className="px-5 py-5 text-sm text-gray-500">No attachments.</div>
            ) : (
              (request.attachments || []).map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] px-5 py-3 last:border-b-0">
                  <div>
                    <div className="text-sm font-bold text-[var(--color-brand-navy)]">{item.original_file_name}</div>
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
              <div className="border-t border-[var(--color-border)] p-4">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm font-semibold text-olive hover:bg-hover-bg">
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
              <div key={item.id} className="border-b border-[var(--color-border)] px-5 py-3 last:border-b-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold">{item.created_by_name}</span>
                  <span className="text-xs text-gray-400">{formatDateTime(item.created_at)}</span>
                </div>
                <p className="mt-1 text-sm text-gray-600">{item.body || item.comment}</p>
                {item.is_internal && <Badge variant="neutral">Internal</Badge>}
              </div>
            ))}
            <div className="grid gap-2 border-t border-[var(--color-border)] p-4">
              <textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add a comment..." className="min-h-[78px] rounded-lg border border-[var(--color-border)] bg-warm-bg px-3 py-2 text-sm outline-none focus:border-olive" />
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
                <div key={item.id} className="border-b border-[var(--color-border)] px-5 py-3 text-sm last:border-b-0">
                  <div className="font-semibold text-[var(--color-brand-navy)]">{item.title}</div>
                  <div className="mt-1 text-xs leading-5 text-gray-500">{item.detail}</div>
                  <div className="mt-1 text-[11px] text-gray-400">{formatDateTime(item.at)}</div>
                </div>
              ))
            )}
          </Card>
          <Card className="mt-4 overflow-hidden">
            <CardHeader title="History" icon={<CalendarDays size={15} />} />
            {(request.history || []).map((item) => (
              <div key={item.id} className="border-b border-[var(--color-border)] px-5 py-3 text-sm last:border-b-0">
                <div className="font-semibold text-[var(--color-brand-navy)]">{labelize(item.action)} to {labelize(item.new_status)}</div>
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
    <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg p-3">
      <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{label}</div>
      <div className="mt-1 text-sm font-bold text-[var(--color-brand-navy)]">{value || '-'}</div>
    </div>
  );
}

export function RequestsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
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
  const [policies, setPolicies] = useState<RequestPolicyMap>({});
  const [actionIntent, setActionIntent] = useState<RequestActionIntent | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [actionError, setActionError] = useState('');

  const role = roleKey(user?.role);
  const canReview = ['manager', 'super_admin', 'admin', 'hr_admin', 'global_access'].includes(role);
  const canReassign = isPrivilegedAdmin(user?.role);
  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  useEffect(() => {
    const newType = searchParams.get('new');
    if (newType === 'application_issue') {
      setModalType('application_issue');
      const next = new URLSearchParams(searchParams);
      next.delete('new');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

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
    if (!user) return;
    const controller = new AbortController();
    const loadPolicies = async () => {
      const res = await fetch(`${API_BASE}/requests/policies`, { headers, signal: controller.signal });
      const body = await res.json().catch(() => null);
      if (res.ok) setPolicies(body?.policies || {});
    };
    loadPolicies().catch(() => undefined);
    return () => controller.abort();
  }, [headers, user]);

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
    if (form.request_type === 'application_issue') {
      payload.application_issue = {
        category: form.category,
        description: form.reason,
      };
    }
    const res = await fetch(`${API_BASE}/requests`, { method: 'POST', headers, body: JSON.stringify(payload) });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(body?.detail || 'Could not save request.');
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
        await load();
        throw new Error(uploadBody?.detail || 'Request saved, but receipt upload failed.');
      }
      if (shouldSubmit) {
        const submitRes = await fetch(`${API_BASE}/requests/${body.id}/submit`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ reason: null }),
        });
        const submitBody = await submitRes.json().catch(() => null);
        if (!submitRes.ok) {
          await load();
          throw new Error(submitBody?.detail || 'Receipt uploaded, but request could not be submitted.');
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
    if (action === 'cancel' || action === 'reject') {
      setActionError('');
      setActionIntent({ row, action });
      return;
    }
    const payload = action === 'approve'
      ? { notes: null }
      : { reason: null };
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

  const confirmActionIntent = async (reason: string) => {
    if (!actionIntent) return;
    if (actionIntent.action === 'reject' && !reason.trim()) return;
    setActionError('');
    setActionSubmitting(true);
    const payload = actionIntent.action === 'reject'
      ? { reason: reason.trim() }
      : { reason: reason.trim() || null };
    try {
      const res = await fetch(`${API_BASE}/requests/${actionIntent.row.id}/${actionIntent.action}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setActionError(body?.detail || 'Action failed. Please review and try again.');
        return;
      }
      const message = `Request ${actionIntent.action === 'reject' ? 'rejected' : 'cancelled'}.`;
      setActionIntent(null);
      setActionError('');
      setDetail(body);
      await load();
      showToast({ message });
    } catch {
      setActionError('Could not reach the server. Please try again.');
    } finally {
      setActionSubmitting(false);
    }
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

  const pendingCount = myRequests.filter((row) => row.status === 'pending').length;
  const approvedCount = myRequests.filter((row) => row.status === 'approved' || row.status === 'paid').length;

  return (
    <PageShell>
      {error && <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}
      <div className="-mt-[72px] mb-7 flex min-h-[56px] justify-end gap-3 max-lg:mt-0 max-lg:justify-start">
        <div className="min-w-[105px] rounded-2xl border border-[#ece5d8] bg-white px-4 py-2.5 text-center shadow-sm">
          <div className="text-2xl font-bold text-[#c38214]">{pendingCount}</div>
          <div className="text-[11px] font-bold uppercase tracking-wide text-[#a99e8a]">Pending</div>
        </div>
        <div className="min-w-[105px] rounded-2xl border border-[#ece5d8] bg-white px-4 py-2.5 text-center shadow-sm">
          <div className="text-2xl font-bold text-[#3f9b52]">{approvedCount}</div>
          <div className="text-[11px] font-bold uppercase tracking-wide text-[#a99e8a]">Approved</div>
        </div>
        {canReview && (
          <div className="min-w-[105px] rounded-2xl border border-[#ece5d8] bg-white px-4 py-2.5 text-center shadow-sm">
            <div className="text-2xl font-bold text-[#c94c38]">{queue.length}</div>
            <div className="text-[11px] font-bold uppercase tracking-wide text-[#a99e8a]">Awaiting Me</div>
          </div>
        )}
      </div>
      <RequestTypeCards onCreate={setModalType} />
      <div className="mt-6 flex flex-wrap items-center gap-3 rounded-2xl border border-[#ece5d8] bg-white p-4 shadow-sm">
        <label className="relative min-w-[260px] flex-1">
          <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-[#a99e8a]" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search requests..."
            className="h-12 w-full rounded-xl border border-[#ece5d8] bg-[#faf8f3] pl-11 pr-4 text-sm outline-none focus:border-[#d97a34]"
          />
        </label>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="h-12 min-w-[140px] rounded-xl border border-[#ece5d8] bg-[#faf8f3] px-4 text-sm outline-none focus:border-[#d97a34]">
          {['all', 'draft', 'pending', 'approved', 'rejected', 'cancelled', 'paid'].map((item) => <option key={item} value={item}>Status: {labelize(item)}</option>)}
        </select>
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="h-12 min-w-[170px] rounded-xl border border-[#ece5d8] bg-[#faf8f3] px-4 text-sm outline-none focus:border-[#d97a34]">
          <option value="all">Type: All</option>
          {requestTypes.map((item) => <option key={item.type} value={item.type}>{item.label}</option>)}
        </select>
        <div className="flex items-center gap-2">
          <input aria-label="From date" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="h-12 rounded-xl border border-[#ece5d8] bg-[#faf8f3] px-3 text-sm outline-none focus:border-[#d97a34]" />
          <ArrowRight size={14} className="text-[#a99e8a]" />
          <input aria-label="To date" type="date" value={dateTo} min={dateFrom || undefined} onChange={(event) => setDateTo(event.target.value)} className="h-12 rounded-xl border border-[#ece5d8] bg-[#faf8f3] px-3 text-sm outline-none focus:border-[#d97a34]" />
        </div>
        <Button variant="ghost" icon={<RefreshCw size={14} className={loading ? 'animate-spin' : ''} />} disabled={loading} onClick={load}>Refresh</Button>
      </div>
      <div className="mt-6 grid gap-6">
        {loading ? (
          <SkeletonRows />
        ) : (
          <>
            <MyRequestsCard rows={myRequests} onCreate={() => setModalType('wfh')} onView={openDetail} />
            {canReview && <ApprovalQueueCard rows={queue} canReassign={canReassign} onView={openDetail} onAction={runAction} />}
          </>
        )}
      </div>
      {modalType && <RequestModal initialType={modalType} policies={policies} onClose={() => setModalType(null)} onSave={createFromForm} />}
      {detail && <DetailDrawer request={detail} userRole={user?.role} employees={employees} onClose={() => setDetail(null)} onRefresh={refreshDetail} onAction={runAction} onMarkPaid={markPaid} onReassign={reassign} headers={headers} />}
      {actionIntent && (
        <ActionReasonModal
          intent={actionIntent}
          submitting={actionSubmitting}
          error={actionError}
          onClose={() => {
            if (actionSubmitting) return;
            setActionIntent(null);
            setActionError('');
          }}
          onConfirm={confirmActionIntent}
        />
      )}
    </PageShell>
  );
}

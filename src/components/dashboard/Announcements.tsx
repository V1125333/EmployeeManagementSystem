import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import {
  AlertTriangle, Bell, CalendarClock, CheckCircle, Edit3, Eye, FileText,
  Megaphone, Paperclip, Pin, Send, ShieldCheck, Trash2, Upload, Users, X,
} from 'lucide-react';
import { Badge, Button, Card, CardHeader } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = (() => {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (configured) return configured;
  return '/api/v1';
})();

const TYPES = ['general', 'hr', 'it_system', 'policy', 'event', 'celebration', 'emergency'];
const PRIORITIES = ['low', 'normal', 'high', 'critical'];
const AUDIENCES = ['everyone', 'department', 'role', 'employee'];
const DEPARTMENTS = ['Engineering', 'Product', 'Design', 'Marketing', 'Sales', 'Operations', 'People', 'Finance'];
const ROLES = ['super_admin', 'hr_admin', 'manager', 'employee', 'trainee'];

interface Announcement {
  id: string;
  title: string;
  message?: string;
  description?: string;
  type?: string;
  announcement_type?: string;
  priority?: string;
  audience_type?: string;
  status?: string;
  is_pinned: boolean;
  requires_acknowledgment?: boolean;
  publish_at: string | null;
  expires_at: string | null;
  created_by?: string;
  created_at: string | null;
  publish_date?: string | null;
  target_values?: string[];
  acknowledged?: boolean;
  read?: boolean;
  acknowledged_count?: number;
  pending_count?: number;
  acknowledgment_percentage?: number;
}

interface EmployeeOption {
  id: string;
  first_name: string;
  last_name: string;
  work_email: string;
  department: string;
  role: string;
}

interface FormState {
  id?: string;
  title: string;
  message: string;
  announcement_type: string;
  priority: string;
  audience_type: string;
  target_values: string[];
  status: 'draft' | 'published';
  is_pinned: boolean;
  requires_acknowledgment: boolean;
  show_on_dashboard: boolean;
  send_email: boolean;
  schedule_mode: 'now' | 'later';
  publish_at: string;
  expires_at: string;
  attachments: string[];
}

const emptyForm: FormState = {
  title: '',
  message: '',
  announcement_type: 'general',
  priority: 'normal',
  audience_type: 'everyone',
  target_values: [],
  status: 'published',
  is_pinned: false,
  requires_acknowledgment: false,
  show_on_dashboard: true,
  send_email: false,
  schedule_mode: 'now',
  publish_at: '',
  expires_at: '',
  attachments: [],
};

function titleCase(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value?: string | null) {
  if (!value) return 'Not set';
  return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function authHeaders(user: ReturnType<typeof useAuth>['user']) {
  const role = (user?.role || '').toLowerCase().replace(/\s+/g, '_') === 'global_access'
    ? 'super_admin'
    : user?.role || '';

  return {
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-role': role,
    'x-user-email': user?.email || '',
    'x-user-name': user?.name || '',
  };
}

async function readApiError(res: Response, fallback: string) {
  try {
    const data = await res.json();
    if (Array.isArray(data.detail)) {
      return data.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(', ') || fallback;
    }
    return data.detail || data.message || fallback;
  } catch {
    return fallback;
  }
}

function formatFetchError(err: unknown) {
  if (err instanceof TypeError && err.message.toLowerCase().includes('fetch')) {
    return 'Cannot reach the backend through the app proxy. Please make sure FastAPI is running on port 8000 and restart the Vite dev server if this just changed.';
  }
  return err instanceof Error ? err.message : 'Unable to save announcement';
}

function isAdminRole(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalized);
}

function priorityVariant(priority: string): 'olive' | 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (priority === 'critical') return 'error';
  if (priority === 'high') return 'warning';
  if (priority === 'low') return 'neutral';
  return 'olive';
}

function priorityDot(priority: string) {
  if (priority === 'critical') return 'bg-status-error';
  if (priority === 'high') return 'bg-status-warning';
  if (priority === 'low') return 'bg-gray-400';
  return 'bg-olive';
}

function statusVariant(status: string): 'olive' | 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (status === 'published') return 'success';
  if (status === 'expired') return 'neutral';
  return 'warning';
}

const categoryStyles: Record<string, { dot: string; pill: string; label: string }> = {
  general: { dot: '#66785F', pill: 'bg-olive/10 text-olive', label: 'General' },
  hr: { dot: '#7E9BB7', pill: 'bg-[#7E9BB7]/12 text-[#55728E]', label: 'HR' },
  policy: { dot: '#D6A85F', pill: 'bg-[#D6A85F]/14 text-[#9A7430]', label: 'Policy' },
  urgent: { dot: '#D97C7C', pill: 'bg-[#D97C7C]/14 text-[#B45454]', label: 'Urgent' },
};

function compactCategory(announcement: Announcement) {
  const value = (announcement.type || announcement.announcement_type || 'general').toLowerCase();
  if (value === 'hr') return 'hr';
  if (value === 'policy') return 'policy';
  if (value === 'urgent' || value === 'emergency' || announcement.priority === 'critical') return 'urgent';
  return 'general';
}

function announcementDescription(announcement: Announcement) {
  return announcement.description || announcement.message || '';
}

function toApiPayload(form: FormState, status: 'draft' | 'published') {
  return {
    title: form.title.trim(),
    message: form.message.trim(),
    announcement_type: form.announcement_type,
    priority: form.priority,
    audience_type: form.audience_type,
    target_values: form.audience_type === 'everyone' ? [] : form.target_values,
    status,
    is_pinned: form.is_pinned,
    requires_acknowledgment: form.requires_acknowledgment,
    publish_at: form.schedule_mode === 'later' && form.publish_at ? new Date(form.publish_at).toISOString() : null,
    expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
  };
}

function AnnouncementFormSection({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: ReactNode;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-[#E5E7EB] bg-warm-card p-5 shadow-card">
      <div className="mb-5 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-olive/10 text-olive">{icon}</div>
        <div>
          <h3 className="text-[15px] font-bold text-[#2F3437]">{title}</h3>
          <p className="mt-0.5 text-[13px] text-gray-500">{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function DeliveryOptionCard({
  label,
  description,
  checked,
  onChange,
  disabled = false,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className={cn('flex min-h-[78px] cursor-pointer items-start gap-3 rounded-xl border px-3.5 py-3 transition-all', checked ? 'border-olive/40 bg-olive/5' : 'border-[#E5E7EB] bg-warm-bg hover:border-olive/25', disabled && 'cursor-not-allowed opacity-55')}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} className="mt-1 accent-olive" />
      <span>
        <span className="block text-[13px] font-bold text-[#2F3437]">{label}</span>
        <span className="mt-0.5 block text-[12px] leading-relaxed text-gray-500">{description}</span>
      </span>
    </label>
  );
}

function CreateAnnouncementDrawer({
  open,
  onClose,
  onSaved,
  editing,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  editing: Announcement | null;
}) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [form, setForm] = useState<FormState>(emptyForm);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [employeeSearch, setEmployeeSearch] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (editing) {
      setForm({
        id: editing.id,
        title: editing.title,
        message: announcementDescription(editing),
        announcement_type: editing.announcement_type || editing.type || 'general',
        priority: editing.priority || 'normal',
        audience_type: editing.audience_type || 'everyone',
        target_values: editing.target_values || [],
        status: editing.status === 'published' ? 'published' : 'draft',
        is_pinned: editing.is_pinned,
        requires_acknowledgment: Boolean(editing.requires_acknowledgment),
        show_on_dashboard: true,
        send_email: false,
        schedule_mode: editing.publish_at && new Date(editing.publish_at) > new Date() ? 'later' : 'now',
        publish_at: editing.publish_at ? editing.publish_at.slice(0, 16) : '',
        expires_at: editing.expires_at ? editing.expires_at.slice(0, 16) : '',
        attachments: [],
      });
    } else {
      setForm(emptyForm);
    }
    setError('');
  }, [editing, open]);

  useEffect(() => {
    if (!open || form.audience_type !== 'employee') return;
    fetch(`${API_BASE}/employees/`, { headers: authHeaders(user) })
      .then((res) => res.json())
      .then((data) => setEmployees(data.employees || []))
      .catch(() => setEmployees([]));
  }, [form.audience_type, open, user]);

  const filteredEmployees = useMemo(() => {
    const term = employeeSearch.trim().toLowerCase();
    if (!term) return employees;
    return employees.filter((employee) => {
      const fullName = `${employee.first_name} ${employee.last_name}`.toLowerCase();
      return fullName.includes(term) || employee.work_email.toLowerCase().includes(term);
    });
  }, [employeeSearch, employees]);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({
      ...current,
      [key]: value,
      ...(key === 'audience_type' ? { target_values: [] } : {}),
    }));
    if (error) setError('');
  };

  const validate = (status: 'draft' | 'published') => {
    if (!form.title.trim()) return 'Announcement title is required.';
    if (!form.message.trim()) return 'Message is required.';
    if (form.expires_at && new Date(form.expires_at) <= new Date()) {
      return 'Expiry date must be in the future.';
    }
    const publishDate = form.schedule_mode === 'later' && form.publish_at ? new Date(form.publish_at) : new Date();
    if (form.schedule_mode === 'later' && !form.publish_at) {
      return 'Publish date is required when scheduling later.';
    }
    if (form.expires_at && new Date(form.expires_at) <= publishDate) {
      return 'Expiry date must be after the publish date.';
    }
    if (status === 'published' && form.audience_type !== 'everyone' && form.target_values.length === 0) {
      return 'Select at least one audience target before publishing.';
    }
    return '';
  };

  const save = async (status: 'draft' | 'published') => {
    const validation = validate(status);
    if (validation) {
      setError(validation);
      return;
    }

    setSaving(true);
    setError('');
    try {
      const url = form.id ? `${API_BASE}/announcements/${form.id}` : `${API_BASE}/announcements`;
      const res = await fetch(url, {
        method: form.id ? 'PUT' : 'POST',
        headers: authHeaders(user),
        body: JSON.stringify(toApiPayload(form, status)),
      });
      if (!res.ok) {
        throw new Error(await readApiError(res, 'Unable to save announcement'));
      }
      const result = await res.json();
      if (!result.success) {
        throw new Error(result.detail || result.message || 'Unable to save announcement');
      }
      showToast({ message: status === 'published' ? 'Announcement published' : 'Announcement saved as draft' });
      onSaved();
      onClose();
    } catch (err) {
      setError(formatFetchError(err));
    } finally {
      setSaving(false);
    }
  };

  const toggleTarget = (value: string) => {
    const next = form.target_values.includes(value)
      ? form.target_values.filter((item) => item !== value)
      : [...form.target_values, value];
    update('target_values', next);
  };

  const renderAudienceTargets = () => {
    if (form.audience_type === 'everyone') return null;
    if (form.audience_type === 'department') {
      return (
        <select value={form.target_values[0] || ''} onChange={(e) => update('target_values', e.target.value ? [e.target.value] : [])} className="input-control">
          <option value="">Select department</option>
          {DEPARTMENTS.map((department) => <option key={department} value={department}>{department}</option>)}
        </select>
      );
    }
    if (form.audience_type === 'role') {
      return (
        <select value={form.target_values[0] || ''} onChange={(e) => update('target_values', e.target.value ? [e.target.value] : [])} className="input-control">
          <option value="">Select role</option>
          {ROLES.map((role) => <option key={role} value={role}>{titleCase(role)}</option>)}
        </select>
      );
    }
    return (
      <div className="space-y-2">
        <input
          value={employeeSearch}
          onChange={(e) => setEmployeeSearch(e.target.value)}
          placeholder="Search employees..."
          className="input-control"
        />
        <div className="max-h-44 overflow-y-auto rounded-xl border border-[#E5E7EB] bg-warm-bg">
          {filteredEmployees.length > 0 ? filteredEmployees.map((employee) => {
            const fullName = `${employee.first_name} ${employee.last_name}`;
            return (
              <label key={employee.id} className="flex items-center gap-3 px-3 py-2.5 border-b border-[#E5E7EB] last:border-b-0 text-[13px] cursor-pointer hover:bg-hover-bg">
                <input
                  type="checkbox"
                  checked={form.target_values.includes(employee.id)}
                  onChange={() => toggleTarget(employee.id)}
                  className="accent-olive"
                />
                <span className="min-w-0">
                  <span className="block font-semibold text-[#2F3437] truncate">{fullName}</span>
                  <span className="block text-gray-400 truncate">{employee.work_email}</span>
                </span>
              </label>
            );
          }) : (
            <div className="px-3 py-4 text-sm text-gray-400">No employees found</div>
          )}
        </div>
      </div>
    );
  };

  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  const addAttachments = (files: FileList | null) => {
    if (!files) return;
    update('attachments', [...form.attachments, ...Array.from(files).map((file) => file.name)]);
  };

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[1000] flex justify-end">
      <div className="absolute inset-0 bg-[#2F3437]/35 backdrop-blur-[3px]" onClick={onClose} />
      <style>{`.input-control{width:100%;padding:11px 14px;border-radius:12px;border:1px solid #E5E7EB;background:#F8F8F5;color:#2F3437;font-size:14px;font-weight:500;outline:none}.input-control:focus{border-color:rgb(102 120 95 / .45);box-shadow:0 0 0 3px rgb(102 120 95 / .1)}.announcement-workspace{width:min(100vw,800px)}@media (min-width:1024px){.announcement-workspace{width:52vw;min-width:720px}}`}</style>
      <aside className="announcement-workspace fixed right-0 top-0 flex h-screen flex-col border-l border-[#E5E7EB] bg-warm-bg shadow-[-18px_0_45px_rgba(47,52,55,0.16)] animate-[slideInRight_0.3s_cubic-bezier(0.16,1,0.3,1)]">
        <header className="sticky top-0 z-10 border-b border-[#E5E7EB] bg-warm-card/95 px-7 py-6 backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-[#2F3437]">{editing ? 'Edit Announcement' : 'Create Announcement'}</h2>
              <p className="mt-1 text-sm text-gray-500">Publish updates, alerts, and company-wide communications.</p>
            </div>
            <button onClick={onClose} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-gray-400 transition-all hover:bg-hover-bg hover:text-gray-600">
              <X size={18} />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-7 py-6">
          <div className="mx-auto max-w-[780px] space-y-5">
            <AnnouncementFormSection icon={<FileText size={17} />} title="Announcement Content" subtitle="Craft the message employees will see on their dashboard.">
              <div className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">Announcement Title</label>
                  <input value={form.title} onChange={(e) => update('title', e.target.value)} className="input-control" placeholder="e.g. Quarterly town hall on Friday" />
                </div>
                <div>
                  <label className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">Description / Rich Text Area</label>
                  <textarea value={form.message} onChange={(e) => update('message', e.target.value)} rows={7} className="input-control resize-none leading-relaxed" placeholder="Write the full announcement message..." />
                </div>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">Announcement Type</label>
                    <select value={form.announcement_type} onChange={(e) => update('announcement_type', e.target.value)} className="input-control">
                      {TYPES.map((type) => <option key={type} value={type}>{titleCase(type)}</option>)}
                    </select>
                    <div className="mt-2"><Badge variant="info">{titleCase(form.announcement_type)}</Badge></div>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">Priority</label>
                    <select value={form.priority} onChange={(e) => update('priority', e.target.value)} className="input-control">
                      {PRIORITIES.map((priority) => <option key={priority} value={priority}>{titleCase(priority)}</option>)}
                    </select>
                    <div className="mt-2 flex items-center gap-2 text-[12px] font-semibold text-gray-500">
                      <span className={cn('h-2.5 w-2.5 rounded-full', priorityDot(form.priority))} />
                      {titleCase(form.priority)} priority
                    </div>
                  </div>
                </div>
              </div>
            </AnnouncementFormSection>

            <AnnouncementFormSection icon={<Users size={17} />} title="Audience Selection" subtitle="Choose exactly who should receive this communication.">
              <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                {AUDIENCES.map((audience) => (
                  <button key={audience} onClick={() => update('audience_type', audience)} className={cn('rounded-xl border px-3 py-3 text-left text-[13px] font-bold transition-all', form.audience_type === audience ? 'border-olive/40 bg-olive/10 text-olive' : 'border-[#E5E7EB] bg-warm-bg text-[#2F3437] hover:border-olive/30')}>
                    {audience === 'employee' ? 'Specific Employees' : titleCase(audience)}
                  </button>
                ))}
              </div>
              <div className="mt-4">{renderAudienceTargets()}</div>
            </AnnouncementFormSection>

            <AnnouncementFormSection icon={<ShieldCheck size={17} />} title="Delivery Options" subtitle="Control placement, delivery channels, and employee actions.">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <DeliveryOptionCard label="Show on Dashboard" description="Display in the employee announcement widget." checked={form.show_on_dashboard} onChange={(value) => update('show_on_dashboard', value)} />
                <DeliveryOptionCard label="Send Email" description="Prepare this announcement for email delivery." checked={form.send_email} onChange={(value) => update('send_email', value)} />
                <DeliveryOptionCard label="Pin Announcement" description="Keep this announcement at the top of lists." checked={form.is_pinned} onChange={(value) => update('is_pinned', value)} />
                <DeliveryOptionCard label="Require Acknowledgment" description="Employees must confirm they have read it." checked={form.requires_acknowledgment} onChange={(value) => update('requires_acknowledgment', value)} />
                <DeliveryOptionCard label="Teams Integration" description="Future channel for Teams broadcast." checked={false} onChange={() => undefined} disabled />
                <DeliveryOptionCard label="Slack Integration" description="Future channel for Slack broadcast." checked={false} onChange={() => undefined} disabled />
              </div>
            </AnnouncementFormSection>

            <AnnouncementFormSection icon={<CalendarClock size={17} />} title="Scheduling" subtitle="Publish immediately or schedule the announcement for later.">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <label className={cn('rounded-xl border px-4 py-3 transition-all', form.schedule_mode === 'now' ? 'border-olive/40 bg-olive/10' : 'border-[#E5E7EB] bg-warm-bg')}>
                  <input type="radio" checked={form.schedule_mode === 'now'} onChange={() => update('schedule_mode', 'now')} className="mr-2 accent-olive" />
                  <span className="text-[13px] font-bold text-[#2F3437]">Publish Now</span>
                </label>
                <label className={cn('rounded-xl border px-4 py-3 transition-all', form.schedule_mode === 'later' ? 'border-olive/40 bg-olive/10' : 'border-[#E5E7EB] bg-warm-bg')}>
                  <input type="radio" checked={form.schedule_mode === 'later'} onChange={() => update('schedule_mode', 'later')} className="mr-2 accent-olive" />
                  <span className="text-[13px] font-bold text-[#2F3437]">Schedule Later</span>
                </label>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">Publish Date/Time</label>
                  <input type="datetime-local" value={form.publish_at} disabled={form.schedule_mode === 'now'} onChange={(e) => update('publish_at', e.target.value)} className="input-control disabled:cursor-not-allowed disabled:opacity-55" />
                </div>
                <div>
                  <label className="mb-1.5 block text-[13px] font-semibold text-[#2F3437]">Expiry Date</label>
                  <input type="datetime-local" value={form.expires_at} onChange={(e) => update('expires_at', e.target.value)} className="input-control" />
                </div>
              </div>
            </AnnouncementFormSection>

            <AnnouncementFormSection icon={<Paperclip size={17} />} title="Attachments" subtitle="Attach supporting files for employees to reference.">
              <label className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-[#D6D8CF] bg-warm-bg px-4 py-8 text-center transition-all hover:border-olive/40 hover:bg-olive/5">
                <Upload size={22} className="text-olive" />
                <span className="mt-3 text-[13px] font-bold text-[#2F3437]">Upload PDF, DOCX, or images</span>
                <span className="mt-1 text-[12px] text-gray-400">Files are previewed here before publishing.</span>
                <input type="file" multiple accept=".pdf,.doc,.docx,image/*" className="hidden" onChange={(e) => addAttachments(e.target.files)} />
              </label>
              {form.attachments.length > 0 && (
                <div className="mt-3 space-y-2">
                  {form.attachments.map((file) => (
                    <div key={file} className="flex items-center gap-2 rounded-xl border border-[#E5E7EB] bg-warm-bg px-3 py-2 text-[13px] font-medium text-[#2F3437]">
                      <FileText size={14} className="text-olive" />
                      <span className="truncate">{file}</span>
                    </div>
                  ))}
                </div>
              )}
            </AnnouncementFormSection>

            <AnnouncementFormSection icon={<Eye size={17} />} title="Live Preview" subtitle="Review how the announcement will appear to employees.">
              <div className="rounded-2xl border border-[#E5E7EB] bg-warm-bg p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      {form.is_pinned && <Badge variant="olive">Pinned</Badge>}
                      <Badge variant="info">{titleCase(form.announcement_type)}</Badge>
                      <Badge variant={priorityVariant(form.priority)}>{titleCase(form.priority)}</Badge>
                    </div>
                    <h4 className="text-[16px] font-bold text-[#2F3437]">{form.title || 'Announcement title preview'}</h4>
                    <p className="mt-2 text-[13px] leading-relaxed text-gray-500">{form.message || 'Your message preview will appear here as you write.'}</p>
                  </div>
                  <Bell size={18} className="shrink-0 text-olive" />
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#E5E7EB] pt-3 text-[12px] text-gray-400">
                  <span>By {user?.name || 'Super Admin'}</span>
                  {form.requires_acknowledgment && <Button size="sm" variant="soft" icon={<CheckCircle size={13} />}>Acknowledge</Button>}
                </div>
              </div>
            </AnnouncementFormSection>
          </div>
        </div>

        <footer className="sticky bottom-0 z-10 border-t border-[#E5E7EB] bg-warm-card/95 px-7 py-4 backdrop-blur">
          <div className="mx-auto flex max-w-[780px] items-center justify-between gap-3">
            <Button variant="ghost" onClick={() => save('draft')} disabled={saving}>Save Draft</Button>
            <div className="flex min-w-0 items-center gap-3">
              {error && <div className="truncate text-[13px] font-medium text-status-error">{error}</div>}
              <Button icon={<Send size={14} />} onClick={() => save('published')} disabled={saving}>
                {saving ? 'Publishing...' : 'Publish Announcement'}
              </Button>
            </div>
          </div>
        </footer>
      </aside>
    </div>,
    document.body
  );
}

export function AnnouncementsPanel({
  createOpen,
  onCreateOpen,
  onCreateClose,
}: {
  createOpen: boolean;
  onCreateOpen: () => void;
  onCreateClose: () => void;
}) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const canManage = isAdminRole(user?.role);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Announcement | null>(null);

  const headers = useMemo(() => authHeaders(user), [user]);

  const loadAnnouncements = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/dashboard/announcements`, { headers });
      const data = await res.json();
      setAnnouncements(data.announcements || []);
    } catch {
      setAnnouncements([]);
    } finally {
      setLoading(false);
    }
  }, [canManage, headers]);

  useEffect(() => {
    loadAnnouncements();
  }, [loadAnnouncements]);

  useEffect(() => {
    if (canManage || announcements.length === 0) return;
    announcements
      .filter((announcement) => !announcement.requires_acknowledgment && !announcement.read)
      .slice(0, 5)
      .forEach((announcement) => {
        fetch(`${API_BASE}/announcements/${announcement.id}/read`, { method: 'POST', headers }).catch(() => {});
      });
  }, [announcements, canManage, headers]);

  const acknowledge = async (announcement: Announcement) => {
    try {
      const res = await fetch(`${API_BASE}/announcements/${announcement.id}/acknowledge`, {
        method: 'POST',
        headers,
      });
      if (!res.ok) throw new Error();
      setAnnouncements((current) => current.map((item) => item.id === announcement.id ? { ...item, acknowledged: true } : item));
      showToast({ message: 'Announcement acknowledged' });
    } catch {
      showToast({ message: 'Unable to acknowledge announcement' });
    }
  };

  const remove = async (announcement: Announcement) => {
    try {
      const res = await fetch(`${API_BASE}/announcements/${announcement.id}`, {
        method: 'DELETE',
        headers,
      });
      if (!res.ok) throw new Error();
      setAnnouncements((current) => current.filter((item) => item.id !== announcement.id));
      showToast({ message: 'Announcement deleted' });
    } catch {
      showToast({ message: 'Unable to delete announcement' });
    }
  };

  const criticalPinned = announcements.find((announcement) => announcement.is_pinned && announcement.priority === 'critical' && announcement.status === 'published');

  return (
    <>
      {criticalPinned && (
        <div className="mb-4 rounded-xl border border-status-error/20 bg-status-error/5 px-4 py-3 flex items-start gap-3">
          <AlertTriangle size={18} className="text-status-error mt-0.5 shrink-0" />
          <div className="min-w-0">
            <div className="text-[13px] font-bold text-status-error">{criticalPinned.title}</div>
            <div className="text-[13px] text-[#2F3437] truncate">{criticalPinned.message}</div>
          </div>
        </div>
      )}

      <Card>
        <CardHeader
          title="Announcements"
          icon={<Megaphone size={15} />}
          action={canManage ? <button className="text-[12px] font-semibold text-olive hover:text-olive-dark">View All Announcements</button> : undefined}
        />
        <div className="p-4">
          {loading ? (
            <div className="py-5 text-center text-sm text-gray-400">Loading announcements...</div>
          ) : announcements.length === 0 ? (
            <div className="flex items-center justify-between gap-4 rounded-xl border border-dashed border-[#D6D8CF] bg-warm-bg px-4 py-4">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-olive/10 text-olive">
                  <Megaphone size={18} />
                </div>
                <div className="min-w-0">
                  <div className="text-[14px] font-bold text-[#2F3437]">No active announcements</div>
                  <div className="text-[12.5px] text-gray-500">Create company-wide updates, alerts, and employee communications.</div>
                </div>
              </div>
              {canManage && <Button size="sm" variant="soft" onClick={onCreateOpen}>Create Announcement</Button>}
            </div>
          ) : (
            <div className="space-y-2">
              {announcements.slice(0, 5).map((announcement) => (
                <div key={announcement.id} className={cn(
                  'rounded-xl border bg-warm-bg px-4 py-3 transition-colors',
                  announcement.is_pinned ? 'border-olive/30' : 'border-[#E5E7EB]'
                )}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        {announcement.is_pinned && <Pin size={13} className="text-olive shrink-0" />}
                        <h3 className="text-[14px] font-bold text-[#2F3437] truncate">{announcement.title}</h3>
                      </div>
                      <p className="text-[13px] text-gray-500 line-clamp-2">{announcement.message}</p>
                    </div>
                    {canManage && (
                      <div className="flex items-center gap-1 shrink-0">
                        {announcement.status !== 'expired' && (
                          <button onClick={() => setEditing(announcement)} className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:bg-warm-card hover:text-olive">
                            <Edit3 size={13} />
                          </button>
                        )}
                        <button onClick={() => remove(announcement)} className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:bg-status-error/10 hover:text-status-error">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2 mt-3">
                    <Badge variant="info">{titleCase(announcement.announcement_type || '')}</Badge>
                    <Badge variant={priorityVariant(announcement.priority || '')}>{titleCase(announcement.priority || '')}</Badge>
                    {canManage && <Badge variant={statusVariant(announcement.status || '')}>{titleCase(announcement.status || '')}</Badge>}
                    {announcement.is_pinned && <Badge variant="olive">Pinned</Badge>}
                  </div>
                  <div className="mt-3 grid grid-cols-1 gap-1 text-[12px] text-gray-400 sm:grid-cols-2">
                    <span>By {announcement.created_by || 'Unknown'}</span>
                    <span>{formatDate(announcement.created_at)}</span>
                    {announcement.expires_at && <span>Expires {formatDate(announcement.expires_at)}</span>}
                    {canManage && <span>Audience: {titleCase(announcement.audience_type || '')}</span>}
                  </div>
                  {canManage && announcement.requires_acknowledgment && (
                    <div className="mt-3 h-2 rounded-full bg-warm-card overflow-hidden">
                      <div className="h-full bg-olive" style={{ width: `${announcement.acknowledgment_percentage || 0}%` }} />
                    </div>
                  )}
                  {canManage && announcement.requires_acknowledgment && (
                    <div className="mt-1 text-[11px] text-gray-400">
                      {announcement.acknowledged_count || 0} acknowledged · {announcement.pending_count || 0} pending
                    </div>
                  )}
                  {!canManage && announcement.requires_acknowledgment && (
                    <div className="mt-4">
                      {announcement.acknowledged ? (
                        <Badge variant="success">Acknowledged</Badge>
                      ) : (
                        <Button size="sm" icon={<CheckCircle size={13} />} onClick={() => acknowledge(announcement)}>
                          Acknowledge
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              ))}
              {announcements.length > 5 && (
                <button className="pt-1 text-[12px] font-semibold text-olive hover:text-olive-dark">View All Announcements</button>
              )}
            </div>
          )}
        </div>
      </Card>

      <CreateAnnouncementDrawer
        open={createOpen || !!editing}
        onClose={() => {
          setEditing(null);
          onCreateClose();
        }}
        onSaved={loadAnnouncements}
        editing={editing}
      />
    </>
  );
}

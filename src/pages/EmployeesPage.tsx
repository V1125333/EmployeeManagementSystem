import { useState, useEffect, useCallback, useMemo, useRef, type DragEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Search, Filter, UserPlus, Download, ChevronDown, ChevronLeft, ChevronRight,
  Mail, Phone, MapPin, Calendar, Briefcase, Building2, User, Shield, X,
  Pencil, Loader2, Plane, KeyRound, History, CheckCircle2, Bell, RotateCcw, Copy, Award, Network,
  Upload, AlertCircle, UsersRound,
} from 'lucide-react';
import { Card, CardHeader, Badge, Button, Avatar } from '@/components/ui';
import { Drawer } from '@/components/ui/Drawer';
import { AddEmployeeDrawer } from '@/components/dashboard/AddEmployeeDrawer';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { CareerProfilePanel } from '@/components/career/CareerProfilePanel';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// ─── Types ───
interface EmployeeRecord {
  id: string;
  first_name: string;
  last_name: string;
  work_email: string;
  phone: string;
  country_code?: string | null;
  department: string;
  designation: string | null;
  role: string;
  workforce_type: string;
  employment_status: string;
  work_location: string;
  work_city?: string | null;
  work_state?: string | null;
  work_country?: string | null;
  joining_date: string | null;
  reporting_manager: string;
  project_status?: 'in_project' | 'bench' | 'trainee';
  profile_image_url: string | null;
  workforce_status?: string;
  access_level?: string;
  mfa_enabled?: boolean;
  device_assigned?: boolean;
  last_login_at?: string | null;
  last_active_at?: string | null;
  is_active: boolean;
  is_first_login: boolean;
  setup_code: string | null;
  created_at: string;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  emergency_contact_relation?: string | null;
}

interface EmployeeListResponse {
  employees: EmployeeRecord[];
  total: number;
  organization_total?: number;
  page: number;
  per_page: number;
  total_pages: number;
  reporting_manager_options?: string[];
  stats?: {
    total: number;
    active: number;
    bench: number;
    in_project: number;
    trainees: number;
  };
}

interface BulkValidationRow {
  row: number;
  name: string;
  email: string;
  department: string;
  valid: boolean;
  error: string | null;
  errors: string[];
}

interface EmployeePreview {
  employee: EmployeeRecord & {
    personal_email?: string | null;
    workforce_status?: string;
    last_login_at?: string | null;
    last_active_at?: string | null;
    access_level?: string;
    mfa_enabled?: boolean;
    device_assigned?: boolean;
    last_updated_at?: string | null;
    updated_by?: string | null;
  };
  account_activation?: {
    account_status: string;
    activation_code: string | null;
    invite_status: string;
  };
  workforce_status: {
    employment_status: string;
    availability: string | null;
    allocation_status: string | null;
    employment_type: string;
    active_allocations: number;
  };
  last_activity: {
    last_login_at: string | null;
    last_active_at: string | null;
    last_active_status: string;
    days_inactive: number | null;
  };
  leave_summary: {
    available_leave_days: number | null;
    current_leave_status: string;
    upcoming_leave_start: string | null;
    upcoming_leave_end: string | null;
    upcoming_leave_status: string | null;
  };
  learning_progress: {
    completed_courses: number;
    total_courses: number;
    completion_percentage: number;
  };
  performance_snapshot: {
    latest_rating: number | null;
    last_review_date: string | null;
    kpi_score: number | null;
  };
  it_access: {
    access_level: string | null;
    mfa_enabled: boolean | null;
    mfa_status?: string | null;
    assigned_systems_count: number | null;
    last_login_at: string | null;
    device_tracking_available?: boolean;
    device_assigned: boolean | null;
  };
  audit_changes: Array<{
    id: string;
    action_type: string;
    field_name: string;
    old_value: string | null;
    new_value: string | null;
    changed_by: string;
    changed_at: string;
  }>;
}

// ─── Filter Options ───
const DEPARTMENTS = ['All', 'Engineering', 'Product', 'Design', 'Marketing', 'Sales', 'Operations', 'People', 'Finance'];
const STATUSES = ['All', 'active', 'inactive', 'onboarding', 'offboarding'];
const ROLES = ['All', 'super_admin', 'hr_admin', 'manager', 'employee', 'trainee'];
const WORK_ARRANGEMENTS = ['All', 'Remote', 'Hybrid', 'Office', 'Onshore', 'Offshore'];
const PROJECT_STATUSES = ['All', 'In Project', 'Bench', 'Trainee'];
const WORKFORCE_TYPES = ['Full-Time Employee', 'Paid Intern', 'Unpaid Intern', 'Trainee', 'Guest'];
const DESIGNATIONS = [
  'AI Developer',
  'Backend Engineer',
  'Frontend Engineer',
  'Full Stack Engineer',
  'Data Engineer',
  'Data Analyst',
  'ML Engineer',
  'Product Manager',
  'Product Designer',
  'People Operations Associate',
  'Sales Executive',
];

// ─── Status Badge ───
const statusVariant: Record<string, 'olive' | 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  active: 'success',
  inactive: 'neutral',
  onboarding: 'info',
  offboarding: 'warning',
};

const projectStatusPresentation: Record<string, { label: string; variant: 'success' | 'warning' | 'info' | 'neutral' }> = {
  in_project: { label: 'In Project', variant: 'success' },
  bench: { label: 'Bench', variant: 'warning' },
  trainee: { label: 'Trainee', variant: 'info' },
};

const roleLabels: Record<string, string> = {
  super_admin: 'Super Admin',
  hr_admin: 'HR Admin',
  manager: 'Manager',
  employee: 'Employee',
  trainee: 'Trainee',
};

function employeeWorkLocation(employee: Pick<EmployeeRecord, 'work_city' | 'work_state' | 'work_country'>) {
  return [employee.work_city?.trim(), employee.work_state?.trim()].filter(Boolean).join(', ')
    || employee.work_country?.trim()
    || 'Not recorded';
}

function FilterDropdown({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1.5 rounded-[9px] border bg-[#faf8f3] px-4 py-[9px] text-[12px] font-semibold transition-colors',
          value !== 'All'
            ? 'border-[#d97a34]/30 text-[#b8611f]'
            : 'border-[#ece5d8] text-[#1f2430] hover:border-[#d97a34]/40'
        )}
      >
        {label}: {value === 'All' ? 'All' : value}
        <ChevronDown size={12} className={cn('transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 z-20 bg-warm-card border border-[var(--color-border)] rounded-xl shadow-card-md py-1 min-w-[160px]">
            {options.map((opt) => (
              <button
                key={opt}
                onClick={() => { onChange(opt); setOpen(false); }}
                className={cn(
                  'w-full text-left px-4 py-2 text-[13px] font-medium transition-colors',
                  opt === value ? 'bg-hover-bg text-olive' : 'text-[var(--color-brand-navy)] hover:bg-hover-bg'
                )}
              >
                {opt === 'All' ? `All ${label}s` : opt}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Employee Detail Drawer ───
function EmployeeDetail({
  employee,
  open,
  onClose,
  onEdit,
}: {
  employee: EmployeeRecord | null;
  open: boolean;
  onClose: () => void;
  onEdit: (employee: EmployeeRecord) => void;
}) {
  if (!employee) return null;

  const initials = `${employee.first_name[0]}${employee.last_name[0]}`.toUpperCase();
  const fullName = `${employee.first_name} ${employee.last_name}`;

  const InfoRow = ({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | null }) => (
    <div className="flex items-start gap-3 py-2.5">
      <span className="text-gray-400 mt-0.5 shrink-0">{icon}</span>
      <div>
        <div className="text-[11px] text-gray-400 font-medium uppercase tracking-wider">{label}</div>
        <div className="text-[14px] text-[var(--color-brand-navy)] font-medium">{value || '—'}</div>
      </div>
    </div>
  );

  return (
    <Drawer open={open} onClose={onClose} title={fullName} subtitle={employee.work_email} width="w-[480px]">
      {/* Profile header */}
      <div className="flex items-center gap-4 mb-6 pb-6 border-b border-[var(--color-border)]">
        <div className="w-16 h-16 rounded-2xl bg-olive flex items-center justify-center text-white text-xl font-bold">
          {initials}
        </div>
        <div>
          <div className="text-lg font-bold text-[var(--color-brand-navy)]">{fullName}</div>
          <div className="text-[13px] text-gray-500">{employee.designation || employee.role}</div>
          <div className="flex gap-2 mt-2">
            <Badge variant={statusVariant[employee.employment_status] || 'neutral'}>
              {employee.employment_status}
            </Badge>
            {employee.is_first_login && (
              <Badge variant="warning">Setup pending</Badge>
            )}
            {employee.setup_code && (
              <Badge variant="olive">{employee.setup_code}</Badge>
            )}
          </div>
        </div>
      </div>

      <Button
        variant="ghost"
        icon={<Pencil size={14} />}
        onClick={() => onEdit(employee)}
        className="mb-6"
      >
        Edit Employee
      </Button>

      {/* Contact */}
      <div className="text-[11px] font-bold text-gray-400 tracking-widest uppercase mb-3">Contact</div>
      <InfoRow icon={<Mail size={15} />} label="Email" value={employee.work_email} />
      <InfoRow icon={<Phone size={15} />} label="Phone" value={employee.phone} />

      <div className="h-px bg-[var(--color-border)] my-4" />

      {/* Employment */}
      <div className="text-[11px] font-bold text-gray-400 tracking-widest uppercase mb-3">Employment</div>
      <InfoRow icon={<Building2 size={15} />} label="Department" value={employee.department} />
      <InfoRow icon={<Briefcase size={15} />} label="Designation" value={employee.designation} />
      <InfoRow icon={<Shield size={15} />} label="Role" value={roleLabels[employee.role] || employee.role} />
      <InfoRow icon={<User size={15} />} label="Workforce Type" value={employee.workforce_type} />
      <InfoRow icon={<User size={15} />} label="Reporting Manager" value={employee.reporting_manager} />
      <InfoRow icon={<MapPin size={15} />} label="Work Arrangement" value={employee.work_location} />
      <InfoRow icon={<MapPin size={15} />} label="Work Location" value={employeeWorkLocation(employee)} />
      <InfoRow icon={<Calendar size={15} />} label="Joining Date" value={employee.joining_date} />
    </Drawer>
  );
}

// ─── Main Page ───
function ExecutiveEmployeeDetail({
  employee,
  open,
  onClose,
  onEdit,
  refreshKey,
}: {
  employee: EmployeeRecord | null;
  open: boolean;
  onClose: () => void;
  onEdit: (employee: EmployeeRecord) => void;
  refreshKey: number;
}) {
  const [preview, setPreview] = useState<EmployeePreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    account: true,
    contact: true,
    emergency: true,
    employment: true,
    career: false,
    access: true,
    leave: true,
    audit: true,
  });
  const { showToast } = useToast();
  const { user } = useAuth();
  const [sendingEmergencyReminder, setSendingEmergencyReminder] = useState(false);
  const [resettingPassword, setResettingPassword] = useState(false);
  const [temporaryPassword, setTemporaryPassword] = useState('');
  const [passwordResetModalOpen, setPasswordResetModalOpen] = useState(false);
  const [passwordResetReason, setPasswordResetReason] = useState('');

  useEffect(() => {
    if (!open || !employee) return;
    setLoadingPreview(true);
    setPreviewError('');
    setTemporaryPassword('');
    fetch(`${API_BASE}/employees/${employee.id}/preview`, {
      headers: {
        'x-user-id': user?.id || '',
        'x-user-email': user?.email || '',
      },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error('Preview data is not available');
        const data = await res.json();
        if (!data?.employee) throw new Error('Preview data is incomplete');
        setPreview(data);
      })
      .catch((err) => {
        setPreview(null);
        setPreviewError(err instanceof Error ? err.message : 'Preview data is not available');
      })
      .finally(() => setLoadingPreview(false));
  }, [open, employee, refreshKey, user?.email, user?.id]);

  if (!employee) return null;

  const data = preview?.employee || employee;
  const initials = `${data.first_name[0]}${data.last_name[0]}`.toUpperCase();
  const fullName = `${data.first_name} ${data.last_name}`;
  const auditChanges = preview?.audit_changes || [];
  const accountStatus = preview?.account_activation?.account_status || (data.is_first_login ? 'pending_activation' : (data.is_active ? 'active' : 'inactive'));
  const activationCode = preview?.account_activation?.activation_code || (data.is_first_login ? data.setup_code : null);
  const inviteStatus = preview?.account_activation?.invite_status || (data.is_first_login ? 'pending' : 'accepted');
  const accessRole = preview?.it_access?.access_level || data.role;
  const currentRole = (user?.role || '').toLowerCase().replace(/\s+/g, '_');
  const canResetPassword = ['super_admin', 'hr_admin', 'admin'].includes(currentRole) && user?.id !== data.id;
  const hasEmergencyDetails = Boolean(
    data.emergency_contact_name?.trim()
    || data.emergency_contact_phone?.trim()
    || data.emergency_contact_relation?.trim()
  );

  const formatDate = (value?: string | null) => value
    ? new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : 'Not recorded';
  const formatDateTime = (value?: string | null) => value
    ? new Date(value).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
    : 'Not recorded';
  const titleCase = (value?: string | null) => value
    ? value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
    : 'Not recorded';
  const formatRole = (value?: string | null) => value ? (roleLabels[value] || titleCase(value)) : 'Not available';
  const formatPhone = (countryCode?: string | null, phone?: string | null) => {
    if (!phone) return 'Not recorded';
    return [countryCode?.trim(), phone.trim()].filter(Boolean).join(' ');
  };
  const mfaLabel = (status?: string | null, enabled?: boolean | null) => {
    if (enabled === true || status === 'enabled') return 'Enabled';
    if (status === 'pending_setup') return 'Pending setup';
    return 'Not available';
  };
  const toggleSection = (key: string) => setOpenSections((current) => ({ ...current, [key]: !current[key] }));
  const sendEmergencyReminder = async () => {
    setSendingEmergencyReminder(true);
    try {
      const res = await fetch(`${API_BASE}/employees/${data.id}/remind-emergency-contact`, {
        method: 'POST',
        headers: {
          'x-user-id': user?.id || '',
          'x-user-email': user?.email || '',
        },
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok || result.success === false) {
        throw new Error(result.detail || result.message || 'Unable to send reminder.');
      }
      showToast({ message: 'Reminder sent to employee.' });
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Unable to send reminder.' });
    } finally {
      setSendingEmergencyReminder(false);
    }
  };
  const handleAdminResetPassword = async () => {
    const reason = passwordResetReason.trim();
    if (reason.length < 3) {
      showToast({ message: 'Reset reason must be at least 3 characters.' });
      return;
    }
    setResettingPassword(true);
    try {
      const res = await fetch(`${API_BASE}/auth/admin-reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-user-id': user?.id || '',
          'x-user-email': user?.email || '',
        },
        body: JSON.stringify({ employee_id: data.id, reason }),
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok || result.success === false) {
        throw new Error(result.detail || result.message || 'Unable to reset password.');
      }
      setTemporaryPassword(result.temporary_password || '');
      setPasswordResetModalOpen(false);
      setPasswordResetReason('');
      showToast({ message: 'Temporary password generated.' });
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Unable to reset password.' });
    } finally {
      setResettingPassword(false);
    }
  };
  const copyTemporaryPassword = async () => {
    if (!temporaryPassword) return;
    await navigator.clipboard.writeText(temporaryPassword);
    showToast({ message: 'Temporary password copied.' });
  };

  const openPasswordResetModal = () => {
    setTemporaryPassword('');
    setPasswordResetReason(`Admin temporary password issued for ${fullName}`);
    setPasswordResetModalOpen(true);
  };

  const Metric = ({ label, value, tone = 'neutral' }: { label: string; value: string | number; tone?: 'neutral' | 'good' | 'warn' | 'bad' }) => (
    <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-2.5">
      <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{label}</div>
      <div className={cn(
        'mt-1 text-[14px] font-semibold',
        tone === 'good' && 'text-status-success',
        tone === 'warn' && 'text-status-warning',
        tone === 'bad' && 'text-status-error',
        tone === 'neutral' && 'text-[var(--color-brand-navy)]'
      )}>
        {value}
      </div>
    </div>
  );

  const Panel = ({ id, title, icon, children }: { id: string; title: string; icon: React.ReactNode; children: React.ReactNode }) => (
    <div className="border border-[var(--color-border)] rounded-xl bg-warm-card overflow-hidden">
      <button onClick={() => toggleSection(id)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-hover-bg transition-colors">
        <span className="flex items-center gap-2 text-[13px] font-bold text-[var(--color-brand-navy)]">
          <span className="text-olive">{icon}</span>
          {title}
        </span>
        <ChevronDown size={15} className={cn('text-gray-400 transition-transform', openSections[id] && 'rotate-180')} />
      </button>
      {openSections[id] && <div className="px-4 pb-4">{children}</div>}
    </div>
  );

  return (
    <Drawer open={open} onClose={onClose} title="Employee Snapshot" width="w-[620px]">
      <div className="space-y-4">
        <div className="rounded-xl border border-[var(--color-border)] bg-warm-card p-4">
          <div className="flex items-start gap-4">
            <Avatar initials={initials} size="lg" variant={data.is_active ? 'filled' : 'soft'} src={data.profile_image_url} />
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-lg font-bold text-[var(--color-brand-navy)] truncate">{fullName}</div>
                  <div className="text-[13px] text-gray-500 truncate">{data.designation || roleLabels[data.role] || data.role} · {data.department || 'No department'}</div>
                </div>
                <Button variant="ghost" size="sm" icon={<Pencil size={13} />} onClick={() => onEdit(employee)}>Edit</Button>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                <Badge variant={statusVariant[data.employment_status] || 'neutral'}>{titleCase(data.employment_status)}</Badge>
                {preview?.workforce_status?.availability && (
                  <Badge variant="olive">{titleCase(preview.workforce_status.availability)}</Badge>
                )}
                {data.is_first_login && <Badge variant="warning">Pending Activation</Badge>}
                <Badge variant="neutral">ID: {data.id.slice(0, 8)}</Badge>
              </div>
              <div className="grid grid-cols-1 gap-2 mt-4 text-[12.5px] text-gray-500 sm:grid-cols-2">
                <div className="flex items-center gap-2 min-w-0"><Mail size={14} className="text-gray-400 shrink-0" /><span className="truncate">{data.work_email}</span></div>
                <div className="flex items-center gap-2"><Phone size={14} className="text-gray-400 shrink-0" />{formatPhone(data.country_code, data.phone)}</div>
                <div className="flex items-center gap-2"><MapPin size={14} className="text-gray-400 shrink-0" />{employeeWorkLocation(data)}</div>
                <div className="flex items-center gap-2 min-w-0"><User size={14} className="text-gray-400 shrink-0" /><span className="truncate">{data.reporting_manager || 'No manager'}</span></div>
              </div>
            </div>
          </div>
        </div>

        {loadingPreview ? (
          <div className="flex items-center justify-center py-8 text-sm text-gray-400">
            <Loader2 size={16} className="animate-spin mr-2" />
            Loading employee preview...
          </div>
        ) : (
          <>
            <Panel id="account" title="Account & Activation" icon={<CheckCircle2 size={15} />}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Metric
                  label="Account Status"
                  value={accountStatus === 'pending_activation' ? 'Pending Activation' : titleCase(accountStatus)}
                  tone={accountStatus === 'active' ? 'good' : accountStatus === 'pending_activation' ? 'warn' : 'bad'}
                />
                <Metric label="Invite Status" value={titleCase(inviteStatus)} />
                {activationCode && <Metric label="Activation Code" value={activationCode} />}
                <Metric label="Member Since" value={formatDate(data.created_at)} />
              </div>
              {accountStatus === 'pending_activation' && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled
                  className="mt-3 opacity-60 cursor-not-allowed"
                >
                  Resend Invite
                </Button>
              )}
            </Panel>

            <Panel id="contact" title="Contact" icon={<Phone size={15} />}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Metric label="Work Email" value={data.work_email || 'Not recorded'} />
                <Metric label="Phone" value={formatPhone(data.country_code, data.phone)} />
                <Metric label="Work Arrangement" value={data.work_location || 'Not recorded'} />
                <Metric label="Work Location" value={employeeWorkLocation(data)} />
              </div>
            </Panel>

            <Panel id="emergency" title="Emergency Contact" icon={<Bell size={15} />}>
              {hasEmergencyDetails ? (
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Metric label="Contact Name" value={data.emergency_contact_name || 'Not recorded'} />
                  <Metric label="Contact Phone" value={data.emergency_contact_phone || 'Not recorded'} />
                  <Metric label="Relationship" value={data.emergency_contact_relation || 'Not recorded'} />
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-warm-bg px-4 py-4">
                  <div className="text-[14px] font-semibold text-[var(--color-brand-navy)]">No details provided</div>
                  <div className="mt-1 text-[12.5px] text-gray-500">
                    Ask the employee to add emergency contact details in My Profile.
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={sendingEmergencyReminder ? <Loader2 size={13} className="animate-spin" /> : <Bell size={13} />}
                    className="mt-3"
                    disabled={sendingEmergencyReminder || !data.is_active}
                    onClick={sendEmergencyReminder}
                  >
                    {sendingEmergencyReminder ? 'Sending' : 'Send Reminder'}
                  </Button>
                </div>
              )}
            </Panel>

            <Panel id="employment" title="Employment" icon={<Briefcase size={15} />}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Metric label="Department" value={data.department || 'Not recorded'} />
                <Metric label="Designation" value={data.designation || 'Not recorded'} />
                <Metric label="Role" value={formatRole(data.role)} />
                <Metric label="Manager" value={data.reporting_manager || 'Not recorded'} />
                <Metric label="Employment Type" value={data.workforce_type || 'Not recorded'} />
                <Metric label="Joining Date" value={formatDate(data.joining_date)} />
                <Metric label="Allocation" value={preview?.workforce_status?.allocation_status ? titleCase(preview.workforce_status.allocation_status) : 'No data recorded'} />
                <Metric label="Availability" value={preview?.workforce_status?.availability ? titleCase(preview.workforce_status.availability) : 'No data recorded'} />
              </div>
            </Panel>

            <Panel id="career" title="Career Profile" icon={<Award size={15} />}>
              <CareerProfilePanel
                employee={{
                  id: data.id,
                  name: fullName,
                  email: data.work_email,
                  designation: data.designation,
                  department: data.department,
                }}
                editable={false}
              />
            </Panel>

            <Panel id="access" title="Access & Security" icon={<KeyRound size={15} />}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Metric label="Access Role" value={formatRole(accessRole)} />
                <Metric label="MFA" value={mfaLabel(preview?.it_access?.mfa_status, preview?.it_access?.mfa_enabled)} tone={preview?.it_access?.mfa_status === 'enabled' ? 'good' : 'neutral'} />
                <Metric label="Last Login" value={formatDateTime(preview?.last_activity?.last_login_at || data.last_login_at)} />
                <Metric label="Last Active" value={formatDateTime(preview?.last_activity?.last_active_at || data.last_active_at)} />
                {preview?.it_access?.assigned_systems_count !== null && preview?.it_access?.assigned_systems_count !== undefined && (
                  <Metric label="Assigned Systems" value={preview.it_access.assigned_systems_count} />
                )}
                {preview?.it_access?.device_tracking_available && (
                  <Metric label="Device Assigned" value={preview.it_access.device_assigned ? 'Assigned' : 'Not assigned'} />
                )}
              </div>
              {canResetPassword && (
                <div className="mt-3 rounded-xl border border-[var(--color-border)] bg-warm-bg p-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-[13px] font-semibold text-[var(--color-brand-navy)]">Password recovery</div>
                      <div className="mt-0.5 text-[12px] text-gray-500">Generate a temporary password and require a change on next login.</div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={resettingPassword ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
                      disabled={resettingPassword}
                      onClick={openPasswordResetModal}
                    >
                      Generate Password
                    </Button>
                  </div>
                  {temporaryPassword && (
                    <div className="mt-3 flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-white px-3 py-2">
                      <code className="min-w-0 flex-1 select-all truncate text-[13px] font-bold text-[var(--color-brand-navy)]">{temporaryPassword}</code>
                      <button
                        type="button"
                        onClick={copyTemporaryPassword}
                        className="rounded-lg p-2 text-olive transition-colors hover:bg-olive/10"
                        aria-label="Copy temporary password"
                      >
                        <Copy size={14} />
                      </button>
                    </div>
                  )}
                </div>
              )}
            </Panel>

            <Panel id="leave" title="Leave Summary" icon={<Plane size={15} />}>
              <div className="grid grid-cols-2 gap-2">
                <Metric
                  label="Available Leave"
                  value={preview?.leave_summary?.available_leave_days !== null && preview?.leave_summary?.available_leave_days !== undefined ? `${preview.leave_summary.available_leave_days} days` : 'No data recorded'}
                />
                <Metric
                  label="Current Status"
                  value={preview?.leave_summary?.current_leave_status ? titleCase(preview.leave_summary.current_leave_status) : 'No data recorded'}
                  tone={preview?.leave_summary?.current_leave_status === 'on_leave' ? 'warn' : 'neutral'}
                />
              </div>
              <div className="mt-3 rounded-xl bg-warm-bg border border-[var(--color-border)] px-3 py-2.5 text-[12.5px] text-gray-500">
                {preview?.leave_summary?.upcoming_leave_start
                  ? `Upcoming: ${formatDate(preview.leave_summary.upcoming_leave_start)} - ${formatDate(preview.leave_summary.upcoming_leave_end)} (${titleCase(preview.leave_summary.upcoming_leave_status)})`
                  : previewError ? 'No leave data available' : 'No leave scheduled'}
              </div>
            </Panel>

            <Panel id="audit" title="Audit History" icon={<History size={15} />}>
              {auditChanges.length > 0 ? (
                <div className="space-y-2">
                  {auditChanges.map((change) => (
                    <div key={change.id} className="rounded-xl bg-warm-bg border border-[var(--color-border)] px-3 py-2.5">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-[13px] font-semibold text-[var(--color-brand-navy)]">{titleCase(change.field_name)} updated</div>
                        <div className="text-[11px] text-gray-400 shrink-0">{formatDate(change.changed_at)}</div>
                      </div>
                      <div className="mt-1 text-[12px] text-gray-500">{change.old_value || 'Empty'} to {change.new_value || 'Empty'}</div>
                      <div className="mt-1 text-[11px] text-gray-400">By {change.changed_by}</div>
                    </div>
                  ))}
                  <button className="text-[12px] font-semibold text-olive hover:text-olive-dark transition-colors">View All</button>
                </div>
              ) : <div className="rounded-xl bg-warm-bg border border-[var(--color-border)] px-3 py-3 text-[13px] text-gray-400">No recent audit changes</div>}
            </Panel>
          </>
        )}
      </div>
      {passwordResetModalOpen && (
        <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/45 px-4">
          <div className="w-full max-w-[520px] overflow-hidden rounded-2xl border border-[var(--color-border)] bg-white shadow-[0_28px_90px_rgba(17,24,39,0.24)]">
            <div className="flex items-start justify-between border-b border-[var(--color-border)] px-6 py-5">
              <div>
                <div className="text-lg font-bold text-[var(--color-brand-navy)]">Generate temporary password</div>
                <div className="mt-1 text-sm text-gray-500">{fullName} · {data.work_email}</div>
              </div>
              <button
                type="button"
                onClick={() => !resettingPassword && setPasswordResetModalOpen(false)}
                className="rounded-lg p-1.5 text-gray-400 transition hover:bg-hover-bg hover:text-[var(--color-brand-navy)]"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <div className="space-y-4 px-6 py-5">
              <label className="block">
                <span className="mb-2 block text-[13px] font-semibold text-[var(--color-brand-navy)]">Admin reason</span>
                <textarea
                  value={passwordResetReason}
                  onChange={(event) => setPasswordResetReason(event.target.value.slice(0, 500))}
                  className="min-h-[112px] w-full resize-none rounded-xl border border-[var(--color-border)] bg-warm-bg px-3.5 py-3 text-sm font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10"
                  placeholder="Example: Employee account locked; identity verified by HR"
                  autoFocus
                />
              </label>
              <div className="rounded-xl bg-warm-bg px-4 py-3 text-xs leading-5 text-gray-500">
                This will unlock the employee account if it is locked, generate a temporary password, and force the employee to create a new password on next login.
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setPasswordResetModalOpen(false)} disabled={resettingPassword}>Cancel</Button>
                <Button
                  icon={resettingPassword ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                  onClick={handleAdminResetPassword}
                  disabled={resettingPassword}
                >
                  {resettingPassword ? 'Generating...' : 'Generate Temporary Password'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Drawer>
  );
}

interface EditFormState {
  first_name: string;
  last_name: string;
  phone: string;
  department: string;
  designation: string;
  role: string;
  workforce_type: string;
  employment_status: string;
  work_location: string;
  work_city: string;
  work_state: string;
  work_country: string;
  reporting_manager: string;
  joining_date: string;
  change_reason: string;
}

function EditEmployeeDrawer({
  employee,
  employees,
  open,
  onClose,
  onSaved,
}: {
  employee: EmployeeRecord | null;
  employees: EmployeeRecord[];
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { user } = useAuth();
  const [form, setForm] = useState<EditFormState>({
    first_name: '',
    last_name: '',
    phone: '',
    department: '',
    designation: '',
    role: '',
    workforce_type: '',
    employment_status: '',
    work_location: '',
    work_city: '',
    work_state: '',
    work_country: '',
    reporting_manager: '',
    joining_date: '',
    change_reason: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const uniqueOptions = (values: Array<string | null | undefined>) => Array.from(new Set(values.filter((value): value is string => !!value?.trim())));
  const optionWithCurrent = (options: string[], current: string) => current && !options.includes(current) ? [current, ...options] : options;
  const managerOptions = optionWithCurrent(
    ['Not assigned', ...uniqueOptions(employees
      .filter((item) => item.id !== employee?.id && ['super_admin', 'hr_admin', 'manager'].includes(item.role))
      .map((item) => `${item.first_name} ${item.last_name}`))],
    form.reporting_manager
  );
  const designationOptions = optionWithCurrent(uniqueOptions([...DESIGNATIONS, ...employees.map((item) => item.designation)]), form.designation);

  useEffect(() => {
    if (!employee) return;
    setForm({
      first_name: employee.first_name,
      last_name: employee.last_name,
      phone: employee.phone,
      department: employee.department,
      designation: employee.designation || '',
      role: employee.role,
      workforce_type: employee.workforce_type,
      employment_status: employee.employment_status,
      work_location: employee.work_location,
      work_city: employee.work_city || '',
      work_state: employee.work_state || '',
      work_country: employee.work_country || '',
      reporting_manager: employee.reporting_manager,
      joining_date: employee.joining_date || '',
      change_reason: '',
    });
    setError('');
  }, [employee]);

  const update = (key: keyof EditFormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (error) setError('');
  };

  const save = async () => {
    if (!employee) return;
    if (!form.first_name.trim() || !form.last_name.trim() || !form.phone.trim() || !form.joining_date) {
      setError('First name, last name, phone, and joining date are required.');
      return;
    }

    const employmentFields: Array<keyof EditFormState> = [
      'department', 'designation', 'role', 'workforce_type', 'employment_status',
      'work_location', 'work_city', 'work_state', 'work_country', 'reporting_manager', 'joining_date',
    ];
    const originalValues: Partial<Record<keyof EditFormState, string>> = {
      department: employee.department,
      designation: employee.designation || '',
      role: employee.role,
      workforce_type: employee.workforce_type,
      employment_status: employee.employment_status,
      work_location: employee.work_location,
      work_city: employee.work_city || '',
      work_state: employee.work_state || '',
      work_country: employee.work_country || '',
      reporting_manager: employee.reporting_manager,
      joining_date: employee.joining_date || '',
    };
    const hasEmploymentChanges = employmentFields.some((field) => form[field] !== originalValues[field]);
    if (hasEmploymentChanges && !form.change_reason.trim()) {
      setError('Enter a reason for changing employment details.');
      return;
    }

    const currentUserRole = user?.role === 'Global Access' ? 'super_admin' : user?.role || '';

    setSaving(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/employees/${employee.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'x-user-id': user?.id || '',
          'x-user-role': currentUserRole,
          'x-user-email': user?.email || '',
          'x-user-name': user?.name || '',
        },
        body: JSON.stringify({
          ...form,
          designation: form.designation || null,
          joining_date: form.joining_date || null,
          change_reason: form.change_reason.trim() || null,
        }),
      });
      const result = await res.json();

      if (!res.ok || !result.success) {
        throw new Error(result.detail || result.message || 'Unable to update employee');
      }

      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update employee');
    } finally {
      setSaving(false);
    }
  };

  const Field = ({
    label,
    value,
    onChange,
    options,
    type = 'text',
  }: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    options?: string[];
    type?: string;
  }) => (
    <div>
      <label className="block text-[13px] font-semibold text-[var(--color-brand-navy)] mb-1.5">
        {label}
      </label>
      {options ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3.5 py-2.5 rounded-xl text-[14px] font-medium bg-warm-bg border border-[var(--color-border)] text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10"
        >
          {options.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      ) : (
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3.5 py-2.5 rounded-xl text-[14px] font-medium bg-warm-bg border border-[var(--color-border)] text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10"
        />
      )}
    </div>
  );

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Edit Employee"
      subtitle={employee ? `${employee.first_name} ${employee.last_name}` : undefined}
      width="w-[560px]"
      footer={
        <div className="flex items-center justify-between gap-3">
          {error ? <div className="text-[13px] font-medium text-status-error">{error}</div> : <div />}
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl text-[13px] font-semibold text-gray-500 border border-[var(--color-border)] hover:bg-hover-bg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={save}
              disabled={saving}
              className={cn(
                'px-5 py-2.5 rounded-xl text-[13px] font-semibold text-white flex items-center gap-2 transition-all shadow-sm',
                saving ? 'bg-olive/60 cursor-not-allowed' : 'bg-olive hover:bg-olive-dark active:scale-[0.98]'
              )}
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      }
    >
      <div className="grid grid-cols-2 gap-4">
        <Field label="First Name" value={form.first_name} onChange={(v) => update('first_name', v)} />
        <Field label="Last Name" value={form.last_name} onChange={(v) => update('last_name', v)} />
        <Field label="Phone" value={form.phone} onChange={(v) => update('phone', v)} />
        <Field label="Department" value={form.department} onChange={(v) => update('department', v)} options={DEPARTMENTS.slice(1)} />
        <Field label="Designation" value={form.designation} onChange={(v) => update('designation', v)} options={designationOptions} />
        <Field label="Role" value={form.role} onChange={(v) => update('role', v)} options={optionWithCurrent(ROLES.slice(1), form.role)} />
        <Field label="Workforce Type" value={form.workforce_type} onChange={(v) => update('workforce_type', v)} options={optionWithCurrent(WORKFORCE_TYPES, form.workforce_type)} />
        <Field label="Status" value={form.employment_status} onChange={(v) => update('employment_status', v)} options={STATUSES.slice(1)} />
        <Field label="Work Arrangement" value={form.work_location} onChange={(v) => update('work_location', v)} options={optionWithCurrent(WORK_ARRANGEMENTS.slice(1), form.work_location)} />
        <Field label="Work City" value={form.work_city} onChange={(v) => update('work_city', v)} />
        <Field label="State / Province" value={form.work_state} onChange={(v) => update('work_state', v)} />
        <Field label="Work Country" value={form.work_country} onChange={(v) => update('work_country', v)} />
        <Field label="Reporting Manager" value={form.reporting_manager} onChange={(v) => update('reporting_manager', v)} options={managerOptions} />
        <Field label="Joining Date" value={form.joining_date} onChange={(v) => update('joining_date', v)} type="date" />
        <div className="col-span-2">
          <label className="mb-1.5 block text-[13px] font-semibold text-[var(--color-brand-navy)]">
            Reason for employment change
          </label>
          <textarea
            value={form.change_reason}
            onChange={(event) => update('change_reason', event.target.value)}
            rows={3}
            maxLength={500}
            placeholder="Required when changing role, department, manager, status, location, or employment dates"
            className="w-full resize-none rounded-xl border border-[var(--color-border)] bg-warm-bg px-3.5 py-2.5 text-[14px] font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10"
          />
          <div className="mt-1 text-[11px] text-gray-400">This reason is recorded in the audit trail and included in the employee notification.</div>
        </div>
      </div>
    </Drawer>
  );
}

function BulkEmployeeUploadModal({
  open,
  onClose,
  headers,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  headers: Record<string, string>;
  onImported: (count: number) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [rows, setRows] = useState<BulkValidationRow[]>([]);
  const [validating, setValidating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const uploadHeaders = useMemo(() => ({
    'x-user-id': headers['x-user-id'] || '',
    'x-user-email': headers['x-user-email'] || '',
    'x-user-name': headers['x-user-name'] || '',
  }), [headers]);

  useEffect(() => {
    if (!open) {
      setFile(null);
      setRows([]);
      setError(null);
      setDragging(false);
    }
  }, [open]);

  const validateFile = async (nextFile: File | null) => {
    if (!nextFile) return;
    setFile(nextFile);
    setRows([]);
    setError(null);
    setValidating(true);
    try {
      const formData = new FormData();
      formData.append('file', nextFile);
      const res = await fetch(`${API_BASE}/employees/bulk/validate`, { method: 'POST', headers: uploadHeaders, body: formData });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not validate the employee file.');
      setRows(data?.rows || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not validate the employee file.');
    } finally {
      setValidating(false);
    }
  };

  const downloadTemplate = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/employees/bulk-template.csv`, { headers: uploadHeaders });
      const data = !res.ok ? await res.json().catch(() => null) : null;
      if (!res.ok) throw new Error(data?.detail || 'Could not download the template.');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'orbit-employee-import-template.csv';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not download the template.');
    }
  };

  const importEmployees = async () => {
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/employees/bulk`, { method: 'POST', headers: uploadHeaders, body: formData });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || 'Could not import employees.');
      onImported(Number(data?.imported || 0));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not import employees.');
    } finally {
      setImporting(false);
    }
  };

  const validCount = rows.filter((row) => row.valid).length;
  const invalidCount = rows.length - validCount;
  if (!open) return null;

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    void validateFile(event.dataTransfer.files?.[0] || null);
  };

  return (
    <div className="fixed inset-0 z-[180] flex items-center justify-center bg-[#1f2430]/45 p-5" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="bulk-upload-title" className="max-h-[90vh] w-full max-w-[640px] overflow-y-auto rounded-[20px] border border-[#ece5d8] bg-[#f7f3ec] shadow-[0_22px_60px_rgba(31,36,48,.22)]">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-[#ece5d8] bg-[#f7f3ec] px-6 py-5">
          <div><h2 id="bulk-upload-title" className="text-[19px] font-bold text-[#1f2430]">Bulk upload employees</h2><p className="mt-1 text-[13px] text-[#8a8371]">Import many employees at once from a CSV or Excel file.</p></div>
          <button type="button" onClick={onClose} aria-label="Close bulk upload" className="grid h-8 w-8 place-items-center rounded-lg text-[#a99e8a] hover:bg-white hover:text-[#1f2430]"><X size={17} /></button>
        </div>
        <div className="space-y-4 p-6">
          <section className="flex flex-wrap items-center justify-between gap-4 rounded-[14px] border border-[#ece5d8] bg-white p-4">
            <div className="flex min-w-0 items-center gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-[11px] bg-[#e9f4ea] text-[#3f9b52]"><Download size={17} /></span><div><h3 className="text-[14px] font-bold text-[#1f2430]">1 · Download the template</h3><p className="mt-1 text-[11.5px] leading-5 text-[#8a8371]">Name, email, department, role, manager, work arrangement and join date.</p></div></div>
            <button type="button" onClick={downloadTemplate} className="rounded-[9px] border border-[#ece5d8] bg-white px-3.5 py-2 text-[12px] font-bold text-[#1f2430] hover:border-[#d97a34] hover:text-[#b8611f]">Template .csv</button>
          </section>

          <section>
            <h3 className="mb-2 text-[14px] font-bold text-[#1f2430]">2 · Upload your completed file</h3>
            <div onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={handleDrop} className={cn('flex min-h-[164px] flex-col items-center justify-center rounded-[14px] border border-dashed px-6 py-7 text-center transition-colors', dragging ? 'border-[#d97a34] bg-[#fff7ef]' : 'border-[#d8cdb8] bg-[#fdfbf7]')}>
              <span className="mb-3 grid h-11 w-11 place-items-center rounded-[12px] bg-[#fbeee1] text-[#d97a34]"><Upload size={19} /></span>
              <div className="text-[14px] font-bold text-[#1f2430]">{validating ? 'Validating file…' : file ? file.name : 'Drop CSV or Excel here, or browse'}</div>
              <div className="mt-1 text-[11.5px] text-[#a99e8a]">Up to 500 rows · .csv, .xlsx</div>
              <button type="button" disabled={validating} onClick={() => fileInputRef.current?.click()} className="mt-4 rounded-[9px] border border-[#d97a34] bg-white px-4 py-2 text-[12px] font-bold text-[#b8611f] hover:bg-[#fff7ef] disabled:opacity-50">{file ? 'Replace file' : 'Browse files'}</button>
              <input ref={fileInputRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={(event) => void validateFile(event.target.files?.[0] || null)} />
            </div>
          </section>

          {(rows.length > 0 || validating) && <section className="overflow-hidden rounded-[14px] border border-[#ece5d8] bg-white">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#f0e7d8] px-4 py-3"><h3 className="text-[14px] font-bold text-[#1f2430]">3 · Review — {validCount} ready, {invalidCount} need fixes</h3><span className="text-[11px] text-[#a99e8a]">{file?.name} · {rows.length} rows</span></div>
            <div className="max-h-[250px] overflow-auto">
              <div className="grid min-w-[520px] grid-cols-[36px_1.4fr_1fr_110px] gap-3 bg-[#fdfbf7] px-4 py-2 text-[10px] font-bold uppercase tracking-wide text-[#a99e8a]"><div>Row</div><div>Name</div><div>Department</div><div>Status</div></div>
              {rows.map((row) => <div key={row.row} className="grid min-w-[520px] grid-cols-[36px_1.4fr_1fr_110px] items-center gap-3 border-t border-[#f6f0e6] px-4 py-2.5 text-[12px]"><div className="text-[#a99e8a]">{row.row}</div><div className="min-w-0"><div className="truncate font-semibold text-[#1f2430]">{row.name}</div><div className="truncate text-[11px] text-[#a99e8a]">{row.email || 'Email missing'}</div></div><div className="truncate text-[#8a8371]">{row.department || '—'}</div><div><span className={cn('inline-flex max-w-full rounded-full px-2.5 py-1 text-[10px] font-bold', row.valid ? 'bg-[#e9f4ea] text-[#3f9b52]' : 'bg-[#fbe9e4] text-[#c0503a]')} title={row.errors.join(', ')}>{row.valid ? 'Ready' : row.error}</span></div></div>)}
            </div>
          </section>}

          {error && <div className="flex items-start gap-2 rounded-xl border border-[#e9b6aa] bg-[#fbe9e4] px-4 py-3 text-[12px] text-[#c0503a]"><AlertCircle size={15} className="mt-0.5 shrink-0" />{error}</div>}
        </div>
        <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-4 border-t border-[#ece5d8] bg-[#f7f3ec] px-6 py-4">
          <p className="max-w-[330px] text-[11px] leading-5 text-[#8a8371]">Only valid rows will be imported. Fix errors and re-upload for the rest.</p>
          <div className="flex gap-2"><button type="button" onClick={onClose} className="rounded-[10px] border border-[#ece5d8] bg-white px-4 py-2.5 text-[12px] font-bold text-[#1f2430]">Cancel</button><button type="button" disabled={validCount < 1 || importing} onClick={importEmployees} className="rounded-[10px] bg-[#2b3243] px-4 py-2.5 text-[12px] font-bold text-white shadow-[0_3px_10px_rgba(43,50,67,.2)] disabled:cursor-not-allowed disabled:opacity-45">{importing ? 'Importing…' : `Import ${validCount} employees`}</button></div>
        </div>
      </div>
    </div>
  );
}

export function EmployeesPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSearch = searchParams.get('search') || '';
  const [employees, setEmployees] = useState<EmployeeRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [organizationTotal, setOrganizationTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(initialSearch);
  const [deptFilter, setDeptFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [roleFilter, setRoleFilter] = useState('All');
  const [locationFilter, setLocationFilter] = useState('All');
  const [projectStatusFilter, setProjectStatusFilter] = useState('All');
  const [reportingManagerFilter, setReportingManagerFilter] = useState('All');
  const [reportingManagerOptions, setReportingManagerOptions] = useState<string[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<EmployeeRecord | null>(null);
  const [editingEmployee, setEditingEmployee] = useState<EmployeeRecord | null>(null);
  const [previewRefreshKey, setPreviewRefreshKey] = useState(0);
  const [showAddEmployee, setShowAddEmployee] = useState(false);
  const [showBulkUpload, setShowBulkUpload] = useState(false);
  const [employeeStats, setEmployeeStats] = useState({ total: 0, active: 0, bench: 0, in_project: 0, trainees: 0 });
  const [exporting, setExporting] = useState(false);
  const [exportLevel, setExportLevel] = useState<'basic' | 'hr' | 'payroll'>('basic');
  const authHeaders = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-name': user?.name || '',
  }), [user]);

  const fetchEmployees = useCallback(async () => {
    if (!user?.email && !user?.id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('per_page', '20');
      if (search) params.set('search', search);
      if (deptFilter !== 'All') params.set('department', deptFilter);
      if (statusFilter !== 'All') params.set('status', statusFilter);
      if (roleFilter !== 'All') params.set('role', roleFilter);
      if (locationFilter !== 'All') params.set('location', locationFilter);
      if (projectStatusFilter !== 'All') params.set('project_status', projectStatusFilter.toLowerCase().replace(/ /g, '_'));
      if (reportingManagerFilter !== 'All') params.set('reporting_manager', reportingManagerFilter);

      const res = await fetch(`${API_BASE}/employees/?${params.toString()}`, { headers: authHeaders });
      if (!res.ok) throw new Error(`Unable to load employees (${res.status})`);
      const data: EmployeeListResponse = await res.json();

      setEmployees(data.employees);
      setTotal(data.total);
      setOrganizationTotal(data.organization_total ?? data.total);
      setTotalPages(data.total_pages);
      setReportingManagerOptions(data.reporting_manager_options || []);
      setEmployeeStats(data.stats || { total: data.organization_total ?? data.total, active: 0, bench: 0, in_project: 0, trainees: 0 });
    } catch {
      console.log('Backend not available — showing empty state');
      setEmployees([]);
      setTotal(0);
      setOrganizationTotal(0);
      setEmployeeStats({ total: 0, active: 0, bench: 0, in_project: 0, trainees: 0 });
    } finally {
      setLoading(false);
    }
  }, [authHeaders, page, search, deptFilter, statusFilter, roleFilter, locationFilter, projectStatusFilter, reportingManagerFilter, user?.email, user?.id]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  // Debounced search
  const [searchInput, setSearchInput] = useState(initialSearch);
  useEffect(() => {
    const urlSearch = searchParams.get('search') || '';
    if (urlSearch !== searchInput) {
      setSearchInput(urlSearch);
      setSearch(urlSearch);
      setPage(1);
    }
  }, [searchParams]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const clearFilters = () => {
    setDeptFilter('All');
    setStatusFilter('All');
    setRoleFilter('All');
    setLocationFilter('All');
    setProjectStatusFilter('All');
    setReportingManagerFilter('All');
    setSearchInput('');
    setSearch('');
    setSearchParams({}, { replace: true });
    setPage(1);
  };

  const hasActiveFilters = deptFilter !== 'All' || statusFilter !== 'All' || roleFilter !== 'All' || locationFilter !== 'All' || projectStatusFilter !== 'All' || reportingManagerFilter !== 'All' || search.trim() !== '' || searchInput.trim() !== '';
  const organizationCount = organizationTotal || total;
  const headerCountText = hasActiveFilters
    ? `Showing ${total} of ${organizationCount} ${organizationCount === 1 ? 'employee' : 'employees'}`
    : `${organizationCount} ${organizationCount === 1 ? 'employee' : 'employees'} in the organization`;

  const handleEmployeeSaved = () => {
    fetchEmployees();
    setPreviewRefreshKey((key) => key + 1);
  };

  const exportCsv = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      params.set('page', '1');
      params.set('per_page', '100');
      if (search) params.set('search', search);
      if (deptFilter !== 'All') params.set('department', deptFilter);
      if (statusFilter !== 'All') params.set('status', statusFilter);
      if (roleFilter !== 'All') params.set('role', roleFilter);
      if (locationFilter !== 'All') params.set('location', locationFilter);
      if (projectStatusFilter !== 'All') params.set('project_status', projectStatusFilter.toLowerCase().replace(/ /g, '_'));
      if (reportingManagerFilter !== 'All') params.set('reporting_manager', reportingManagerFilter);
      params.set('level', exportLevel);

      const res = await fetch(`${API_BASE}/employees/export?${params.toString()}`, { headers: authHeaders });
      if (!res.ok) throw new Error(`Unable to export employees (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const date = new Date().toISOString().slice(0, 10);
      link.href = url;
      link.download = `reknew-employees-${exportLevel}-${date}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Unable to export employees.');
    } finally {
      setExporting(false);
    }
  };

  const statCards = [
    { label: 'Total employees', value: employeeStats.total, icon: <UsersRound size={16} />, tone: 'bg-[#f5f0e6] text-[#8a7a5c]' },
    { label: 'Active', value: employeeStats.active, icon: <CheckCircle2 size={16} />, tone: 'bg-[#e9f4ea] text-[#3f9b52]' },
    { label: 'On bench', value: employeeStats.bench, icon: <Briefcase size={16} />, tone: 'bg-[#fbf1dc] text-[#c98a1e]' },
    { label: 'In project', value: employeeStats.in_project, icon: <Briefcase size={16} />, tone: 'bg-[#fff7ef] text-[#d97a34]' },
    { label: 'Trainees', value: employeeStats.trainees, icon: <Award size={16} />, tone: 'bg-[#f0eafb] text-[#8a6bbf]' },
  ];

  return (
    <div className="-mx-[var(--layout-main-padding-x)] -my-[var(--layout-main-padding-y)] min-h-[calc(100vh-3.5rem)] bg-[#f7f3ec] px-8 py-[26px]">
      {/* Header */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="mb-1 text-[26px] font-bold tracking-[-.5px] text-[#1f2430]">Employees</h1>
          <p className="text-sm text-[#7a7263]">
            {headerCountText}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2.5">
          <button type="button" onClick={() => navigate('/organization')} className="flex h-11 items-center gap-2 rounded-[11px] border border-[#ece5d8] bg-white px-4 text-[13px] font-bold text-[#1f2430] hover:border-[#d97a34]"><Network size={15} />Organization Chart</button>
          <select
            className="h-11 rounded-[11px] border border-[#ece5d8] bg-white px-4 text-[13px] font-bold text-[#d97a34] outline-none focus:border-[#d97a34]"
            value={exportLevel}
            onChange={(event) => setExportLevel(event.target.value as 'basic' | 'hr' | 'payroll')}
            aria-label="Employee export level"
          >
            <option value="basic">Basic CSV</option>
            <option value="hr">Full export</option>
            <option value="payroll">Payroll CSV</option>
          </select>
          <button type="button" disabled={exporting} onClick={exportCsv} className="flex h-11 items-center gap-2 rounded-[11px] border border-[#ece5d8] bg-white px-4 text-[13px] font-bold text-[#1f2430] hover:border-[#d97a34] disabled:opacity-50"><Download size={15} />{exporting ? 'Exporting' : 'Export'}</button>
          <button type="button" onClick={() => setShowBulkUpload(true)} className="flex h-11 items-center gap-2 rounded-[11px] border border-[#d97a34] bg-white px-4 text-[13px] font-bold text-[#d97a34] hover:bg-[#fff7ef]"><Upload size={15} />Bulk Upload</button>
          <button type="button" onClick={() => setShowAddEmployee(true)} className="flex h-11 items-center gap-2 rounded-[11px] bg-[#2b3243] px-4 text-[13px] font-bold text-white shadow-[0_4px_12px_rgba(43,50,67,.22)] hover:bg-[#1f2430]"><UserPlus size={15} />Add Employee</button>
        </div>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3.5 md:grid-cols-3 xl:grid-cols-5">
        {statCards.map((stat) => <div key={stat.label} className="flex items-center gap-3 rounded-[14px] border border-[#ece5d8] bg-white px-[18px] py-[15px]"><span className={cn('grid h-[38px] w-[38px] shrink-0 place-items-center rounded-[11px]', stat.tone)}>{stat.icon}</span><div><div className="text-[21px] font-bold leading-none text-[#1f2430]">{stat.value}</div><div className="mt-1.5 text-[11.5px] text-[#8a8371]">{stat.label}</div></div></div>)}
      </div>

      {/* Search + Filters */}
      <div className="mb-5 rounded-[16px] border border-[#ece5d8] bg-white px-[18px] py-4">
        <div>
          {/* Search bar */}
          <div className="flex items-center gap-3 mb-4">
            <div className="flex flex-1 items-center gap-2 rounded-[10px] border border-[#ece5d8] bg-[#faf8f3] px-3.5 py-[11px]">
              <Search size={16} className="text-gray-400 shrink-0" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search by name or email..."
                className="bg-transparent border-none outline-none text-[13px] text-[var(--color-brand-navy)] placeholder:text-gray-400 w-full font-sans"
              />
              {searchInput && (
                <button onClick={() => { setSearchInput(''); setSearch(''); }} className="text-gray-400 hover:text-gray-600">
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Filter pills */}
          <div className="flex flex-wrap items-center gap-2.5">
            <Filter size={14} className="text-gray-400" />
            <FilterDropdown label="Department" value={deptFilter} options={DEPARTMENTS} onChange={(v) => { setDeptFilter(v); setPage(1); }} />
            <FilterDropdown label="Status" value={statusFilter} options={STATUSES} onChange={(v) => { setStatusFilter(v); setPage(1); }} />
            <FilterDropdown label="Role" value={roleFilter} options={ROLES} onChange={(v) => { setRoleFilter(v); setPage(1); }} />
            <FilterDropdown label="Work Arrangement" value={locationFilter} options={WORK_ARRANGEMENTS} onChange={(v) => { setLocationFilter(v); setPage(1); }} />
            <FilterDropdown label="Project Status" value={projectStatusFilter} options={PROJECT_STATUSES} onChange={(v) => { setProjectStatusFilter(v); setPage(1); }} />
            <FilterDropdown label="Reporting Manager" value={reportingManagerFilter} options={['All', ...reportingManagerOptions]} onChange={(v) => { setReportingManagerFilter(v); setPage(1); }} />
            {hasActiveFilters && (
              <button onClick={clearFilters} className="text-[12px] text-status-error font-medium hover:underline ml-1">
                Clear all
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-[16px] border border-[#ece5d8] bg-white">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-sm text-gray-400">Loading employees...</div>
          </div>
        ) : employees.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="text-3xl mb-3">👥</div>
            <div className="text-[15px] font-semibold text-[var(--color-brand-navy)] mb-1">No employees found</div>
            <div className="text-sm text-gray-500">
              {hasActiveFilters ? 'Try adjusting your filters' : 'Add your first employee to get started'}
            </div>
          </div>
        ) : (
          <>
            {/* Table header */}
            <div className="grid min-w-[1420px] grid-cols-[2.1fr_1fr_.9fr_1.2fr_1fr_1.1fr_.9fr_.9fr_60px] gap-3 border-b border-[#f0e7d8] bg-[#fdfbf7] px-[22px] py-3.5 text-[10px] font-bold uppercase tracking-wider text-[#a99e8a]">
              <div>Employee</div>
              <div>Department</div>
              <div>Role</div>
              <div>Reporting Manager</div>
              <div>Project Status</div>
              <div>Work Location</div>
              <div>Status</div>
              <div>Joined</div>
              <div className="text-right">Edit</div>
            </div>

            {/* Table rows */}
            {employees.map((emp, employeeIndex) => {
              const initials = `${emp.first_name[0]}${emp.last_name[0]}`.toUpperCase();
              const avatarTones = ['bg-[#fff0e1] text-[#d97a34]', 'bg-[#edf5ec] text-[#3f7d3f]', 'bg-[#eaeef6] text-[#5a6f9e]', 'bg-[#f0eafb] text-[#8a6bbf]', 'bg-[#f5f0e6] text-[#8a7a5c]'];
              return (
                <div
                  key={emp.id}
                  onClick={() => setSelectedEmployee(emp)}
                  className="grid min-w-[1420px] cursor-pointer grid-cols-[2.1fr_1fr_.9fr_1.2fr_1fr_1.1fr_.9fr_.9fr_60px] items-center gap-3 border-b border-[#f6f0e6] px-[22px] py-3.5 transition-colors hover:bg-[#fdfbf7]"
                >
                  {/* Name + email */}
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={cn('grid h-[38px] w-[38px] shrink-0 place-items-center rounded-full text-[12px] font-bold', avatarTones[employeeIndex % avatarTones.length])}>{initials}</span>
                    <div className="min-w-0">
                      <div className="text-[13.5px] font-semibold text-[var(--color-brand-navy)] truncate">
                        {emp.first_name} {emp.last_name}
                      </div>
                      <div className="text-[12px] text-gray-400 truncate">{emp.work_email}</div>
                    </div>
                  </div>

                  {/* Department */}
                  <div className="text-[13px] text-gray-500 truncate">{emp.department}</div>

                  {/* Role */}
                  <div className="text-[13px] text-gray-500 truncate">
                    {roleLabels[emp.role] || emp.role}
                  </div>

                  {/* Reporting Manager */}
                  <div className="text-[13px] text-gray-500 truncate" title={emp.reporting_manager || 'Not assigned'}>
                    {emp.reporting_manager || 'Not assigned'}
                  </div>

                  {/* Current project status */}
                  <div>
                    {(() => {
                      const presentation = projectStatusPresentation[emp.project_status || 'bench'] || projectStatusPresentation.bench;
                      return <Badge variant={presentation.variant}>{presentation.label}</Badge>;
                    })()}
                  </div>

                  {/* Work location and arrangement */}
                  <div className="min-w-0">
                    <div className="truncate text-[13px] text-gray-500" title={employeeWorkLocation(emp)}>{employeeWorkLocation(emp)}</div>
                    <div className="truncate text-[11px] text-gray-400">{emp.work_location || 'Arrangement not set'}</div>
                  </div>

                  {/* Status */}
                  <div className={cn('flex items-center gap-2 text-[12px] font-semibold', emp.employment_status === 'active' ? 'text-[#3f9b52]' : 'text-[#a99e8a]')}><span className={cn('h-2 w-2 rounded-full', emp.employment_status === 'active' ? 'bg-[#3f9b52]' : 'bg-[#a99e8a]')} />{emp.employment_status}</div>

                  {/* Joined */}
                  <div className="text-[12px] text-gray-400">
                    {emp.joining_date
                      ? new Date(emp.joining_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                      : '—'}
                  </div>

                  <div className="flex justify-end">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingEmployee(emp);
                      }}
                      title="Edit employee"
                      className="flex h-[30px] w-[30px] items-center justify-center rounded-[9px] border border-[#ece5d8] text-[#8a8371] transition-colors hover:border-[#d97a34] hover:text-[#d97a34]"
                    >
                      <Pencil size={15} />
                    </button>
                  </div>
                </div>
              );
            })}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-5 py-3">
                <div className="text-[12px] text-gray-400">
                  Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of {total}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page === 1}
                    className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center transition-colors',
                      page === 1 ? 'text-gray-300' : 'text-gray-500 hover:bg-hover-bg'
                    )}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      className={cn(
                        'w-8 h-8 rounded-lg flex items-center justify-center text-[13px] font-medium transition-colors',
                        p === page ? 'bg-olive text-white' : 'text-gray-500 hover:bg-hover-bg'
                      )}
                    >
                      {p}
                    </button>
                  ))}
                  <button
                    onClick={() => setPage(Math.min(totalPages, page + 1))}
                    disabled={page === totalPages}
                    className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center transition-colors',
                      page === totalPages ? 'text-gray-300' : 'text-gray-500 hover:bg-hover-bg'
                    )}
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Employee Detail Drawer */}
      <ExecutiveEmployeeDetail
        employee={selectedEmployee}
        open={!!selectedEmployee}
        onClose={() => setSelectedEmployee(null)}
        onEdit={(employee) => {
          setEditingEmployee(employee);
        }}
        refreshKey={previewRefreshKey}
      />

      <EditEmployeeDrawer
        employee={editingEmployee}
        employees={employees}
        open={!!editingEmployee}
        onClose={() => setEditingEmployee(null)}
        onSaved={handleEmployeeSaved}
      />

      {/* Add Employee Drawer — same component used on Dashboard */}
      <AddEmployeeDrawer
        open={showAddEmployee}
        onClose={() => {
          setShowAddEmployee(false);
          fetchEmployees(); // Refresh list after adding
        }}
      />
      <BulkEmployeeUploadModal
        open={showBulkUpload}
        onClose={() => setShowBulkUpload(false)}
        headers={authHeaders}
        onImported={(count) => {
          setShowBulkUpload(false);
          showToast({ message: `${count} ${count === 1 ? 'employee' : 'employees'} added.` });
          setPage(1);
          void fetchEmployees();
        }}
      />
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import {
  Search, Filter, UserPlus, Download, ChevronDown, ChevronLeft, ChevronRight,
  Mail, Phone, MapPin, Calendar, Briefcase, Building2, User, Shield, X,
  Pencil, Loader2, Plane, KeyRound, History, CheckCircle2,
} from 'lucide-react';
import { Card, CardHeader, Badge, Button, Avatar } from '@/components/ui';
import { Drawer } from '@/components/ui/Drawer';
import { AddEmployeeDrawer } from '@/components/dashboard/AddEmployeeDrawer';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = 'http://localhost:8000/api/v1';

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
  joining_date: string | null;
  reporting_manager: string;
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
}

interface EmployeeListResponse {
  employees: EmployeeRecord[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
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
const LOCATIONS = ['All', 'Onshore', 'Offshore', 'Remote', 'Hybrid'];

// ─── Status Badge ───
const statusVariant: Record<string, 'olive' | 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  active: 'success',
  inactive: 'neutral',
  onboarding: 'info',
  offboarding: 'warning',
};

const roleLabels: Record<string, string> = {
  super_admin: 'Super Admin',
  hr_admin: 'HR Admin',
  manager: 'Manager',
  employee: 'Employee',
  trainee: 'Trainee',
};

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
          'flex items-center gap-1.5 px-3 py-[7px] rounded-lg text-[13px] font-medium transition-colors border',
          value !== 'All'
            ? 'bg-olive/10 text-olive border-olive/20'
            : 'bg-warm-card text-gray-500 border-[#E5E7EB] hover:bg-hover-bg'
        )}
      >
        {label}: {value === 'All' ? 'All' : value}
        <ChevronDown size={12} className={cn('transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 z-20 bg-warm-card border border-[#E5E7EB] rounded-xl shadow-card-md py-1 min-w-[160px]">
            {options.map((opt) => (
              <button
                key={opt}
                onClick={() => { onChange(opt); setOpen(false); }}
                className={cn(
                  'w-full text-left px-4 py-2 text-[13px] font-medium transition-colors',
                  opt === value ? 'bg-hover-bg text-olive' : 'text-[#2F3437] hover:bg-hover-bg'
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
        <div className="text-[14px] text-[#2F3437] font-medium">{value || '—'}</div>
      </div>
    </div>
  );

  return (
    <Drawer open={open} onClose={onClose} title={fullName} subtitle={employee.work_email} width="w-[480px]">
      {/* Profile header */}
      <div className="flex items-center gap-4 mb-6 pb-6 border-b border-[#E5E7EB]">
        <div className="w-16 h-16 rounded-2xl bg-olive flex items-center justify-center text-white text-xl font-bold">
          {initials}
        </div>
        <div>
          <div className="text-lg font-bold text-[#2F3437]">{fullName}</div>
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

      <div className="h-px bg-[#E5E7EB] my-4" />

      {/* Employment */}
      <div className="text-[11px] font-bold text-gray-400 tracking-widest uppercase mb-3">Employment</div>
      <InfoRow icon={<Building2 size={15} />} label="Department" value={employee.department} />
      <InfoRow icon={<Briefcase size={15} />} label="Designation" value={employee.designation} />
      <InfoRow icon={<Shield size={15} />} label="Role" value={roleLabels[employee.role] || employee.role} />
      <InfoRow icon={<User size={15} />} label="Workforce Type" value={employee.workforce_type} />
      <InfoRow icon={<User size={15} />} label="Reporting Manager" value={employee.reporting_manager} />
      <InfoRow icon={<MapPin size={15} />} label="Work Location" value={employee.work_location} />
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
    employment: true,
    access: true,
    leave: true,
    audit: true,
  });

  useEffect(() => {
    if (!open || !employee) return;
    setLoadingPreview(true);
    setPreviewError('');
    fetch(`${API_BASE}/employees/${employee.id}/preview`)
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
  }, [open, employee, refreshKey]);

  if (!employee) return null;

  const data = preview?.employee || employee;
  const initials = `${data.first_name[0]}${data.last_name[0]}`.toUpperCase();
  const fullName = `${data.first_name} ${data.last_name}`;
  const auditChanges = preview?.audit_changes || [];
  const accountStatus = preview?.account_activation?.account_status || (data.is_first_login ? 'pending_activation' : (data.is_active ? 'active' : 'inactive'));
  const activationCode = preview?.account_activation?.activation_code || (data.is_first_login ? data.setup_code : null);
  const inviteStatus = preview?.account_activation?.invite_status || (data.is_first_login ? 'pending' : 'accepted');
  const accessRole = preview?.it_access?.access_level || data.role;

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
  const countryName = (countryCode?: string | null) => {
    const normalizedCode = countryCode?.trim();
    const countries: Record<string, string> = {
      '+1': 'United States / Canada',
      '+44': 'United Kingdom',
      '+49': 'Germany',
      '+61': 'Australia',
      '+81': 'Japan',
      '+91': 'India',
    };
    return normalizedCode ? countries[normalizedCode] || normalizedCode : 'Not recorded';
  };
  const mfaLabel = (status?: string | null, enabled?: boolean | null) => {
    if (enabled === true || status === 'enabled') return 'Enabled';
    if (status === 'pending_setup') return 'Pending setup';
    return 'Not available';
  };
  const toggleSection = (key: string) => setOpenSections((current) => ({ ...current, [key]: !current[key] }));

  const Metric = ({ label, value, tone = 'neutral' }: { label: string; value: string | number; tone?: 'neutral' | 'good' | 'warn' | 'bad' }) => (
    <div className="rounded-xl border border-[#E5E7EB] bg-warm-bg px-3 py-2.5">
      <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{label}</div>
      <div className={cn(
        'mt-1 text-[14px] font-semibold',
        tone === 'good' && 'text-status-success',
        tone === 'warn' && 'text-status-warning',
        tone === 'bad' && 'text-status-error',
        tone === 'neutral' && 'text-[#2F3437]'
      )}>
        {value}
      </div>
    </div>
  );

  const Panel = ({ id, title, icon, children }: { id: string; title: string; icon: React.ReactNode; children: React.ReactNode }) => (
    <div className="border border-[#E5E7EB] rounded-xl bg-warm-card overflow-hidden">
      <button onClick={() => toggleSection(id)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-hover-bg transition-colors">
        <span className="flex items-center gap-2 text-[13px] font-bold text-[#2F3437]">
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
        <div className="rounded-xl border border-[#E5E7EB] bg-warm-card p-4">
          <div className="flex items-start gap-4">
            <Avatar initials={initials} size="lg" variant={data.is_active ? 'filled' : 'soft'} src={data.profile_image_url} />
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-lg font-bold text-[#2F3437] truncate">{fullName}</div>
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
                <div className="flex items-center gap-2"><MapPin size={14} className="text-gray-400 shrink-0" />{data.work_location || 'Not recorded'}</div>
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
                <Metric label="Work Country" value={countryName(data.country_code)} />
                <Metric label="Work Location" value={data.work_location || 'Not recorded'} />
              </div>
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
              <div className="mt-3 rounded-xl bg-warm-bg border border-[#E5E7EB] px-3 py-2.5 text-[12.5px] text-gray-500">
                {preview?.leave_summary?.upcoming_leave_start
                  ? `Upcoming: ${formatDate(preview.leave_summary.upcoming_leave_start)} - ${formatDate(preview.leave_summary.upcoming_leave_end)} (${titleCase(preview.leave_summary.upcoming_leave_status)})`
                  : previewError ? 'No leave data available' : 'No leave scheduled'}
              </div>
            </Panel>

            <Panel id="audit" title="Audit History" icon={<History size={15} />}>
              {auditChanges.length > 0 ? (
                <div className="space-y-2">
                  {auditChanges.map((change) => (
                    <div key={change.id} className="rounded-xl bg-warm-bg border border-[#E5E7EB] px-3 py-2.5">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-[13px] font-semibold text-[#2F3437]">{titleCase(change.field_name)} updated</div>
                        <div className="text-[11px] text-gray-400 shrink-0">{formatDate(change.changed_at)}</div>
                      </div>
                      <div className="mt-1 text-[12px] text-gray-500">{change.old_value || 'Empty'} to {change.new_value || 'Empty'}</div>
                      <div className="mt-1 text-[11px] text-gray-400">By {change.changed_by}</div>
                    </div>
                  ))}
                  <button className="text-[12px] font-semibold text-olive hover:text-olive-dark transition-colors">View All</button>
                </div>
              ) : <div className="rounded-xl bg-warm-bg border border-[#E5E7EB] px-3 py-3 text-[13px] text-gray-400">No recent audit changes</div>}
            </Panel>
          </>
        )}
      </div>
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
  reporting_manager: string;
}

function EditEmployeeDrawer({
  employee,
  open,
  onClose,
  onSaved,
}: {
  employee: EmployeeRecord | null;
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
    reporting_manager: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

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
      reporting_manager: employee.reporting_manager,
    });
    setError('');
  }, [employee]);

  const update = (key: keyof EditFormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (error) setError('');
  };

  const save = async () => {
    if (!employee) return;
    if (!form.first_name.trim() || !form.last_name.trim() || !form.phone.trim()) {
      setError('First name, last name, and phone are required.');
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
  }: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    options?: string[];
  }) => (
    <div>
      <label className="block text-[13px] font-semibold text-[#2F3437] mb-1.5">
        {label}
      </label>
      {options ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3.5 py-2.5 rounded-xl text-[14px] font-medium bg-warm-bg border border-[#E5E7EB] text-[#2F3437] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10"
        >
          {options.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3.5 py-2.5 rounded-xl text-[14px] font-medium bg-warm-bg border border-[#E5E7EB] text-[#2F3437] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10"
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
              className="px-4 py-2.5 rounded-xl text-[13px] font-semibold text-gray-500 border border-[#E5E7EB] hover:bg-hover-bg transition-colors"
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
        <Field label="Designation" value={form.designation} onChange={(v) => update('designation', v)} />
        <Field label="Role" value={form.role} onChange={(v) => update('role', v)} options={ROLES.slice(1)} />
        <Field label="Workforce Type" value={form.workforce_type} onChange={(v) => update('workforce_type', v)} />
        <Field label="Status" value={form.employment_status} onChange={(v) => update('employment_status', v)} options={STATUSES.slice(1)} />
        <Field label="Work Location" value={form.work_location} onChange={(v) => update('work_location', v)} options={LOCATIONS.slice(1)} />
        <Field label="Reporting Manager" value={form.reporting_manager} onChange={(v) => update('reporting_manager', v)} />
      </div>
    </Drawer>
  );
}

export function EmployeesPage() {
  const [employees, setEmployees] = useState<EmployeeRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [roleFilter, setRoleFilter] = useState('All');
  const [locationFilter, setLocationFilter] = useState('All');
  const [selectedEmployee, setSelectedEmployee] = useState<EmployeeRecord | null>(null);
  const [editingEmployee, setEditingEmployee] = useState<EmployeeRecord | null>(null);
  const [previewRefreshKey, setPreviewRefreshKey] = useState(0);
  const [showAddEmployee, setShowAddEmployee] = useState(false);

  const fetchEmployees = useCallback(async () => {
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

      const res = await fetch(`${API_BASE}/employees/?${params.toString()}`);
      const data: EmployeeListResponse = await res.json();

      setEmployees(data.employees);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch {
      console.log('Backend not available — showing empty state');
      setEmployees([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, search, deptFilter, statusFilter, roleFilter, locationFilter]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  // Debounced search
  const [searchInput, setSearchInput] = useState('');
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
    setSearchInput('');
    setSearch('');
    setPage(1);
  };

  const hasActiveFilters = deptFilter !== 'All' || statusFilter !== 'All' || roleFilter !== 'All' || locationFilter !== 'All' || search !== '';

  const handleEmployeeSaved = () => {
    fetchEmployees();
    setPreviewRefreshKey((key) => key + 1);
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">Employees</h1>
          <p className="text-sm text-gray-500">
            {total} {total === 1 ? 'employee' : 'employees'} in the organization
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" icon={<Download size={14} />}>Export CSV</Button>
          <Button icon={<UserPlus size={14} />} onClick={() => setShowAddEmployee(true)}>Add Employee</Button>
        </div>
      </div>

      {/* Search + Filters */}
      <Card className="mb-5">
        <div className="px-5 py-4">
          {/* Search bar */}
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 flex items-center gap-2 px-3.5 py-[8px] bg-warm-bg border border-[#E5E7EB] rounded-lg">
              <Search size={16} className="text-gray-400 shrink-0" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search by name or email..."
                className="bg-transparent border-none outline-none text-[13px] text-[#2F3437] placeholder:text-gray-400 w-full font-sans"
              />
              {searchInput && (
                <button onClick={() => { setSearchInput(''); setSearch(''); }} className="text-gray-400 hover:text-gray-600">
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Filter pills */}
          <div className="flex items-center gap-2 flex-wrap">
            <Filter size={14} className="text-gray-400" />
            <FilterDropdown label="Department" value={deptFilter} options={DEPARTMENTS} onChange={(v) => { setDeptFilter(v); setPage(1); }} />
            <FilterDropdown label="Status" value={statusFilter} options={STATUSES} onChange={(v) => { setStatusFilter(v); setPage(1); }} />
            <FilterDropdown label="Role" value={roleFilter} options={ROLES} onChange={(v) => { setRoleFilter(v); setPage(1); }} />
            <FilterDropdown label="Location" value={locationFilter} options={LOCATIONS} onChange={(v) => { setLocationFilter(v); setPage(1); }} />
            {hasActiveFilters && (
              <button onClick={clearFilters} className="text-[12px] text-status-error font-medium hover:underline ml-1">
                Clear all
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-sm text-gray-400">Loading employees...</div>
          </div>
        ) : employees.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="text-3xl mb-3">👥</div>
            <div className="text-[15px] font-semibold text-[#2F3437] mb-1">No employees found</div>
            <div className="text-sm text-gray-500">
              {hasActiveFilters ? 'Try adjusting your filters' : 'Add your first employee to get started'}
            </div>
          </div>
        ) : (
          <>
            {/* Table header */}
            <div className="grid grid-cols-[1fr_140px_120px_120px_100px_100px_64px] gap-4 px-5 py-3 border-b border-[#E5E7EB] text-[11px] font-bold text-gray-400 tracking-wider uppercase">
              <div>Employee</div>
              <div>Department</div>
              <div>Role</div>
              <div>Location</div>
              <div>Status</div>
              <div>Joined</div>
              <div className="text-right">Edit</div>
            </div>

            {/* Table rows */}
            {employees.map((emp) => {
              const initials = `${emp.first_name[0]}${emp.last_name[0]}`.toUpperCase();
              return (
                <div
                  key={emp.id}
                  onClick={() => setSelectedEmployee(emp)}
                  className="grid grid-cols-[1fr_140px_120px_120px_100px_100px_64px] gap-4 px-5 py-3 border-b border-[#E5E7EB] hover:bg-hover-bg cursor-pointer transition-colors items-center"
                >
                  {/* Name + email */}
                  <div className="flex items-center gap-3 min-w-0">
                    <Avatar initials={initials} size="md" variant={emp.is_active ? 'filled' : 'soft'} />
                    <div className="min-w-0">
                      <div className="text-[13.5px] font-semibold text-[#2F3437] truncate">
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

                  {/* Location */}
                  <div className="text-[13px] text-gray-500 truncate">{emp.work_location}</div>

                  {/* Status */}
                  <div>
                    <Badge variant={statusVariant[emp.employment_status] || 'neutral'}>
                      {emp.employment_status}
                    </Badge>
                  </div>

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
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:bg-olive/10 hover:text-olive transition-colors"
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
      </Card>

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
    </div>
  );
}

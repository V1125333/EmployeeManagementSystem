import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Briefcase, User, Heart, Pencil, Camera, Trash2, Save, X, Loader2, KeyRound,
} from 'lucide-react';
import { Card, Badge, Button } from '@/components/ui';
import { AllocationMixBar } from '@/components/allocations/AllocationMixBar';
import { AuditTimeline } from '@/components/audit/AuditTimeline';
import { CareerProfilePanel } from '@/components/career/CareerProfilePanel';
import { OrganizationChart } from '@/components/organization/OrganizationChart';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface ProfileData {
  id: string;
  first_name: string;
  last_name: string;
  work_email: string;
  personal_email: string | null;
  phone: string;
  country_code: string;
  date_of_birth: string | null;
  gender: string | null;
  department: string;
  designation: string | null;
  role: string;
  workforce_type: string;
  employment_status: string;
  work_location: string;
  work_city: string | null;
  work_state: string | null;
  work_country: string | null;
  joining_date: string | null;
  reporting_manager: string;
  profile_image_url: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_contact_relation: string | null;
  current_address: string | null;
  is_active: boolean;
  created_at: string;
  last_updated_at: string | null;
  updated_by: string | null;
  last_login_at: string | null;
  last_active_at: string | null;
  mfa_enabled: boolean;
}

interface ProfileForm {
  full_name: string;
  personal_email: string;
  phone: string;
  date_of_birth: string;
  gender: string;
  current_address: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  emergency_contact_relation: string;
  work_city: string;
  work_state: string;
  work_country: string;
}

interface AllocationRecord {
  id: string;
  project_id: string | null;
  project_name: string | null;
  project_code?: string | null;
  project_location?: string | null;
  manager_name: string | null;
  allocation_percentage: number;
  allocation_role: string;
  billing_type: string;
  status: string;
  start_date: string;
  end_date: string | null;
}

interface AllocationDisplayRow extends AllocationRecord {
  isDerivedAvailability?: boolean;
}

type ProfileTab = 'overview' | 'organization' | 'allocations' | 'activity' | 'career';

const roleLabels: Record<string, string> = {
  super_admin: 'Super Admin',
  hr_admin: 'HR Admin',
  manager: 'Manager',
  employee: 'Employee',
  trainee: 'Trainee',
};

const allocationStatusVariant: Record<string, 'olive' | 'success' | 'warning' | 'error' | 'neutral' | 'info'> = {
  active: 'olive',
  available: 'info',
  upcoming: 'info',
  completed: 'neutral',
  cancelled: 'error',
  bench: 'neutral',
  partially_allocated: 'info',
  fully_allocated: 'olive',
  overallocated: 'error',
};

const GENDER_OPTIONS = [
  { value: '', label: 'Select gender' },
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'non_binary', label: 'Non-binary' },
  { value: 'prefer_not_to_say', label: 'Prefer not to say' },
];

function makeInitials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').toUpperCase().slice(0, 2);
}

function profileToForm(profile: ProfileData): ProfileForm {
  return {
    full_name: `${profile.first_name} ${profile.last_name}`.trim(),
    personal_email: profile.personal_email || '',
    phone: profile.phone || '',
    date_of_birth: profile.date_of_birth || '',
    gender: profile.gender || '',
    current_address: profile.current_address || '',
    emergency_contact_name: profile.emergency_contact_name || '',
    emergency_contact_phone: profile.emergency_contact_phone || '',
    emergency_contact_relation: profile.emergency_contact_relation || '',
    work_city: profile.work_city || '',
    work_state: profile.work_state || '',
    work_country: profile.work_country || '',
  };
}

function formatDate(value: string | null) {
  if (!value) return null;
  return new Date(value).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatShortDate(value: string | null) {
  if (!value) return null;
  return new Date(value).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatDateTime(value: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatTenure(joiningDate: string | null) {
  const joined = parseDateOnly(joiningDate);
  if (!joined) return 'Not available';
  const today = new Date();
  if (joined > today) return 'Starts soon';
  let months = (today.getFullYear() - joined.getFullYear()) * 12 + today.getMonth() - joined.getMonth();
  if (today.getDate() < joined.getDate()) months -= 1;
  if (months < 12) return `${Math.max(0, months)} mo`;
  const years = Math.floor(months / 12);
  const remainingMonths = months % 12;
  return remainingMonths ? `${years}y ${remainingMonths}m` : `${years} ${years === 1 ? 'yr' : 'yrs'}`;
}

function formatWorkLocation(city?: string | null, state?: string | null, country?: string | null) {
  const locality = [city?.trim(), state?.trim()].filter(Boolean).join(', ');
  return locality || country?.trim() || 'Location not set';
}

function parseDateOnly(value?: string | null) {
  if (!value) return null;
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function addDays(value: Date, days: number) {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return next;
}

function toIsoDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

function isCurrentAllocation(allocation: AllocationRecord) {
  if (allocation.status !== 'active') return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = parseDateOnly(allocation.start_date);
  const end = parseDateOnly(allocation.end_date);
  return Boolean(start && start <= today && (!end || end >= today));
}

function effectiveAllocationStatus(allocation: AllocationRecord) {
  if (allocation.status === 'active' && !isCurrentAllocation(allocation)) {
    return 'completed';
  }
  return allocation.status;
}

function formatAllocationStatus(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function projectDisplayName(allocation: AllocationRecord) {
  return allocation.project_name || 'Project not named';
}

function projectCode(allocation: AllocationRecord) {
  return allocation.project_code || '-';
}

function buildAvailabilityRow(allocations: AllocationRecord[]): AllocationDisplayRow | null {
  const currentAllocations = allocations.filter(isCurrentAllocation);
  const activeTotal = currentAllocations.reduce(
    (total, allocation) => total + Number(allocation.allocation_percentage || 0),
    0
  );
  if (activeTotal >= 100) return null;

  const endedDates = allocations
    .filter((allocation) => allocation.status !== 'cancelled')
    .map((allocation) => parseDateOnly(allocation.end_date))
    .filter((value): value is Date => Boolean(value))
    .sort((a, b) => b.getTime() - a.getTime());
  const benchStart = endedDates[0] ? addDays(endedDates[0], 1) : new Date();
  benchStart.setHours(0, 0, 0, 0);
  const reviewDate = addDays(benchStart, 30);

  return {
    id: 'derived-availability',
    project_id: null,
    project_name: activeTotal === 0 ? 'Bench / Available' : 'Available Capacity',
    project_code: activeTotal === 0 ? 'BENCH' : 'AVAILABLE',
    project_location: allocations[0]?.project_location || 'Remote',
    manager_name: currentAllocations[0]?.manager_name || allocations[0]?.manager_name || 'Resource Management',
    allocation_percentage: 100 - activeTotal,
    allocation_role: activeTotal === 0 ? 'Bench' : 'Available capacity',
    billing_type: 'internal',
    status: activeTotal === 0 ? 'bench' : 'available',
    start_date: toIsoDate(benchStart),
    end_date: toIsoDate(reviewDate),
    isDerivedAvailability: true,
  };
}

function normalizeRole(role: string | undefined) {
  return role === 'Global Access' ? 'super_admin' : role || '';
}

function normalizedRoleKey(role: string | undefined) {
  return normalizeRole(role).toLowerCase().replace(/\s+/g, '_');
}

function canViewEmployeeActivity(userRole: string | undefined) {
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalizedRoleKey(userRole));
}

function validateForm(form: ProfileForm) {
  const nextErrors: Partial<Record<keyof ProfileForm | 'image', string>> = {};
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const phonePattern = /^[0-9+()\-\s]{7,20}$/;
  const phoneDigits = form.phone.replace(/\D/g, '');
  const emergencyName = form.emergency_contact_name.trim();
  const emergencyPhone = form.emergency_contact_phone.trim();
  const emergencyRelation = form.emergency_contact_relation.trim();
  const emergencyDigits = emergencyPhone.replace(/\D/g, '');
  const hasEmergencyContact = Boolean(emergencyName || emergencyPhone || emergencyRelation);

  if (!form.full_name.trim()) nextErrors.full_name = 'Full name is required';
  if (form.full_name.trim().split(/\s+/).length < 2) nextErrors.full_name = 'Enter first and last name';
  if (form.personal_email && !emailPattern.test(form.personal_email)) nextErrors.personal_email = 'Enter a valid email';
  if (!form.phone.trim()) nextErrors.phone = 'Phone number is required';
  if (form.phone && (!phonePattern.test(form.phone) || phoneDigits.length < 7)) nextErrors.phone = 'Enter a valid phone number';

  if (hasEmergencyContact && !emergencyName) nextErrors.emergency_contact_name = 'Emergency contact name is required';
  if (hasEmergencyContact && !emergencyPhone) nextErrors.emergency_contact_phone = 'Emergency contact phone is required';
  if (hasEmergencyContact && !emergencyRelation) nextErrors.emergency_contact_relation = 'Relationship is required';
  if (emergencyPhone && (!phonePattern.test(emergencyPhone) || emergencyDigits.length < 7)) {
    nextErrors.emergency_contact_phone = 'Enter a valid emergency phone';
  }

  return nextErrors;
}

function InfoRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-[var(--color-border)] last:border-b-0">
      <span className="text-gray-400 mt-0.5 shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-gray-400 font-medium uppercase tracking-wider mb-0.5">{label}</div>
        <div className="text-[14px] text-[var(--color-brand-navy)] font-medium break-words">{value || '—'}</div>
      </div>
    </div>
  );
}

function ProfileInfoItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">{label}</div>
      <div className="break-words text-[14px] font-semibold text-[var(--color-brand-navy)]">{value || '—'}</div>
    </div>
  );
}

function EmploymentRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-6 border-b border-[var(--color-border)] py-3.5 last:border-b-0">
      <span className="text-[13px] text-gray-500">{label}</span>
      <span className="text-right text-[14px] font-semibold text-[var(--color-brand-navy)]">{value || '—'}</span>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  error,
  type = 'text',
  textarea,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type?: string;
  textarea?: boolean;
  options?: { value: string; label: string }[] | string[];
}) {
  const inputClass = cn(
    'w-full rounded-xl text-[14px] font-medium bg-warm-bg border text-[var(--color-brand-navy)]',
    'outline-none transition-all duration-150 focus:border-olive/40 focus:ring-2 focus:ring-olive/10',
    error ? 'border-status-error/40' : 'border-[var(--color-border)]',
    textarea ? 'px-3.5 py-3 min-h-[94px] resize-none' : 'px-3.5 py-2.5'
  );

  return (
    <div>
      <label className="block text-[13px] font-semibold text-[var(--color-brand-navy)] mb-1.5">{label}</label>
      {options ? (
        <select value={value} onChange={(e) => onChange(e.target.value)} className={inputClass}>
          {options.map((option) => {
            const item = typeof option === 'string' ? { value: option, label: option } : option;
            return <option key={item.value} value={item.value}>{item.label}</option>;
          })}
        </select>
      ) : textarea ? (
        <textarea value={value} onChange={(e) => onChange(e.target.value)} className={inputClass} />
      ) : (
        <input type={type} value={value} onChange={(e) => onChange(e.target.value)} className={inputClass} />
      )}
      {error && <div className="mt-1.5 text-[12px] font-medium text-status-error">{error}</div>}
    </div>
  );
}

export function ProfilePage() {
  const { user, updateUser } = useAuth();
  const { showToast } = useToast();
  const [searchParams] = useSearchParams();
  const employeeIdParam = searchParams.get('employee_id');
  const requestedTab = searchParams.get('tab');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [form, setForm] = useState<ProfileForm | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Partial<Record<keyof ProfileForm | 'image', string>>>({});
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [confirmRemoveEmergency, setConfirmRemoveEmergency] = useState(false);
  const [activeTab, setActiveTab] = useState<ProfileTab>(
    requestedTab === 'organization' || requestedTab === 'allocations' || requestedTab === 'activity' || requestedTab === 'career' ? requestedTab : 'overview'
  );
  const [allocations, setAllocations] = useState<AllocationRecord[]>([]);
  const [allocationsLoading, setAllocationsLoading] = useState(false);
  const [allocationsError, setAllocationsError] = useState('');
  const [passwordResetLoading, setPasswordResetLoading] = useState(false);

  const loadProfile = async () => {
    if (!user?.email && !employeeIdParam) {
      setLoading(false);
      setError('No email found');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const res = employeeIdParam
        ? await fetch(`${API_BASE}/employees/${encodeURIComponent(employeeIdParam)}`, {
          headers: {
            'x-user-id': user?.id || '',
            'x-user-role': normalizeRole(user?.role),
            'x-user-email': user?.email || '',
          },
        })
        : await fetch(`${API_BASE}/auth/me/${encodeURIComponent(user?.email || '')}`);
      const data = await res.json();
      const nextProfile = employeeIdParam ? data : data.employee;
      if (res.ok && nextProfile && (employeeIdParam || data.success)) {
        setProfile(nextProfile);
        setForm(profileToForm(nextProfile));
      } else {
        setError(data.detail || data.message || 'Profile not found');
      }
    } catch {
      setError('Cannot connect to server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, [employeeIdParam, user?.email, user?.id, user?.role]);

  useEffect(() => {
    if (requestedTab === 'organization' || requestedTab === 'allocations' || requestedTab === 'activity' || requestedTab === 'overview' || requestedTab === 'career') {
      setActiveTab(requestedTab);
    }
  }, [requestedTab]);

  const loadAllocations = async (employeeId: string) => {
    setAllocationsLoading(true);
    setAllocationsError('');
    try {
      const res = await fetch(`${API_BASE}/allocations/employee/${employeeId}`, {
        headers: {
          'x-user-id': user?.id || employeeId,
          'x-user-role': normalizeRole(user?.role),
          'x-user-email': user?.email || profile?.work_email || '',
        },
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Unable to load allocations');
      }
      setAllocations(Array.isArray(data) ? data : []);
    } catch (err) {
      setAllocations([]);
      setAllocationsError(err instanceof Error ? err.message : 'Unable to load allocations');
    } finally {
      setAllocationsLoading(false);
    }
  };

  useEffect(() => {
    if (profile?.id) loadAllocations(profile.id);
  }, [profile?.id, user?.id, user?.email, user?.role]);

  useEffect(() => {
    return () => {
      if (imagePreview?.startsWith('blob:')) URL.revokeObjectURL(imagePreview);
    };
  }, [imagePreview]);

  const originalForm = useMemo(() => (profile ? profileToForm(profile) : null), [profile]);
  const currentImage = removeImage ? null : imagePreview || profile?.profile_image_url || null;
  const fullName = form?.full_name || (profile ? `${profile.first_name} ${profile.last_name}` : '');
  const initials = makeInitials(fullName || user?.name || 'User');
  const dirty = Boolean(
    form && originalForm && (
      JSON.stringify(form) !== JSON.stringify(originalForm) ||
      imageFile ||
      removeImage
    )
  );
  const hasSavedEmergencyContact = Boolean(
    profile && (
      profile.emergency_contact_name?.trim() ||
      profile.emergency_contact_phone?.trim() ||
      profile.emergency_contact_relation?.trim()
    )
  );
  const isOwnProfile = Boolean(profile && user && (profile.id === user.id || profile.work_email.toLowerCase() === user.email?.toLowerCase()));
  const canEditProfile = isOwnProfile;
  const canViewActivity = canViewEmployeeActivity(user?.role);
  const visibleTabs = useMemo(
    () => [
      { key: 'overview' as const, label: 'Overview' },
      { key: 'organization' as const, label: 'Organization' },
      { key: 'allocations' as const, label: 'Allocations' },
      ...(canViewActivity ? [{ key: 'activity' as const, label: 'Activity' }] : []),
      { key: 'career' as const, label: 'Career Profile' },
    ],
    [canViewActivity]
  );
  const currentAllocations = useMemo(() => allocations.filter(isCurrentAllocation), [allocations]);
  const allocationRows = useMemo<AllocationDisplayRow[]>(() => {
    const availabilityRow = buildAvailabilityRow(allocations);
    return availabilityRow ? [...allocations, availabilityRow] : allocations;
  }, [allocations]);
  const derivedAllocationSummary = useMemo(() => {
    const totalActive = currentAllocations.reduce(
      (total, allocation) => total + Number(allocation.allocation_percentage || 0),
      0
    );
    const activeProjectIds = new Set(
      currentAllocations.map((allocation) => allocation.project_id || allocation.project_name || allocation.id)
    );
    const activeEndDates = currentAllocations
      .map((allocation) => allocation.end_date)
      .filter(Boolean)
      .sort() as string[];
    let allocationStatus = 'bench';
    if (totalActive > 100) allocationStatus = 'overallocated';
    else if (totalActive === 100) allocationStatus = 'fully_allocated';
    else if (totalActive > 0) allocationStatus = 'partially_allocated';

    return {
      total_active_allocation_percentage: totalActive,
      available_capacity_percentage: Math.max(0, 100 - totalActive),
      allocation_status: allocationStatus,
      active_projects_count: activeProjectIds.size,
      next_end_date: activeEndDates[0] || null,
    };
  }, [currentAllocations]);

  const completeness = useMemo(() => {
    if (!profile || !form) return { percent: 0, firstMissing: null as null | { label: string; sectionId: string } };
    const fields = [
      { value: form.full_name, label: 'your name', sectionId: 'profile-personal' },
      { value: profile.work_email, label: 'your work email', sectionId: 'profile-personal' },
      { value: form.personal_email, label: 'your personal email', sectionId: 'profile-personal' },
      { value: form.phone, label: 'your phone number', sectionId: 'profile-personal' },
      { value: form.date_of_birth, label: 'your date of birth', sectionId: 'profile-personal' },
      { value: form.gender, label: 'your gender', sectionId: 'profile-personal' },
      { value: form.current_address, label: 'your address', sectionId: 'profile-personal' },
      { value: profile.department, label: 'your department', sectionId: 'profile-employment' },
      { value: profile.designation, label: 'your designation', sectionId: 'profile-employment' },
      { value: form.work_city, label: 'your work city', sectionId: 'profile-personal' },
      { value: form.work_country, label: 'your work country', sectionId: 'profile-personal' },
      { value: profile.joining_date, label: 'your joining date', sectionId: 'profile-employment' },
      { value: form.emergency_contact_name, label: 'an emergency contact', sectionId: 'profile-emergency' },
      { value: form.emergency_contact_phone, label: 'an emergency contact phone', sectionId: 'profile-emergency' },
      { value: form.emergency_contact_relation, label: 'an emergency contact relationship', sectionId: 'profile-emergency' },
    ];
    const filled = fields.filter((field) => String(field.value || '').trim()).length;
    const firstMissingField = fields.find((field) => !String(field.value || '').trim());
    return {
      percent: Math.round((filled / fields.length) * 100),
      firstMissing: firstMissingField ? { label: firstMissingField.label, sectionId: firstMissingField.sectionId } : null,
    };
  }, [form, profile]);

  const isOnline = useMemo(() => {
    if (!profile?.last_active_at) return false;
    const lastActive = new Date(profile.last_active_at).getTime();
    return Number.isFinite(lastActive) && Date.now() - lastActive <= 15 * 60 * 1000;
  }, [profile?.last_active_at]);

  useEffect(() => {
    if (activeTab === 'activity' && !canViewActivity) {
      setActiveTab('overview');
    }
  }, [activeTab, canViewActivity]);

  const updateForm = (key: keyof ProfileForm, value: string) => {
    setForm((current) => current ? { ...current, [key]: value } : current);
    setErrors((current) => ({ ...current, [key]: undefined }));
    if (key.startsWith('emergency_contact_')) setConfirmRemoveEmergency(false);
  };

  const startEdit = () => {
    if (!profile) return;
    if (!canEditProfile) {
      showToast({ message: 'Managers can view employee profiles, but only the employee or HR/admin can edit them.' });
      return;
    }
    setForm(profileToForm(profile));
    setImageFile(null);
    setImagePreview(null);
    setRemoveImage(false);
    setErrors({});
    setConfirmRemoveEmergency(false);
    setEditMode(true);
  };

  const openProfileSection = (sectionId: string) => {
    if (!editMode && canEditProfile && sectionId !== 'profile-employment') startEdit();
    window.setTimeout(() => document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 0);
  };

  const requestPasswordReset = async () => {
    if (!profile || !isOwnProfile) return;
    setPasswordResetLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/forgot-password/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: profile.work_email.toLowerCase() }),
      });
      const result = await res.json().catch(() => null);
      if (!res.ok || !result?.success) throw new Error(result?.detail || result?.message || 'Could not start password reset.');
      showToast({ message: 'Password reset instructions were sent to your work email.' });
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Could not start password reset.' });
    } finally {
      setPasswordResetLoading(false);
    }
  };

  const cancelEdit = () => {
    if (profile) setForm(profileToForm(profile));
    setImageFile(null);
    setImagePreview(null);
    setRemoveImage(false);
    setErrors({});
    setConfirmRemoveEmergency(false);
    setEditMode(false);
  };

  const chooseImage = (file: File | undefined) => {
    if (!file) return;
    if (!canEditProfile) {
      showToast({ message: 'Only the employee or HR/admin can update this profile photo.' });
      return;
    }
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
    if (!allowedTypes.includes(file.type)) {
      setErrors((current) => ({ ...current, image: 'Use JPEG, PNG, WebP, or GIF' }));
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setErrors((current) => ({ ...current, image: 'Image must be 5MB or less' }));
      return;
    }

    if (imagePreview?.startsWith('blob:')) URL.revokeObjectURL(imagePreview);
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
    setRemoveImage(false);
    setErrors((current) => ({ ...current, image: undefined }));
  };

  const handleRemoveImage = () => {
    if (!canEditProfile) {
      showToast({ message: 'Only the employee or HR/admin can remove this profile photo.' });
      return;
    }
    if (imagePreview?.startsWith('blob:')) URL.revokeObjectURL(imagePreview);
    setImageFile(null);
    setImagePreview(null);
    setRemoveImage(true);
    setErrors((current) => ({ ...current, image: undefined }));
  };

  const saveProfile = async () => {
    if (!profile || !form || !dirty) return;
    if (!canEditProfile) {
      showToast({ message: 'Only the employee or HR/admin can save profile changes.' });
      return;
    }
    const nextErrors = validateForm(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    const headers = {
      'Content-Type': 'application/json',
      'x-user-id': user?.id || profile.id,
      'x-user-role': normalizeRole(user?.role),
      'x-user-email': user?.email || profile.work_email,
      'x-user-name': user?.name || form.full_name,
    };

    setSaving(true);
    try {
      const body = {
        personal_email: form.personal_email || null,
        phone: form.phone,
        date_of_birth: form.date_of_birth || null,
        gender: form.gender || null,
        current_address: form.current_address || null,
        emergency_contact_name: form.emergency_contact_name || null,
        emergency_contact_phone: form.emergency_contact_phone || null,
        emergency_contact_relation: form.emergency_contact_relation || null,
        ...(removeImage ? { profile_image_url: null } : {}),
      };

      const res = await fetch(`${API_BASE}/employees/${profile.id}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(body),
      });
      const result = await res.json();
      if (!res.ok || !result.success) {
        throw new Error(result.detail || result.message || 'Unable to save profile');
      }

      if (imageFile) {
        const imageData = new FormData();
        imageData.append('file', imageFile);
        const uploadRes = await fetch(`${API_BASE}/employees/${profile.id}/upload-profile-picture`, {
          method: 'POST',
          headers: {
            'x-user-id': user?.id || profile.id,
            'x-user-role': normalizeRole(user?.role),
            'x-user-email': user?.email || profile.work_email,
            'x-user-name': user?.name || form.full_name,
          },
          body: imageData,
        });
        const uploadResult = await uploadRes.json();
        if (!uploadRes.ok || !uploadResult.success) {
          throw new Error(uploadResult.detail || uploadResult.message || 'Unable to upload profile photo');
        }
      }

      const refreshedRes = await fetch(`${API_BASE}/auth/me/${encodeURIComponent(profile.work_email)}`);
      const refreshed = await refreshedRes.json();
      const nextProfile = refreshed.employee || result.employee;
      setProfile(nextProfile);
      setForm(profileToForm(nextProfile));
      setImageFile(null);
      setImagePreview(null);
      setRemoveImage(false);
      setConfirmRemoveEmergency(false);
      setEditMode(false);
      if (nextProfile.id === user?.id || nextProfile.work_email === user?.email) {
        updateUser({
          name: `${nextProfile.first_name} ${nextProfile.last_name}`.trim(),
          initials: makeInitials(`${nextProfile.first_name} ${nextProfile.last_name}`),
          profileImageUrl: nextProfile.profile_image_url || null,
        });
      }
      window.dispatchEvent(new CustomEvent('reknew:actions-updated'));
      showToast({ message: 'Profile updated successfully' });
    } catch (err) {
      setErrors((current) => ({
        ...current,
        image: err instanceof Error ? err.message : 'Unable to save profile',
      }));
    } finally {
      setSaving(false);
    }
  };

  const removeEmergencyContact = async () => {
    if (!profile || !form) return;
    if (!canEditProfile) {
      showToast({ message: 'Only the employee or HR/admin can remove emergency contact details.' });
      return;
    }

    const headers = {
      'Content-Type': 'application/json',
      'x-user-id': user?.id || profile.id,
      'x-user-role': normalizeRole(user?.role),
      'x-user-email': user?.email || profile.work_email,
      'x-user-name': user?.name || form.full_name,
    };

    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/employees/${profile.id}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({
          emergency_contact_name: null,
          emergency_contact_phone: null,
          emergency_contact_relation: null,
        }),
      });
      const result = await res.json();
      if (!res.ok || !result.success) {
        throw new Error(result.detail || result.message || 'Unable to remove emergency contact');
      }

      const nextProfile = result.employee || {
        ...profile,
        emergency_contact_name: null,
        emergency_contact_phone: null,
        emergency_contact_relation: null,
      };
      setProfile(nextProfile);
      setForm(profileToForm(nextProfile));
      setErrors({});
      setConfirmRemoveEmergency(false);
      setEditMode(false);
      window.dispatchEvent(new CustomEvent('reknew:actions-updated'));
      showToast({ message: 'Emergency contact removed.' });
    } catch (err) {
      showToast({ message: err instanceof Error ? err.message : 'Unable to remove emergency contact.' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-gray-400">Loading profile...</div>
      </div>
    );
  }

  if (error || !profile || !form) {
    return (
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-[var(--color-brand-navy)] tracking-tight mb-1">My Profile</h1>
          <p className="text-sm text-gray-500">Your personal and employment information</p>
        </div>
        <Card className="flex items-center justify-center py-20">
          <div className="text-center">
            <div className="text-[15px] font-semibold text-[var(--color-brand-navy)] mb-1">Profile unavailable</div>
            <div className="text-sm text-gray-500">{error || 'Profile data is only available for registered employees.'}</div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">{isOwnProfile ? 'My Profile' : 'Employee Profile'}</h1>
          <p className="text-sm text-gray-500">{isOwnProfile ? 'Your personal and employment information.' : `${fullName}'s personal and employment information.`}</p>
        </div>
        {canEditProfile && (editMode ? (
          <div className="flex items-center gap-2">
            <Button variant="ghost" icon={<X size={14} />} onClick={cancelEdit} disabled={saving}>Cancel</Button>
            <Button icon={saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} onClick={saveProfile} disabled={!dirty || saving}>
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        ) : (
          <Button icon={<Pencil size={14} />} onClick={startEdit}>Edit Profile</Button>
        ))}
      </div>

      <div className="relative mb-5 overflow-hidden rounded-3xl border border-[#ece0cb] bg-[#fbf5ea] px-6 py-7 text-[#1f2430] shadow-[0_10px_30px_rgba(60,40,10,0.05)] md:px-8">
        <div className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(217,122,52,0.16),transparent_70%)]" />
        <div className="relative flex flex-col gap-7 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="relative h-24 w-24 shrink-0">
              <button
                type="button"
                disabled={!editMode || !canEditProfile}
                onClick={() => editMode && canEditProfile && fileInputRef.current?.click()}
                className={cn(
                  'flex h-24 w-24 items-center justify-center overflow-hidden rounded-full bg-[linear-gradient(135deg,#e79a55,#c9611f)] text-2xl font-bold text-white',
                  'ring-[3px] ring-white shadow-[0_4px_12px_rgba(201,97,31,0.25)] transition-all duration-200',
                  editMode && canEditProfile && 'cursor-pointer hover:ring-white'
                )}
              >
                {currentImage ? (
                  <img src={currentImage} alt="Profile" className="w-full h-full object-cover" />
                ) : (
                  initials
                )}
                {editMode && canEditProfile && (
                  <span className="absolute inset-0 rounded-full bg-black/35 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center">
                    <Camera size={22} />
                  </span>
                )}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                className="hidden"
                onChange={(event) => chooseImage(event.target.files?.[0])}
              />
              {editMode && canEditProfile && currentImage && (
                <button
                  type="button"
                  onClick={handleRemoveImage}
                  title="Remove photo"
                  className="absolute -right-1 -bottom-1 w-8 h-8 rounded-full bg-warm-card border border-[var(--color-border)] text-status-error flex items-center justify-center shadow-card hover:bg-status-error/5 transition-colors"
                >
                  <Trash2 size={15} />
                </button>
              )}
              <span
                title={isOnline ? 'Online' : 'Offline'}
                className={cn('absolute bottom-1 right-1 h-4 w-4 rounded-full border-[3px] border-[#fbf5ea]', isOnline ? 'bg-emerald-400' : 'bg-gray-400')}
              />
            </div>

            <div className="min-w-0">
              <div className="mb-0.5 text-2xl font-bold text-[#1f2430]">{fullName}</div>
              <div className="mb-3 text-[14px] text-[#8a8371]">
                {profile.designation || roleLabels[profile.role] || profile.role} <span className="text-[#8a8371]">·</span> {profile.department || 'Department not set'}
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-[#e5f3e5] px-3 py-1 text-xs font-bold text-[#3f7d3f]">• {formatAllocationStatus(profile.employment_status)}</span>
                <span className="rounded-full bg-[#fbeee1] px-3 py-1 text-xs font-bold text-[#b8611f]">{roleLabels[profile.role] || profile.role}</span>
                <span className="rounded-full bg-[#efe7d8] px-3 py-1 text-xs font-bold text-[#7a7263]">{formatAllocationStatus(profile.workforce_type)}</span>
              </div>
              {errors.image && <div className="mt-2 text-[12px] font-medium text-status-error">{errors.image}</div>}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: 'Tenure', value: formatTenure(profile.joining_date), detail: profile.joining_date ? `Since ${formatShortDate(profile.joining_date)}` : 'Joining date not set' },
              { label: 'Work Location', value: formatWorkLocation(profile.work_city, profile.work_state, profile.work_country), detail: profile.work_location || 'Work arrangement not set' },
              { label: 'Reporting Manager', value: profile.reporting_manager || '—', detail: profile.reporting_manager ? 'Reports to' : 'No manager assigned' },
            ].map((stat) => (
              <div key={stat.label} className="min-w-[142px] rounded-2xl border border-[#ece0cb] bg-white px-5 py-4">
                <div className="text-xs font-medium text-[#8a8371]">{stat.label}</div>
                <div className="mt-1 max-w-[180px] truncate text-xl font-bold text-[#1f2430]" title={stat.value}>{stat.value}</div>
                <div className="mt-1 max-w-[180px] truncate text-[11px] text-[#a99e8a]">{stat.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <Card className="mb-5 p-5">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="text-[13px] font-bold text-[var(--color-brand-navy)]">Profile completeness</div>
          <div className="text-[13px] font-bold text-[var(--color-brand-orange)]">{completeness.percent}%</div>
        </div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-[var(--color-border)]">
            <div className="h-full rounded-full bg-gradient-to-r from-[var(--color-brand-orange)] to-olive transition-all" style={{ width: `${completeness.percent}%` }} />
          </div>
          {completeness.firstMissing ? (
            <button type="button" onClick={() => openProfileSection(completeness.firstMissing!.sectionId)} className="text-left text-[13px] text-gray-500 hover:text-[var(--color-brand-orange)] lg:min-w-[300px] lg:text-right">
              Add <span className="font-semibold text-[var(--color-brand-orange)]">{completeness.firstMissing.label}</span> to improve your profile.
            </button>
          ) : (
            <div className="text-[13px] font-semibold text-status-success">Your profile is complete.</div>
          )}
        </div>
      </Card>

      <div className="mb-5 flex border-b border-[var(--color-border)]">
        {visibleTabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'border-b-2 px-4 py-3 text-[13px] font-bold transition-colors',
              activeTab === tab.key
                ? 'border-olive text-[var(--color-brand-navy)]'
                : 'border-transparent text-gray-400 hover:text-[var(--color-brand-navy)]'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-5">
        <div className="space-y-5 xl:col-span-3">
        <Card id="profile-personal">
          <div className="flex items-center gap-3 px-6 pt-6">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-brand-orange)]/10 text-[var(--color-brand-orange)]"><User size={16} /></div>
            <div className="text-[15px] font-bold text-[var(--color-brand-navy)]">Personal Information</div>
          </div>
          <div className="px-6 pb-6 pt-5">
            {editMode ? (
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <Field label="Personal Email" value={form.personal_email} onChange={(v) => updateForm('personal_email', v)} error={errors.personal_email} type="email" />
                <Field label="Phone Number" value={form.phone} onChange={(v) => updateForm('phone', v)} error={errors.phone} />
                <Field label="Date of Birth" value={form.date_of_birth} onChange={(v) => updateForm('date_of_birth', v)} type="date" />
                <Field label="Gender" value={form.gender} onChange={(v) => updateForm('gender', v)} options={GENDER_OPTIONS} />
                <div className="md:col-span-2">
                  <Field label="Address" value={form.current_address} onChange={(v) => updateForm('current_address', v)} textarea />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-x-10 gap-y-6 md:grid-cols-2">
                <ProfileInfoItem label="Work Email" value={profile.work_email} />
                <ProfileInfoItem label="Personal Email" value={profile.personal_email} />
                <ProfileInfoItem label="Phone" value={profile.phone ? `${profile.country_code || ''} ${profile.phone}`.trim() : null} />
                <ProfileInfoItem label="Date of Birth" value={formatDate(profile.date_of_birth)} />
                <ProfileInfoItem label="Gender" value={profile.gender ? formatAllocationStatus(profile.gender) : null} />
                <ProfileInfoItem label="Address" value={profile.current_address} />
              </div>
            )}
          </div>
        </Card>

        <Card id="profile-emergency">
          <div className="flex items-center gap-3 px-6 pt-6">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-brand-orange)]/10 text-[var(--color-brand-orange)]"><Heart size={16} /></div>
            <div className="text-[15px] font-bold text-[var(--color-brand-navy)]">Emergency Contact</div>
          </div>
          <div className="px-6 pb-6 pt-4">
            {editMode ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Field label="Contact Name *" value={form.emergency_contact_name} onChange={(v) => updateForm('emergency_contact_name', v)} error={errors.emergency_contact_name} />
                  <Field label="Contact Phone *" value={form.emergency_contact_phone} onChange={(v) => updateForm('emergency_contact_phone', v)} error={errors.emergency_contact_phone} />
                  <div className="md:col-span-2">
                    <Field label="Relationship *" value={form.emergency_contact_relation} onChange={(v) => updateForm('emergency_contact_relation', v)} error={errors.emergency_contact_relation} />
                  </div>
                </div>
                {hasSavedEmergencyContact && (
                  <div className="rounded-xl border border-status-error/20 bg-status-error/[0.04] p-3">
                    {confirmRemoveEmergency ? (
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <div className="text-[13px] font-semibold text-[var(--color-brand-navy)]">Remove emergency contact?</div>
                          <div className="text-[12px] text-gray-500">This clears the saved contact name, phone, and relationship.</div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="ghost" size="sm" onClick={() => setConfirmRemoveEmergency(false)} disabled={saving}>Cancel</Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="border-status-error/25 text-status-error hover:bg-status-error/[0.06]"
                            icon={saving ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                            onClick={removeEmergencyContact}
                            disabled={saving}
                          >
                            Remove
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setConfirmRemoveEmergency(true)}
                        className="inline-flex items-center gap-2 text-[13px] font-semibold text-status-error transition hover:text-status-error/80"
                      >
                        <Trash2 size={14} />
                        Remove Emergency Contact
                      </button>
                    )}
                  </div>
                )}
              </div>
            ) : hasSavedEmergencyContact ? (
              <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                <ProfileInfoItem label="Contact Name" value={profile.emergency_contact_name} />
                <ProfileInfoItem label="Contact Phone" value={profile.emergency_contact_phone} />
                <ProfileInfoItem label="Relationship" value={profile.emergency_contact_relation} />
              </div>
            ) : (
              <div className="flex min-h-[120px] flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--color-brand-orange)]/30 bg-[var(--color-brand-orange)]/[0.025] px-5 text-center">
                <div className="text-[13px] text-gray-500">No emergency contact added yet.</div>
                {canEditProfile && <button type="button" onClick={() => openProfileSection('profile-emergency')} className="mt-2 text-[13px] font-bold text-[var(--color-brand-orange)] hover:underline">+ Add contact</button>}
              </div>
            )}
          </div>
        </Card>
        </div>

        <div className="space-y-5 xl:col-span-2">
        <Card id="profile-employment">
          <div className="flex items-center gap-3 px-6 pt-6">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-olive/10 text-olive"><Briefcase size={16} /></div>
            <div className="text-[15px] font-bold text-[var(--color-brand-navy)]">Employment Details</div>
          </div>
          <div className="px-6 pb-4 pt-3">
            <EmploymentRow label="Department" value={profile.department} />
            <EmploymentRow label="Designation" value={profile.designation} />
            <EmploymentRow label="Role" value={roleLabels[profile.role] || profile.role} />
            <EmploymentRow label="Reporting Manager" value={profile.reporting_manager} />
            <EmploymentRow label="Work Arrangement" value={profile.work_location} />
            <EmploymentRow label="Work Location" value={formatWorkLocation(profile.work_city, profile.work_state, profile.work_country)} />
            <EmploymentRow label="Employment Type" value={formatAllocationStatus(profile.workforce_type)} />
            <EmploymentRow label="Joining Date" value={formatDate(profile.joining_date)} />
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3 px-6 pt-6">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-500"><KeyRound size={16} /></div>
            <div className="text-[15px] font-bold text-[var(--color-brand-navy)]">Account &amp; Security</div>
          </div>
          <div className="px-6 pb-5 pt-3">
            <EmploymentRow label="Username" value={profile.work_email} />
            <EmploymentRow label="Last Login" value={formatDateTime(profile.last_login_at) || 'Not recorded'} />
            <EmploymentRow label="Two-Factor Authentication" value={<span className={profile.mfa_enabled ? 'text-status-success' : 'text-status-warning'}>{profile.mfa_enabled ? 'Enabled' : 'Not enabled'}</span>} />
            {isOwnProfile && (
              <Button className="mt-4" variant="ghost" icon={passwordResetLoading ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />} onClick={requestPasswordReset} disabled={passwordResetLoading}>
                {passwordResetLoading ? 'Sending reset link...' : 'Change password'}
              </Button>
            )}
          </div>
        </Card>
        </div>
      </div>
      )}

      {activeTab === 'organization' && (
        <OrganizationChart initialView="my-line" focusedEmployeeId={profile.id} />
      )}

      {activeTab === 'allocations' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card className="p-5 md:col-span-2">
              <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Allocation Mix</div>
              <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
                <div className="text-2xl font-bold text-[var(--color-brand-navy)]">
                  {derivedAllocationSummary.total_active_allocation_percentage}% allocated
                </div>
                <div className="text-sm font-bold text-status-success">
                  {derivedAllocationSummary.available_capacity_percentage}% available
                </div>
              </div>
              <AllocationMixBar allocated={derivedAllocationSummary.total_active_allocation_percentage} className="mt-4" />
            </Card>
            <Card className="p-5">
              <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Active Projects</div>
              <div className="mt-2 text-2xl font-bold text-[var(--color-brand-navy)]">{derivedAllocationSummary.active_projects_count}</div>
            </Card>
            <Card className="p-5">
              <div className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Next End Date</div>
              <div className="mt-2 text-2xl font-bold text-[var(--color-brand-navy)]">
                {derivedAllocationSummary.next_end_date ? formatShortDate(derivedAllocationSummary.next_end_date) : 'None'}
              </div>
            </Card>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[12px] font-bold uppercase tracking-wide text-gray-400">Allocation Status</span>
            <Badge variant={allocationStatusVariant[derivedAllocationSummary.allocation_status] || 'neutral'}>
              {formatAllocationStatus(derivedAllocationSummary.allocation_status)}
            </Badge>
          </div>

          <Card>
            <div className="px-6 py-4 border-b border-[var(--color-border)]">
              <div className="text-[13px] font-bold text-[var(--color-brand-navy)]">Allocations</div>
            </div>
          {allocationsLoading ? (
            <div className="flex items-center justify-center px-6 py-16 text-sm text-gray-400">
              Loading allocations...
            </div>
          ) : allocationsError ? (
            <div className="px-6 py-10 text-center">
              <div className="text-[15px] font-semibold text-[var(--color-brand-navy)] mb-1">Allocations unavailable</div>
              <div className="text-sm text-gray-500">{allocationsError}</div>
            </div>
          ) : allocationRows.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-olive/10 text-olive">
                <Briefcase size={20} />
              </div>
              <div className="text-[15px] font-semibold text-[var(--color-brand-navy)]">No allocations found</div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-left">
                <thead className="bg-warm-bg">
                  <tr className="text-[11px] font-bold uppercase tracking-wide text-gray-400">
                    <th className="px-6 py-3">Project Code</th>
                    <th className="px-4 py-3">Project Name</th>
                    <th className="px-4 py-3">Manager</th>
                    <th className="px-4 py-3">Project Location</th>
                    <th className="px-4 py-3">Allocation %</th>
                    <th className="px-4 py-3">Start Date</th>
                    <th className="px-4 py-3">End / Review Date</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {allocationRows.map((allocation) => {
                    const rowStatus = allocation.isDerivedAvailability ? allocation.status : effectiveAllocationStatus(allocation);
                    return (
                    <tr key={allocation.id} className="border-t border-[var(--color-border)] text-[14px] text-[var(--color-brand-navy)]">
                      <td className="px-6 py-4 font-semibold">{projectCode(allocation)}</td>
                      <td className="px-4 py-4">
                        <div className="font-semibold">{projectDisplayName(allocation)}</div>
                        <div className="text-xs text-gray-500">{allocation.allocation_role}</div>
                      </td>
                      <td className="px-4 py-4 text-gray-600">{allocation.manager_name || 'Not assigned'}</td>
                      <td className="px-4 py-4 text-gray-600">{allocation.project_location || 'Remote'}</td>
                      <td className="px-4 py-4 font-semibold">{allocation.allocation_percentage}%</td>
                      <td className="px-4 py-4 text-gray-600">{formatDate(allocation.start_date) || '-'}</td>
                      <td className="px-4 py-4 text-gray-600">{formatDate(allocation.end_date) || '-'}</td>
                      <td className="px-4 py-4">
                        <Badge variant={allocationStatusVariant[rowStatus] || 'neutral'}>
                          {formatAllocationStatus(rowStatus)}
                        </Badge>
                      </td>
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

      {activeTab === 'activity' && (
        <AuditTimeline entityType="employee" entityId={profile.id} maxItems={12} />
      )}

      {activeTab === 'career' && (
        <CareerProfilePanel
          employee={{
            id: profile.id,
            name: `${profile.first_name} ${profile.last_name}`.trim(),
            email: profile.work_email,
            designation: profile.designation,
            department: profile.department,
          }}
          editable={!employeeIdParam || profile.id === user?.id || profile.work_email === user?.email}
        />
      )}
    </div>
  );
}

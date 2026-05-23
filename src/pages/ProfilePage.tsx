import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Mail, Phone, MapPin, Calendar, Briefcase, Building2, User, Shield,
  Heart, Home, Clock, Pencil, Camera, Trash2, Save, X, Loader2,
} from 'lucide-react';
import { Card, Badge, Button } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = 'http://localhost:8000/api/v1';

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
  work_location: string;
}

const roleLabels: Record<string, string> = {
  super_admin: 'Super Admin',
  hr_admin: 'HR Admin',
  manager: 'Manager',
  employee: 'Employee',
  trainee: 'Trainee',
};

const statusVariant: Record<string, 'success' | 'warning' | 'error' | 'neutral' | 'info'> = {
  active: 'success',
  inactive: 'neutral',
  onboarding: 'info',
  offboarding: 'warning',
};

const GENDER_OPTIONS = [
  { value: '', label: 'Select gender' },
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'non_binary', label: 'Non-binary' },
  { value: 'prefer_not_to_say', label: 'Prefer not to say' },
];

const LOCATION_OPTIONS = ['Onshore', 'Offshore', 'Remote', 'Hybrid'];

function makeInitials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').toUpperCase().slice(0, 2);
}

function splitName(fullName: string) {
  const parts = fullName.trim().split(/\s+/);
  const firstName = parts.shift() || '';
  return {
    first_name: firstName,
    last_name: parts.join(' ') || firstName,
  };
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
    work_location: profile.work_location || '',
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

function normalizeRole(role: string | undefined) {
  return role === 'Global Access' ? 'super_admin' : role || '';
}

function validateForm(form: ProfileForm) {
  const nextErrors: Partial<Record<keyof ProfileForm | 'image', string>> = {};
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const phonePattern = /^[0-9+()\-\s]{7,20}$/;
  const phoneDigits = form.phone.replace(/\D/g, '');
  const emergencyDigits = form.emergency_contact_phone.replace(/\D/g, '');

  if (!form.full_name.trim()) nextErrors.full_name = 'Full name is required';
  if (form.full_name.trim().split(/\s+/).length < 2) nextErrors.full_name = 'Enter first and last name';
  if (form.personal_email && !emailPattern.test(form.personal_email)) nextErrors.personal_email = 'Enter a valid email';
  if (!form.phone.trim()) nextErrors.phone = 'Phone number is required';
  if (form.phone && (!phonePattern.test(form.phone) || phoneDigits.length < 7)) nextErrors.phone = 'Enter a valid phone number';
  if (!form.work_location.trim()) nextErrors.work_location = 'Work location is required';
  if (form.emergency_contact_phone && (!phonePattern.test(form.emergency_contact_phone) || emergencyDigits.length < 7)) {
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
    <div className="flex items-start gap-3 py-3 border-b border-[#E5E7EB] last:border-b-0">
      <span className="text-gray-400 mt-0.5 shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-gray-400 font-medium uppercase tracking-wider mb-0.5">{label}</div>
        <div className="text-[14px] text-[#2F3437] font-medium break-words">{value || '—'}</div>
      </div>
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
    'w-full rounded-xl text-[14px] font-medium bg-warm-bg border text-[#2F3437]',
    'outline-none transition-all duration-150 focus:border-olive/40 focus:ring-2 focus:ring-olive/10',
    error ? 'border-status-error/40' : 'border-[#E5E7EB]',
    textarea ? 'px-3.5 py-3 min-h-[94px] resize-none' : 'px-3.5 py-2.5'
  );

  return (
    <div>
      <label className="block text-[13px] font-semibold text-[#2F3437] mb-1.5">{label}</label>
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

  const loadProfile = async () => {
    if (!user?.email) {
      setLoading(false);
      setError('No email found');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/auth/me/${encodeURIComponent(user.email)}`);
      const data = await res.json();
      if (data.success && data.employee) {
        setProfile(data.employee);
        setForm(profileToForm(data.employee));
      } else {
        setError(data.message || 'Profile not found');
      }
    } catch {
      setError('Cannot connect to server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, [user?.email]);

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

  const updateForm = (key: keyof ProfileForm, value: string) => {
    setForm((current) => current ? { ...current, [key]: value } : current);
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const startEdit = () => {
    if (!profile) return;
    setForm(profileToForm(profile));
    setImageFile(null);
    setImagePreview(null);
    setRemoveImage(false);
    setErrors({});
    setEditMode(true);
  };

  const cancelEdit = () => {
    if (profile) setForm(profileToForm(profile));
    setImageFile(null);
    setImagePreview(null);
    setRemoveImage(false);
    setErrors({});
    setEditMode(false);
  };

  const chooseImage = (file: File | undefined) => {
    if (!file) return;
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
    if (imagePreview?.startsWith('blob:')) URL.revokeObjectURL(imagePreview);
    setImageFile(null);
    setImagePreview(null);
    setRemoveImage(true);
    setErrors((current) => ({ ...current, image: undefined }));
  };

  const saveProfile = async () => {
    if (!profile || !form || !dirty) return;
    const nextErrors = validateForm(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    const nameParts = splitName(form.full_name);
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
        ...nameParts,
        personal_email: form.personal_email || null,
        phone: form.phone,
        date_of_birth: form.date_of_birth || null,
        gender: form.gender || null,
        current_address: form.current_address || null,
        emergency_contact_name: form.emergency_contact_name || null,
        emergency_contact_phone: form.emergency_contact_phone || null,
        emergency_contact_relation: form.emergency_contact_relation || null,
        work_location: form.work_location,
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
      setEditMode(false);
      updateUser({
        name: `${nextProfile.first_name} ${nextProfile.last_name}`.trim(),
        initials: makeInitials(`${nextProfile.first_name} ${nextProfile.last_name}`),
        profileImageUrl: nextProfile.profile_image_url || null,
      });
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
          <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">My Profile</h1>
          <p className="text-sm text-gray-500">Your personal and employment information</p>
        </div>
        <Card className="flex items-center justify-center py-20">
          <div className="text-center">
            <div className="text-[15px] font-semibold text-[#2F3437] mb-1">Profile unavailable</div>
            <div className="text-sm text-gray-500">{error || 'Profile data is only available for registered employees.'}</div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">My Profile</h1>
        <p className="text-sm text-gray-500">Your personal and employment information</p>
      </div>

      <Card className="mb-5">
        <div className="px-6 py-6 flex flex-col gap-5 border-b border-[#E5E7EB] md:flex-row md:items-center md:justify-between">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="relative w-24 h-24 shrink-0">
              <button
                type="button"
                disabled={!editMode}
                onClick={() => editMode && fileInputRef.current?.click()}
                className={cn(
                  'w-24 h-24 rounded-full overflow-hidden bg-olive text-white flex items-center justify-center text-2xl font-bold',
                  'ring-4 ring-olive/10 transition-all duration-200',
                  editMode && 'hover:ring-olive/25 cursor-pointer'
                )}
              >
                {currentImage ? (
                  <img src={currentImage} alt="Profile" className="w-full h-full object-cover" />
                ) : (
                  initials
                )}
                {editMode && (
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
              {editMode && currentImage && (
                <button
                  type="button"
                  onClick={handleRemoveImage}
                  title="Remove photo"
                  className="absolute -right-1 -bottom-1 w-8 h-8 rounded-full bg-warm-card border border-[#E5E7EB] text-status-error flex items-center justify-center shadow-card hover:bg-status-error/5 transition-colors"
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>

            <div className="min-w-0">
              <div className="text-xl font-bold text-[#2F3437] mb-0.5">{fullName}</div>
              <div className="text-[14px] text-gray-500 mb-2">{profile.designation || roleLabels[profile.role] || profile.role}</div>
              <div className="flex flex-wrap gap-2">
                <Badge variant={statusVariant[profile.employment_status] || 'neutral'}>
                  {profile.employment_status}
                </Badge>
                <Badge variant="olive">{roleLabels[profile.role] || profile.role}</Badge>
                <Badge variant="neutral">{profile.workforce_type}</Badge>
              </div>
              {errors.image && <div className="mt-2 text-[12px] font-medium text-status-error">{errors.image}</div>}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {editMode ? (
              <>
                <Button variant="ghost" icon={<X size={14} />} onClick={cancelEdit} disabled={saving}>Cancel</Button>
                <Button icon={saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} onClick={saveProfile} disabled={!dirty || saving}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </>
            ) : (
              <Button icon={<Pencil size={14} />} onClick={startEdit}>Edit Profile</Button>
            )}
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Card>
          <div className="px-6 py-4 border-b border-[#E5E7EB]">
            <div className="text-[13px] font-bold text-[#2F3437]">Personal Information</div>
          </div>
          <div className="px-6 py-2">
            {editMode ? (
              <div className="grid grid-cols-1 gap-4 py-4 md:grid-cols-2">
                <Field label="Full Name" value={form.full_name} onChange={(v) => updateForm('full_name', v)} error={errors.full_name} />
                <Field label="Personal Email" value={form.personal_email} onChange={(v) => updateForm('personal_email', v)} error={errors.personal_email} type="email" />
                <Field label="Phone Number" value={form.phone} onChange={(v) => updateForm('phone', v)} error={errors.phone} />
                <Field label="Date of Birth" value={form.date_of_birth} onChange={(v) => updateForm('date_of_birth', v)} type="date" />
                <Field label="Gender" value={form.gender} onChange={(v) => updateForm('gender', v)} options={GENDER_OPTIONS} />
                <div className="md:col-span-2">
                  <Field label="Address" value={form.current_address} onChange={(v) => updateForm('current_address', v)} textarea />
                </div>
              </div>
            ) : (
              <>
                <InfoRow icon={<Mail size={15} />} label="Work Email" value={profile.work_email} />
                <InfoRow icon={<Mail size={15} />} label="Personal Email" value={profile.personal_email} />
                <InfoRow icon={<Phone size={15} />} label="Phone" value={profile.phone ? `${profile.country_code || ''} ${profile.phone}` : null} />
                <InfoRow icon={<Calendar size={15} />} label="Date of Birth" value={formatDate(profile.date_of_birth)} />
                <InfoRow icon={<User size={15} />} label="Gender" value={profile.gender ? profile.gender.replace(/_/g, ' ') : null} />
                <InfoRow icon={<Home size={15} />} label="Address" value={profile.current_address} />
              </>
            )}
          </div>
        </Card>

        <Card>
          <div className="px-6 py-4 border-b border-[#E5E7EB]">
            <div className="text-[13px] font-bold text-[#2F3437]">Employment Details</div>
          </div>
          <div className="px-6 py-2">
            <InfoRow icon={<Building2 size={15} />} label="Department" value={profile.department} />
            <InfoRow icon={<Briefcase size={15} />} label="Designation" value={profile.designation} />
            <InfoRow icon={<Shield size={15} />} label="Role" value={roleLabels[profile.role] || profile.role} />
            <InfoRow icon={<User size={15} />} label="Reporting Manager" value={profile.reporting_manager} />
            {editMode ? (
              <div className="py-3 border-b border-[#E5E7EB]">
                <Field label="Work Location" value={form.work_location} onChange={(v) => updateForm('work_location', v)} error={errors.work_location} options={LOCATION_OPTIONS} />
              </div>
            ) : (
              <InfoRow icon={<MapPin size={15} />} label="Work Location" value={profile.work_location} />
            )}
            <InfoRow icon={<Calendar size={15} />} label="Joining Date" value={formatDate(profile.joining_date)} />
          </div>
        </Card>

        <Card>
          <div className="px-6 py-4 border-b border-[#E5E7EB]">
            <div className="text-[13px] font-bold text-[#2F3437]">Emergency Contact</div>
          </div>
          <div className="px-6 py-2">
            {editMode ? (
              <div className="grid grid-cols-1 gap-4 py-4 md:grid-cols-2">
                <Field label="Contact Name" value={form.emergency_contact_name} onChange={(v) => updateForm('emergency_contact_name', v)} />
                <Field label="Contact Phone" value={form.emergency_contact_phone} onChange={(v) => updateForm('emergency_contact_phone', v)} error={errors.emergency_contact_phone} />
                <div className="md:col-span-2">
                  <Field label="Relationship" value={form.emergency_contact_relation} onChange={(v) => updateForm('emergency_contact_relation', v)} />
                </div>
              </div>
            ) : (
              <>
                <InfoRow icon={<Heart size={15} />} label="Contact Name" value={profile.emergency_contact_name} />
                <InfoRow icon={<Phone size={15} />} label="Contact Phone" value={profile.emergency_contact_phone} />
                <InfoRow icon={<User size={15} />} label="Relationship" value={profile.emergency_contact_relation} />
              </>
            )}
          </div>
        </Card>

        <Card>
          <div className="px-6 py-4 border-b border-[#E5E7EB]">
            <div className="text-[13px] font-bold text-[#2F3437]">Account Information</div>
          </div>
          <div className="px-6 py-2">
            <InfoRow icon={<Shield size={15} />} label="Account Status" value={profile.is_active ? 'Active' : 'Deactivated'} />
            <InfoRow icon={<Clock size={15} />} label="Member Since" value={formatDate(profile.created_at)} />
            <InfoRow icon={<Clock size={15} />} label="Last Updated On" value={formatDate(profile.last_updated_at)} />
            <InfoRow icon={<User size={15} />} label="Updated By" value={profile.updated_by} />
          </div>
        </Card>
      </div>
    </div>
  );
}

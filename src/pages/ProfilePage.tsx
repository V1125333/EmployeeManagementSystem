import { useState, useEffect } from 'react';
import {
  Mail, Phone, MapPin, Calendar, Briefcase, Building2, User,
  Shield, UserCircle, AlertCircle, Heart, Lock, Edit2, X, Check, Loader, ChevronDown,
} from 'lucide-react';
import { Card, CardHeader, Badge, Button } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = 'http://localhost:8000/api/v1';

const GENDER_OPTIONS = ['Male', 'Female', 'Non-Binary', 'Prefer not to say'];

// ─── Types ───
interface EmployeeDetail {
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
  location: string | null;
  joining_date: string | null;
  date_of_exit: string | null;
  inactive_reason: string | null;
  reporting_manager: string;
  onboarding_type: string | null;
  profile_image_url: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_contact_relation: string | null;
  current_address: string | null;
  permanent_address: string | null;
  notes: string | null;
  is_active: boolean;
  is_first_login: boolean;
  setup_code: string | null;
  created_at: string;
}

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

// ─── Editable Info Row ───
function EditableInfoRow({
  icon,
  label,
  value,
  onChange,
  isEditing,
  isRestricted,
  type = 'text',
  tooltip,
  options,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | null | undefined;
  onChange?: (v: string) => void;
  isEditing?: boolean;
  isRestricted?: boolean;
  type?: 'text' | 'email' | 'date' | 'textarea' | 'select';
  tooltip?: string;
  options?: string[];
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const displayValue = value || '—';

  return (
    <div className="flex items-start gap-3 py-3">
      <span className="text-gray-400 mt-0.5 shrink-0 relative group">
        {icon}
        {tooltip && (
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-[11px] rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
            {tooltip}
          </div>
        )}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider mb-0.5 flex items-center gap-1">
          {label}
          {isRestricted && <Lock size={10} className="text-status-warning" />}
        </div>
        {isEditing && !isRestricted ? (
          type === 'select' && options ? (
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="w-full px-2 py-1.5 text-[14px] bg-hover-bg border border-[#E5E7EB] rounded-lg text-[#2F3437] placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-olive/50 flex items-center justify-between"
              >
                <span>{value || 'Select...'}</span>
                <ChevronDown size={14} className={cn('transition-transform', dropdownOpen && 'rotate-180')} />
              </button>
              {dropdownOpen && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setDropdownOpen(false)} />
                  <div className="absolute top-full left-0 right-0 mt-1 z-40 bg-warm-card border border-[#E5E7EB] rounded-lg shadow-card-md py-1">
                    {options.map((opt) => (
                      <button
                        key={opt}
                        onClick={() => {
                          onChange?.(opt);
                          setDropdownOpen(false);
                        }}
                        className={cn(
                          'w-full text-left px-3 py-2 text-[14px] transition-colors',
                          opt === value ? 'bg-olive/10 text-olive font-medium' : 'text-[#2F3437] hover:bg-hover-bg'
                        )}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : type === 'textarea' ? (
            <textarea
              value={value || ''}
              onChange={(e) => onChange?.(e.target.value)}
              className="w-full px-2 py-1.5 text-[14px] bg-hover-bg border border-[#E5E7EB] rounded-lg text-[#2F3437] placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-olive/50 resize-none"
              rows={3}
              placeholder={`Enter ${label.toLowerCase()}`}
            />
          ) : (
            <input
              type={type}
              value={value || ''}
              onChange={(e) => onChange?.(e.target.value)}
              className="w-full px-2 py-1.5 text-[14px] bg-hover-bg border border-[#E5E7EB] rounded-lg text-[#2F3437] placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-olive/50"
              placeholder={`Enter ${label.toLowerCase()}`}
            />
          )
        ) : (
          <div
            className={cn(
              'text-[14px] font-medium',
              isRestricted ? 'text-gray-400 italic' : 'text-[#2F3437]'
            )}
          >
            {displayValue}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Section divider ───
function SectionDivider({ label }: { label: string }) {
  return (
    <div className="text-[11px] font-bold text-gray-400 tracking-widest uppercase pt-1 pb-2 border-b border-[#E5E7EB] mb-1">
      {label}
    </div>
  );
}

// ─── Main Page ───
export function ProfilePage() {
  const { user } = useAuth();
  const [employee, setEmployee] = useState<EmployeeDetail | null>(null);
  const [editData, setEditData] = useState<Partial<EmployeeDetail>>({});
  const [changedFields, setChangedFields] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isUploadingPicture, setIsUploadingPicture] = useState(false);

  const isSuperAdmin = user?.role === 'super_admin';

  useEffect(() => {
    if (!user?.id) {
      setLoading(false);
      return;
    }

    const fetchProfile = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/employees/${user.id}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: EmployeeDetail = await res.json();
        setEmployee(data);
      } catch {
        setError('Could not load profile data. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [user?.id]);

  const handleEditChange = (field: keyof EmployeeDetail, value: string) => {
    setEditData((prev) => ({ ...prev, [field]: value }));
    setChangedFields((prev) => new Set(prev).add(field));
  };

  const handleStartEdit = () => {
    if (employee) {
      setEditData(employee);
      setChangedFields(new Set());
      setIsEditing(true);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditData({});
    setChangedFields(new Set());
    setSaveMessage(null);
  };

  const handleSave = async () => {
    if (!employee || !user?.id) return;

    setIsSaving(true);
    setSaveMessage(null);

    try {
      // Only send fields that were actually changed
      const dataToSend: Record<string, any> = {};
      changedFields.forEach((field) => {
        dataToSend[field] = editData[field as keyof EmployeeDetail];
      });

      console.log('Saving changed fields:', dataToSend);
      console.log('User ID:', user.id, 'User Role:', user.role);

      const res = await fetch(`${API_BASE}/employees/${employee.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'x-user-id': user.id,
          'x-user-role': user.role,
        },
        body: JSON.stringify(dataToSend),
      });

      const responseText = await res.text();
      console.log('Response status:', res.status, 'Response:', responseText);

      if (!res.ok) {
        try {
          const errData = JSON.parse(responseText);
          throw new Error(errData.detail || `HTTP ${res.status}`);
        } catch {
          throw new Error(`HTTP ${res.status}: ${responseText}`);
        }
      }

      const data = JSON.parse(responseText);
      // Update only the changed fields in the employee object
      setEmployee((prev) => {
        if (!prev) return null;
        const updated = { ...prev };
        changedFields.forEach((field) => {
          (updated as any)[field] = editData[field as keyof EmployeeDetail];
        });
        return updated;
      });
      setIsEditing(false);
      setChangedFields(new Set());
      setSaveMessage({ type: 'success', text: 'Profile updated successfully!' });
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (err) {
      console.error('Save error:', err);
      setSaveMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to save changes',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleProfilePictureUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !employee || !user?.id) return;

    setIsUploadingPicture(true);
    setSaveMessage(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_BASE}/employees/${employee.id}/upload-profile-picture`, {
        method: 'POST',
        headers: {
          'x-user-id': user.id,
          'x-user-role': user.role,
        },
        body: formData,
      });

      const responseText = await res.text();

      if (!res.ok) {
        try {
          const errData = JSON.parse(responseText);
          throw new Error(errData.detail || `HTTP ${res.status}`);
        } catch {
          throw new Error(`HTTP ${res.status}: ${responseText}`);
        }
      }

      const data = JSON.parse(responseText);
      setEmployee((prev) => (prev ? { ...prev, profile_image_url: data.profile_image_url } : null));
      setSaveMessage({ type: 'success', text: 'Profile picture updated successfully!' });
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (err) {
      console.error('Upload error:', err);
      setSaveMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to upload picture',
      });
    } finally {
      setIsUploadingPicture(false);
      // Reset file input
      e.target.value = '';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="text-sm text-gray-400">Loading profile...</div>
      </div>
    );
  }

  if (error || !employee) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">My Profile</h1>
          <p className="text-sm text-gray-500">Your personal and employment information</p>
        </div>
        <Card>
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <AlertCircle size={32} className="text-gray-300" />
            <div className="text-[15px] font-semibold text-[#2F3437]">Profile unavailable</div>
            <div className="text-sm text-gray-500 text-center max-w-xs">
              {error || 'Profile data is only available for registered employees.'}
            </div>
          </div>
        </Card>
      </div>
    );
  }

  const fullName = `${employee.first_name} ${employee.last_name}`;
  const initials = `${employee.first_name[0]}${employee.last_name[0]}`.toUpperCase();

  const formatDate = (d: string | null) =>
    d ? new Date(d).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : null;

  const hasEmergencyContact =
    employee.emergency_contact_name ||
    employee.emergency_contact_phone ||
    employee.emergency_contact_relation;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Page header with edit button */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">My Profile</h1>
          <p className="text-sm text-gray-500">Your personal and employment information</p>
        </div>
        {!isEditing ? (
          <Button
            variant="primary"
            size="sm"
            icon={<Edit2 size={14} />}
            onClick={handleStartEdit}
          >
            Edit Profile
          </Button>
        ) : (
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              icon={<X size={14} />}
              onClick={handleCancel}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={isSaving ? <Loader size={14} className="animate-spin" /> : <Check size={14} />}
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        )}
      </div>

      {/* Success/Error message */}
      {saveMessage && (
        <Card
          className={cn(
            'mb-5 px-5 py-3 flex items-center gap-3',
            saveMessage.type === 'success' ? 'bg-status-success/10' : 'bg-status-error/10'
          )}
        >
          <div
            className={cn(
              'text-sm font-medium',
              saveMessage.type === 'success' ? 'text-status-success' : 'text-status-error'
            )}
          >
            {saveMessage.text}
          </div>
        </Card>
      )}

      {/* Profile hero card */}
      <Card className="mb-5">
        <div className="px-7 py-6 flex items-center gap-5">
          {/* Avatar with upload */}
          <div className="relative group shrink-0">
            <input
              id="profile-pic-input"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              onChange={handleProfilePictureUpload}
              disabled={isUploadingPicture}
              className="hidden"
            />
            {employee.profile_image_url && employee.profile_image_url.startsWith('data:') ? (
              <img
                src={employee.profile_image_url}
                alt={fullName}
                className="w-20 h-20 rounded-2xl object-cover shrink-0"
              />
            ) : (
              <div className="w-20 h-20 rounded-2xl bg-olive flex items-center justify-center text-white text-2xl font-bold shrink-0">
                {initials}
              </div>
            )}
            <label
              htmlFor="profile-pic-input"
              className={cn(
                'absolute inset-0 rounded-2xl bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer flex items-center justify-center',
                isUploadingPicture && 'opacity-100 cursor-not-allowed'
              )}
            >
              {isUploadingPicture ? (
                <Loader size={20} className="text-white animate-spin" />
              ) : (
                <span className="text-white text-xs font-semibold text-center px-2">Upload Photo</span>
              )}
            </label>
          </div>

          {/* Name + meta */}
          <div className="flex-1 min-w-0">
            <div className="text-xl font-bold text-[#2F3437] tracking-tight">{fullName}</div>
            <div className="text-[14px] text-gray-500 mt-0.5">
              {employee.designation || roleLabels[employee.role] || employee.role}
            </div>
            <div className="text-[13px] text-gray-400 mt-0.5">{employee.department}</div>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <Badge variant={statusVariant[employee.employment_status] || 'neutral'}>
                {employee.employment_status}
              </Badge>
              <Badge variant="sage">{roleLabels[employee.role] || employee.role}</Badge>
              {employee.workforce_type && (
                <Badge variant="neutral">{employee.workforce_type}</Badge>
              )}
            </div>
          </div>

          {/* Employee ID chip */}
          <div className="text-right shrink-0">
            <div className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider mb-1">
              Employee ID
            </div>
            <div className="text-[13px] font-mono text-[#2F3437] bg-warm-bg border border-[#E5E7EB] rounded-lg px-3 py-1.5">
              {employee.id.slice(0, 8).toUpperCase()}
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Personal Info */}
        <Card>
          <CardHeader title="Personal Information" icon={<UserCircle size={15} />} />
          <div className="px-5 py-2 divide-y divide-[#F0F0EC]">
            <EditableInfoRow
              icon={<Mail size={15} />}
              label="Work Email"
              value={(isEditing ? editData.work_email : employee.work_email) || '—'}
              isEditing={false}
              isRestricted={true}
              tooltip="Work email cannot be changed"
            />
            <EditableInfoRow
              icon={<Mail size={15} />}
              label="Personal Email"
              value={isEditing ? editData.personal_email : employee.personal_email}
              onChange={(v) => handleEditChange('personal_email', v)}
              isEditing={isEditing}
              type="email"
            />
            <EditableInfoRow
              icon={<Phone size={15} />}
              label="Phone"
              value={
                isEditing
                  ? editData.phone
                  : employee.phone
                    ? `${employee.country_code || ''} ${employee.phone}`.trim()
                    : null
              }
              onChange={(v) => handleEditChange('phone', v)}
              isEditing={isEditing}
            />
            <EditableInfoRow
              icon={<Calendar size={15} />}
              label="Date of Birth"
              value={
                isEditing && editData.date_of_birth
                  ? editData.date_of_birth
                  : formatDate(employee.date_of_birth)
              }
              onChange={(v) => handleEditChange('date_of_birth', v)}
              isEditing={isEditing && isSuperAdmin}
              isRestricted={!isSuperAdmin}
              type="date"
              tooltip={!isSuperAdmin ? 'Only super admin can edit' : undefined}
            />
            <EditableInfoRow
              icon={<User size={15} />}
              label="Gender"
              value={isEditing ? editData.gender : employee.gender}
              onChange={(v) => handleEditChange('gender', v)}
              isEditing={isEditing}
              type="select"
              options={GENDER_OPTIONS}
            />
            <EditableInfoRow
              icon={<MapPin size={15} />}
              label="Current Address"
              value={isEditing ? editData.current_address : employee.current_address}
              onChange={(v) => handleEditChange('current_address', v)}
              isEditing={isEditing}
              type="textarea"
            />
            {(isEditing || employee.permanent_address) && (
              <EditableInfoRow
                icon={<MapPin size={15} />}
                label="Permanent Address"
                value={isEditing ? editData.permanent_address : employee.permanent_address}
                onChange={(v) => handleEditChange('permanent_address', v)}
                isEditing={isEditing}
                type="textarea"
              />
            )}
          </div>
        </Card>

        {/* Employment Details */}
        <Card>
          <CardHeader title="Employment Details" icon={<Briefcase size={15} />} />
          <div className="px-5 py-2 divide-y divide-[#F0F0EC]">
            <EditableInfoRow
              icon={<Building2 size={15} />}
              label="Department"
              value={isEditing ? editData.department : employee.department}
              onChange={(v) => handleEditChange('department', v)}
              isEditing={isEditing && isSuperAdmin}
              isRestricted={!isSuperAdmin}
            />
            <EditableInfoRow
              icon={<Briefcase size={15} />}
              label="Designation"
              value={isEditing ? editData.designation : employee.designation}
              onChange={(v) => handleEditChange('designation', v)}
              isEditing={isEditing && isSuperAdmin}
              isRestricted={!isSuperAdmin}
            />
            <EditableInfoRow
              icon={<Shield size={15} />}
              label="Role"
              value={roleLabels[(isEditing ? editData.role : employee.role) || ''] || (isEditing ? editData.role : employee.role)}
              isEditing={false}
              isRestricted={true}
            />
            <EditableInfoRow
              icon={<User size={15} />}
              label="Workforce Type"
              value={isEditing ? editData.workforce_type : employee.workforce_type}
              onChange={(v) => handleEditChange('workforce_type', v)}
              isEditing={isEditing && isSuperAdmin}
              isRestricted={!isSuperAdmin}
            />
            <EditableInfoRow
              icon={<MapPin size={15} />}
              label="Work Location"
              value={isEditing ? editData.work_location : employee.work_location}
              onChange={(v) => handleEditChange('work_location', v)}
              isEditing={isEditing && isSuperAdmin}
              isRestricted={!isSuperAdmin}
            />
            <EditableInfoRow
              icon={<User size={15} />}
              label="Reporting Manager"
              value={isEditing ? editData.reporting_manager : employee.reporting_manager}
              onChange={(v) => handleEditChange('reporting_manager', v)}
              isEditing={isEditing && isSuperAdmin}
              isRestricted={!isSuperAdmin}
            />
            <EditableInfoRow
              icon={<Calendar size={15} />}
              label="Joining Date"
              value={
                isEditing && editData.joining_date
                  ? editData.joining_date
                  : formatDate(employee.joining_date)
              }
              onChange={(v) => handleEditChange('joining_date', v)}
              isEditing={isEditing && isSuperAdmin}
              isRestricted={!isSuperAdmin}
              type="date"
            />
            {(isEditing || employee.date_of_exit) && (
              <EditableInfoRow
                icon={<Calendar size={15} />}
                label="Date of Exit"
                value={
                  isEditing && editData.date_of_exit
                    ? editData.date_of_exit
                    : formatDate(employee.date_of_exit)
                }
                onChange={(v) => handleEditChange('date_of_exit', v)}
                isEditing={isEditing && isSuperAdmin}
                isRestricted={!isSuperAdmin}
                type="date"
              />
            )}
            {(isEditing || employee.onboarding_type) && (
              <EditableInfoRow
                icon={<Briefcase size={15} />}
                label="Onboarding Type"
                value={isEditing ? editData.onboarding_type : employee.onboarding_type}
                onChange={(v) => handleEditChange('onboarding_type', v)}
                isEditing={isEditing && isSuperAdmin}
                isRestricted={!isSuperAdmin}
              />
            )}
            {(isEditing || employee.inactive_reason) && (
              <EditableInfoRow
                icon={<AlertCircle size={15} />}
                label="Inactive Reason"
                value={isEditing ? editData.inactive_reason : employee.inactive_reason}
                onChange={(v) => handleEditChange('inactive_reason', v)}
                isEditing={isEditing && isSuperAdmin}
                isRestricted={!isSuperAdmin}
              />
            )}
          </div>
        </Card>
      </div>

      {/* Emergency Contact */}
      {(isEditing || hasEmergencyContact) && (
        <Card className="mt-5">
          <CardHeader title="Emergency Contact" icon={<Heart size={15} />} />
          <div className="px-5 py-2 grid grid-cols-1 gap-y-3 lg:grid-cols-3 lg:gap-x-10">
            <EditableInfoRow
              icon={<User size={15} />}
              label="Name"
              value={isEditing ? editData.emergency_contact_name : employee.emergency_contact_name}
              onChange={(v) => handleEditChange('emergency_contact_name', v)}
              isEditing={isEditing}
            />
            <EditableInfoRow
              icon={<Phone size={15} />}
              label="Phone"
              value={isEditing ? editData.emergency_contact_phone : employee.emergency_contact_phone}
              onChange={(v) => handleEditChange('emergency_contact_phone', v)}
              isEditing={isEditing}
            />
            <EditableInfoRow
              icon={<Heart size={15} />}
              label="Relation"
              value={isEditing ? editData.emergency_contact_relation : employee.emergency_contact_relation}
              onChange={(v) => handleEditChange('emergency_contact_relation', v)}
              isEditing={isEditing}
            />
          </div>
        </Card>
      )}

      {/* Notes */}
      {(isEditing || employee.notes) && (
        <Card className="mt-5">
          <CardHeader title="Additional Notes" icon={<AlertCircle size={15} />} />
          <div className="px-5 py-3">
            <EditableInfoRow
              icon={<AlertCircle size={15} />}
              label="Notes"
              value={isEditing ? editData.notes : employee.notes}
              onChange={(v) => handleEditChange('notes', v)}
              isEditing={isEditing && isSuperAdmin}
              isRestricted={!isSuperAdmin}
              type="textarea"
            />
          </div>
        </Card>
      )}
    </div>
  );
}

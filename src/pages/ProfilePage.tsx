import { useState, useEffect } from 'react';
import {
  Mail, Phone, MapPin, Calendar, Briefcase, Building2, User, Shield,
  Heart, Home, Clock,
} from 'lucide-react';
import { Card, Badge, Avatar } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';

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

function InfoRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | null }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-[#E5E7EB] last:border-b-0">
      <span className="text-gray-400 mt-0.5 shrink-0">{icon}</span>
      <div className="flex-1">
        <div className="text-[11px] text-gray-400 font-medium uppercase tracking-wider mb-0.5">{label}</div>
        <div className="text-[14px] text-[#2F3437] font-medium">{value || '—'}</div>
      </div>
    </div>
  );
}

export function ProfilePage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user?.email) {
      setLoading(false);
      setError('No email found');
      return;
    }

    fetch(`${API_BASE}/auth/me/${user.email}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.success && data.employee) {
          setProfile(data.employee);
        } else {
          setError(data.message || 'Profile not found');
        }
      })
      .catch(() => setError('Cannot connect to server'))
      .finally(() => setLoading(false));
  }, [user]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-gray-400">Loading profile...</div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">My Profile</h1>
          <p className="text-sm text-gray-500">Your personal and employment information</p>
        </div>
        <Card className="flex items-center justify-center py-20">
          <div className="text-center">
            <div className="text-3xl mb-3">👤</div>
            <div className="text-[15px] font-semibold text-[#2F3437] mb-1">Profile unavailable</div>
            <div className="text-sm text-gray-500">{error || 'Profile data is only available for registered employees.'}</div>
          </div>
        </Card>
      </div>
    );
  }

  const fullName = `${profile.first_name} ${profile.last_name}`;
  const initials = `${profile.first_name[0]}${profile.last_name[0]}`.toUpperCase();

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">My Profile</h1>
        <p className="text-sm text-gray-500">Your personal and employment information</p>
      </div>

      {/* Profile Card */}
      <Card className="mb-5">
        <div className="px-6 py-6 flex items-center gap-5 border-b border-[#E5E7EB]">
          <div className="w-20 h-20 rounded-2xl bg-olive flex items-center justify-center text-white text-2xl font-bold">
            {initials}
          </div>
          <div>
            <div className="text-xl font-bold text-[#2F3437] mb-0.5">{fullName}</div>
            <div className="text-[14px] text-gray-500 mb-2">{profile.designation || roleLabels[profile.role] || profile.role}</div>
            <div className="flex gap-2">
              <Badge variant={statusVariant[profile.employment_status] || 'neutral'}>
                {profile.employment_status}
              </Badge>
              <Badge variant="olive">{roleLabels[profile.role] || profile.role}</Badge>
              <Badge variant="neutral">{profile.workforce_type}</Badge>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-5">
        {/* Personal Info */}
        <Card>
          <div className="px-6 py-4 border-b border-[#E5E7EB]">
            <div className="text-[13px] font-bold text-[#2F3437]">Personal Information</div>
          </div>
          <div className="px-6 py-2">
            <InfoRow icon={<Mail size={15} />} label="Work Email" value={profile.work_email} />
            <InfoRow icon={<Mail size={15} />} label="Personal Email" value={profile.personal_email} />
            <InfoRow icon={<Phone size={15} />} label="Phone" value={profile.phone ? `${profile.country_code || ''} ${profile.phone}` : null} />
            <InfoRow icon={<Calendar size={15} />} label="Date of Birth" value={profile.date_of_birth} />
            <InfoRow icon={<User size={15} />} label="Gender" value={profile.gender ? profile.gender.charAt(0).toUpperCase() + profile.gender.slice(1) : null} />
            <InfoRow icon={<Home size={15} />} label="Address" value={profile.current_address} />
          </div>
        </Card>

        {/* Employment Info */}
        <Card>
          <div className="px-6 py-4 border-b border-[#E5E7EB]">
            <div className="text-[13px] font-bold text-[#2F3437]">Employment Details</div>
          </div>
          <div className="px-6 py-2">
            <InfoRow icon={<Building2 size={15} />} label="Department" value={profile.department} />
            <InfoRow icon={<Briefcase size={15} />} label="Designation" value={profile.designation} />
            <InfoRow icon={<Shield size={15} />} label="Role" value={roleLabels[profile.role] || profile.role} />
            <InfoRow icon={<User size={15} />} label="Reporting Manager" value={profile.reporting_manager} />
            <InfoRow icon={<MapPin size={15} />} label="Work Location" value={profile.work_location} />
            <InfoRow icon={<Calendar size={15} />} label="Joining Date" value={profile.joining_date} />
          </div>
        </Card>

        {/* Emergency Contact */}
        <Card>
          <div className="px-6 py-4 border-b border-[#E5E7EB]">
            <div className="text-[13px] font-bold text-[#2F3437]">Emergency Contact</div>
          </div>
          <div className="px-6 py-2">
            <InfoRow icon={<Heart size={15} />} label="Contact Name" value={profile.emergency_contact_name} />
            <InfoRow icon={<Phone size={15} />} label="Contact Phone" value={profile.emergency_contact_phone} />
            <InfoRow icon={<User size={15} />} label="Relationship" value={profile.emergency_contact_relation} />
          </div>
        </Card>

        {/* Account Info */}
        <Card>
          <div className="px-6 py-4 border-b border-[#E5E7EB]">
            <div className="text-[13px] font-bold text-[#2F3437]">Account Information</div>
          </div>
          <div className="px-6 py-2">
            <InfoRow icon={<Shield size={15} />} label="Account Status" value={profile.is_active ? 'Active' : 'Deactivated'} />
            <InfoRow icon={<Clock size={15} />} label="Member Since" value={profile.created_at ? new Date(profile.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : null} />
          </div>
        </Card>
      </div>
    </div>
  );
}

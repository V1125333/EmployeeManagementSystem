import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Bell,
  ChevronRight,
  Eye,
  Globe2,
  Headphones,
  HelpCircle,
  KeyRound,
  LockKeyhole,
  Monitor,
  Moon,
  Palette,
  Save,
  Shield,
  ShieldCheck,
  Sun,
  Upload,
  UserRound,
  X,
} from 'lucide-react';
import { Avatar, Button, Card, CardHeader } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import type { UserPreferences } from '@/hooks/useTheme';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

type SettingsTab = 'profile' | 'general' | 'security' | 'notifications' | 'appearance' | 'privacy' | 'support';

interface LegacySettings {
  mfa_enabled: boolean;
  notification_company_announcements: boolean;
  notification_attendance_reminders: boolean;
  notification_task_assignments: boolean;
  notification_training_notifications: boolean;
  notification_project_allocation_updates: boolean;
  profile_visibility: string;
  phone_visibility: string;
  birthday_visibility: string;
}

interface SettingsProfile {
  id: string;
  first_name: string;
  last_name: string;
  display_name: string;
  work_email: string;
  phone?: string | null;
  country_code?: string | null;
  profile_image_url?: string | null;
  timezone: string;
  date_format: string;
  last_login_at?: string | null;
}

const tabs: { key: SettingsTab; label: string; icon: ReactNode }[] = [
  { key: 'profile', label: 'Profile', icon: <UserRound size={16} /> },
  { key: 'general', label: 'General', icon: <Globe2 size={16} /> },
  { key: 'security', label: 'Security', icon: <Shield size={16} /> },
  { key: 'notifications', label: 'Notifications', icon: <Bell size={16} /> },
  { key: 'appearance', label: 'Appearance', icon: <Palette size={16} /> },
  { key: 'privacy', label: 'Privacy', icon: <Eye size={16} /> },
  { key: 'support', label: 'Support', icon: <Headphones size={16} /> },
];

const dateFormats = ['DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD'];
const languages = [
  { label: 'English (US)', value: 'en-US' },
  { label: 'English (UK)', value: 'en-GB' },
];
const accentOptions = [
  ['olive', '#66785F'],
  ['blue', '#3B82F6'],
  ['indigo', '#6366F1'],
  ['purple', '#8B5CF6'],
  ['emerald', '#10B981'],
  ['rose', '#F43F5E'],
  ['slate', '#64748B'],
];
const timezoneOptions = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Toronto',
  'America/Sao_Paulo',
  'Asia/Kolkata',
  'Asia/Dubai',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Manila',
  'Asia/Seoul',
  'Europe/London',
  'Europe/Berlin',
  'Europe/Paris',
  'Europe/Dublin',
  'Pacific/Auckland',
  'Pacific/Honolulu',
  'Australia/Sydney',
];
const privacyOptions = ['Everyone', 'Managers Only', 'HR Only', 'Private'];

const defaultLegacy: LegacySettings = {
  mfa_enabled: false,
  notification_company_announcements: true,
  notification_attendance_reminders: true,
  notification_task_assignments: true,
  notification_training_notifications: true,
  notification_project_allocation_updates: true,
  profile_visibility: 'Everyone',
  phone_visibility: 'Managers Only',
  birthday_visibility: 'Everyone',
};

function headersFor(user: ReturnType<typeof useAuth>['user']) {
  return {
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': user?.role || '',
    'x-user-name': user?.name || '',
  };
}

function isAdminRole(role?: string) {
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes((role || '').toLowerCase().replace(/\s+/g, '_'));
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
}

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold text-gray-500">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-xs text-gray-400">{hint}</span>}
    </label>
  );
}

function inputClass() {
  return 'w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm font-medium text-[#2F3437] outline-none transition-colors focus:border-accent focus:ring-2 focus:ring-accent-light';
}

function SelectField({ value, onChange, options }: { value: string; onChange: (value: string) => void; options: string[] }) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)} className={inputClass()}>
      {options.map((option) => <option key={option} value={option}>{option}</option>)}
    </select>
  );
}

function SearchableTimezone({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [query, setQuery] = useState('');
  const filtered = timezoneOptions.filter((item) => item.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <div className="space-y-2">
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search timezones..." className={inputClass()} />
      <select value={value} onChange={(event) => onChange(event.target.value)} className={inputClass()}>
        {filtered.map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    </div>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-4 border-b border-[#E5E7EB] py-3 last:border-b-0">
      <span className="text-sm font-medium text-[#2F3437]">{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="h-4 w-4 rounded border-[#D1D5DB] accent-[var(--color-accent)]" />
    </label>
  );
}

function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 px-4">
      <div className="w-full max-w-lg rounded-xl border border-[#E5E7EB] bg-warm-card shadow-card-md">
        <div className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-4">
          <div className="text-sm font-bold text-[#2F3437]">{title}</div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-hover-bg hover:text-[#2F3437]"><X size={16} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function ThemeCard({ mode, selected, onClick }: { mode: 'light' | 'dark' | 'system'; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-xl border p-3 text-left transition-all',
        selected ? 'border-accent bg-accent-light shadow-card-md' : 'border-[#E5E7EB] bg-white hover:bg-hover-bg'
      )}
    >
      <div className={cn('mb-3 h-16 rounded-lg border', mode === 'dark' ? 'border-[#3A3E3A] bg-[#222522]' : 'border-[#E5E7EB] bg-white', mode === 'system' && 'bg-gradient-to-br from-white from-50% to-[#222522] to-50%')} />
      <div className="text-sm font-bold capitalize text-[#2F3437]">{mode}</div>
      <div className="mt-1 text-xs text-gray-500">{mode === 'system' ? 'Follow device setting' : `${mode} interface`}</div>
    </button>
  );
}

function SupportCard({ icon, title, description, onClick }: { icon: ReactNode; title: string; description: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex min-h-[112px] flex-col items-start rounded-lg border border-[#E5E7EB] bg-white p-4 text-left transition-colors hover:bg-hover-bg">
      <span className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-accent-light text-accent">{icon}</span>
      <span className="text-sm font-bold text-[#2F3437]">{title}</span>
      <span className="mt-1 text-xs leading-5 text-gray-500">{description}</span>
    </button>
  );
}

export function SettingsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');
  const [legacy, setLegacy] = useState<LegacySettings>(defaultLegacy);
  const [profile, setProfile] = useState<SettingsProfile | null>(null);
  const [generalDraft, setGeneralDraft] = useState<Partial<UserPreferences>>({});
  const [notificationDraft, setNotificationDraft] = useState<Partial<UserPreferences>>({});
  const [loading, setLoading] = useState(true);
  const [savingSection, setSavingSection] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [passwordModal, setPasswordModal] = useState(false);
  const [guideModal, setGuideModal] = useState(false);
  const [ticketModal, setTicketModal] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' });
  const [passwordError, setPasswordError] = useState('');
  const [ticketForm, setTicketForm] = useState({ category: 'HR', subject: '', description: '' });
  const profileUploadInputRef = useRef<HTMLInputElement | null>(null);

  const headers = useMemo(() => headersFor(user), [user]);
  const preferences = theme.preferences;
  const landingPages = isAdminRole(user?.role)
    ? ['Dashboard', 'Employees', 'Team Allocation', 'Time Off & Attendance', 'Assets & Access', 'Staffing Requests']
    : ['My Dashboard', 'Apply Leave', 'Timesheets', 'Check In / Out', 'Documents', 'Company Handbook'];
  const currentGeneral = { ...preferences, ...generalDraft } as UserPreferences;
  const currentNotifications = { ...preferences, ...notificationDraft } as UserPreferences;

  useEffect(() => {
    async function loadSettings() {
      setLoading(true);
      setError('');
      try {
        const [legacyRes, profileRes] = await Promise.all([
          fetch(`${API_BASE}/settings/me`, { headers }),
          fetch(`${API_BASE}/settings/profile`, { headers }),
        ]);
        if (!legacyRes.ok || !profileRes.ok) throw new Error('Could not load settings.');
        setLegacy({ ...defaultLegacy, ...(await legacyRes.json()) });
        setProfile(await profileRes.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load settings.');
      } finally {
        setLoading(false);
      }
    }
    if (user?.id || user?.email) loadSettings();
  }, [headers, user?.email, user?.id]);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (!theme.isDirty) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [theme.isDirty]);

  async function patchLegacy(section: SettingsTab, payload: Record<string, unknown>) {
    setSavingSection(section);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/settings/me/${section}`, { method: 'PATCH', headers, body: JSON.stringify(payload) });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `Could not save ${section} settings.`);
      }
      setLegacy({ ...legacy, ...(await res.json()) });
      showToast({ message: 'Settings saved successfully' });
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not save ${section} settings.`);
    } finally {
      setSavingSection(null);
    }
  }

  async function saveGeneral() {
    setSavingSection('general');
    try {
      const res = await fetch(`${API_BASE}/settings/preferences/general`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(generalDraft),
      });
      if (!res.ok) throw new Error('Could not save general preferences.');
      setGeneralDraft({});
      await theme.refreshPreferences();
      showToast({ message: 'General settings saved' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save general preferences.');
    } finally {
      setSavingSection(null);
    }
  }

  async function saveNotifications() {
    setSavingSection('notifications');
    try {
      const [preferenceRes, legacyRes] = await Promise.all([
        fetch(`${API_BASE}/settings/preferences/notifications`, {
          method: 'PATCH',
          headers,
          body: JSON.stringify(notificationDraft),
        }),
        fetch(`${API_BASE}/settings/me/notifications`, {
          method: 'PATCH',
          headers,
          body: JSON.stringify({
            notification_company_announcements: legacy.notification_company_announcements,
            notification_leave_updates: currentNotifications.email_notif_leave_approved || currentNotifications.email_notif_leave_rejected,
            notification_attendance_reminders: legacy.notification_attendance_reminders,
            notification_task_assignments: legacy.notification_task_assignments,
            notification_training_notifications: legacy.notification_training_notifications,
            notification_project_allocation_updates: legacy.notification_project_allocation_updates,
          }),
        }),
      ]);
      if (!preferenceRes.ok || !legacyRes.ok) throw new Error('Could not save notification preferences.');
      setLegacy({ ...legacy, ...(await legacyRes.json()) });
      setNotificationDraft({});
      await theme.refreshPreferences();
      showToast({ message: 'Notification settings saved' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save notification preferences.');
    } finally {
      setSavingSection(null);
    }
  }

  async function saveAppearance() {
    setSavingSection('appearance');
    setError('');
    try {
      await theme.savePreferences();
      showToast({ message: 'Appearance saved' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save appearance.');
    } finally {
      setSavingSection(null);
    }
  }

  async function saveProfile() {
    if (!profile) return;
    setSavingSection('profile');
    try {
      const employeeRes = await fetch(`${API_BASE}/employees/${profile.id}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({
          first_name: profile.first_name,
          last_name: profile.last_name,
          phone: profile.phone,
        }),
      });
      if (!employeeRes.ok) throw new Error('Could not save profile.');
      const prefRes = await fetch(`${API_BASE}/settings/preferences/general`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ timezone: profile.timezone, date_format: profile.date_format }),
      });
      if (!prefRes.ok) throw new Error('Could not save profile preferences.');
      await theme.refreshPreferences();
      showToast({ message: 'Profile saved' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save profile.');
    } finally {
      setSavingSection(null);
    }
  }

  async function uploadProfilePicture(file: File) {
    if (!profile) return;
    if (!file.type.startsWith('image/')) {
      setError('Please upload a valid image file.');
      return;
    }
    setSavingSection('profile-upload');
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/employees/${profile.id}/upload-profile-picture`, {
        method: 'POST',
        headers: {
          'x-user-id': user?.id || '',
          'x-user-email': user?.email || '',
          'x-user-role': user?.role || '',
          'x-user-name': user?.name || '',
        },
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || 'Could not upload profile picture.');
      }
      const data = await res.json();
      setProfile({ ...profile, profile_image_url: data.profile_image_url });
      showToast({ message: 'Profile picture updated' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not upload profile picture.');
    } finally {
      setSavingSection(null);
      if (profileUploadInputRef.current) profileUploadInputRef.current.value = '';
    }
  }

  async function submitSupportTicket() {
    if (!ticketForm.category.trim() || !ticketForm.subject.trim() || !ticketForm.description.trim()) {
      setError('Category, subject, and description are required.');
      return;
    }
    setSavingSection('support');
    try {
      const res = await fetch(`${API_BASE}/support-tickets`, { method: 'POST', headers, body: JSON.stringify(ticketForm) });
      if (!res.ok) throw new Error('Could not submit support ticket.');
      setTicketModal(false);
      setTicketForm({ category: 'HR', subject: '', description: '' });
      showToast({ message: 'Support ticket submitted successfully' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit support ticket.');
    } finally {
      setSavingSection(null);
    }
  }

  function submitPasswordChange() {
    if (!passwordForm.current || !passwordForm.next || !passwordForm.confirm) setPasswordError('All password fields are required.');
    else if (passwordForm.next.length < 8) setPasswordError('New password must be at least 8 characters.');
    else if (passwordForm.next !== passwordForm.confirm) setPasswordError('New password and confirmation must match.');
    else {
      setPasswordError('');
      showToast({ message: 'Change password is coming soon.' });
      setPasswordModal(false);
    }
  }

  const privacyAction = (
    <Button
      onClick={() => patchLegacy('privacy', {
        profile_visibility: legacy.profile_visibility,
        phone_visibility: legacy.phone_visibility,
        birthday_visibility: legacy.birthday_visibility,
      })}
      disabled={savingSection === 'privacy'}
      icon={<Save size={16} />}
    >
      {savingSection === 'privacy' ? 'Saving' : 'Save'}
    </Button>
  );

  if (loading || !preferences) {
    return <div className="py-20 text-center text-sm text-gray-500">Loading settings...</div>;
  }

  return (
    <div className="animate-fade-up">
      <div className="mb-7">
        <h1 className="mb-1 text-2xl font-bold tracking-tight text-[#2F3437]">Settings</h1>
        <p className="text-sm text-gray-500">Manage your profile, preferences, security, and notifications.</p>
      </div>

      {error && <div className="mb-5 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <Card className="overflow-hidden">
          <div className="p-3">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  'mb-1 flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm font-semibold transition-all last:mb-0',
                  activeTab === tab.key ? 'bg-accent text-white shadow-sm' : 'text-gray-500 hover:bg-hover-bg hover:text-[#2F3437]'
                )}
              >
                <span className="flex items-center gap-2.5">{tab.icon}{tab.label}</span>
                {activeTab === tab.key && <ChevronRight size={15} />}
              </button>
            ))}
          </div>
        </Card>

        <div className="min-w-0">
          {activeTab === 'profile' && profile && (
            <Card>
              <CardHeader title="Profile" icon={<UserRound size={17} />} action={<Button icon={<Save size={16} />} disabled={savingSection === 'profile'} onClick={saveProfile}>{savingSection === 'profile' ? 'Saving' : 'Save Profile'}</Button>} />
              <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-2">
                <div className="md:col-span-2 flex items-center gap-4 rounded-xl border border-[#E5E7EB] bg-white p-4">
                  <Avatar initials={initials(profile.display_name)} size="lg" variant="filled" src={profile.profile_image_url} />
                  <div className="min-w-0 flex-1">
                    <div className="font-bold text-[#2F3437]">{profile.display_name}</div>
                    <div className="text-sm text-gray-500">{profile.work_email}</div>
                  </div>
                  <input
                    ref={profileUploadInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void uploadProfilePicture(file);
                    }}
                  />
                  <Button
                    variant="ghost"
                    icon={<Upload size={16} />}
                    disabled={savingSection === 'profile-upload'}
                    onClick={() => profileUploadInputRef.current?.click()}
                  >
                    {savingSection === 'profile-upload' ? 'Uploading' : 'Upload'}
                  </Button>
                </div>
                <Field label="First Name"><input value={profile.first_name} onChange={(e) => setProfile({ ...profile, first_name: e.target.value })} className={inputClass()} /></Field>
                <Field label="Last Name"><input value={profile.last_name} onChange={(e) => setProfile({ ...profile, last_name: e.target.value })} className={inputClass()} /></Field>
                <Field label="Phone Number"><input value={profile.phone || ''} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} className={inputClass()} /></Field>
                <Field label="Work Email" hint="Work email is managed by HR/Admin."><input value={profile.work_email} readOnly className={`${inputClass()} bg-hover-bg text-gray-500`} /></Field>
                <Field label="Timezone"><SearchableTimezone value={profile.timezone} onChange={(timezone) => setProfile({ ...profile, timezone })} /></Field>
                <Field label="Date Format"><SelectField value={profile.date_format} options={dateFormats} onChange={(date_format) => setProfile({ ...profile, date_format })} /></Field>
              </div>
            </Card>
          )}

          {activeTab === 'general' && (
            <Card>
              <CardHeader title="General" icon={<Globe2 size={17} />} action={<Button icon={<Save size={16} />} disabled={savingSection === 'general'} onClick={saveGeneral}>{savingSection === 'general' ? 'Saving' : 'Save'}</Button>} />
              <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-2">
                <Field label="Language"><select value={currentGeneral.language} onChange={(e) => setGeneralDraft({ ...generalDraft, language: e.target.value })} className={inputClass()}>{languages.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="Date Format"><SelectField value={currentGeneral.date_format} options={dateFormats} onChange={(date_format) => setGeneralDraft({ ...generalDraft, date_format })} /></Field>
                <Field label="Time Zone"><SearchableTimezone value={currentGeneral.timezone} onChange={(timezone) => setGeneralDraft({ ...generalDraft, timezone })} /></Field>
                <Field label="Default Landing Page"><SelectField value={currentGeneral.default_landing_page} options={landingPages} onChange={(default_landing_page) => setGeneralDraft({ ...generalDraft, default_landing_page })} /></Field>
              </div>
            </Card>
          )}

          {activeTab === 'security' && (
            <Card>
              <CardHeader title="Security" icon={<ShieldCheck size={17} />} />
              <div className="divide-y divide-[#E5E7EB] p-5">
                <div className="flex flex-col gap-3 pb-4 md:flex-row md:items-center md:justify-between">
                  <div><div className="text-sm font-bold text-[#2F3437]">Password</div><div className="mt-1 text-sm text-gray-500">Password changes are coming soon.</div></div>
                  <Button variant="ghost" icon={<KeyRound size={16} />} onClick={() => setPasswordModal(true)}>Change Password</Button>
                </div>
                <div className="py-4 text-sm text-gray-500">Last login: <span className="font-semibold text-[#2F3437]">{profile?.last_login_at ? new Date(profile.last_login_at).toLocaleString() : 'Not recorded'}</span></div>
                <div className="flex flex-col gap-3 py-4 md:flex-row md:items-center md:justify-between">
                  <div><div className="text-sm font-bold text-[#2F3437]">Multi-Factor Authentication</div><div className="mt-1 text-sm text-gray-500">Add an extra verification step for sign in.</div></div>
                  <label className="flex items-center gap-2 text-sm font-semibold text-[#2F3437]"><input type="checkbox" checked={legacy.mfa_enabled} onChange={(e) => setLegacy({ ...legacy, mfa_enabled: e.target.checked })} className="h-4 w-4 accent-[var(--color-accent)]" />MFA Enabled</label>
                </div>
                <div className="pt-4"><Button disabled variant="ghost">Sign Out All Devices</Button><span className="ml-3 text-xs text-gray-400">Session management coming soon</span></div>
              </div>
            </Card>
          )}

          {activeTab === 'notifications' && (
            <Card>
              <CardHeader title="Notifications" icon={<Bell size={17} />} action={<Button icon={<Save size={16} />} disabled={savingSection === 'notifications'} onClick={saveNotifications}>{savingSection === 'notifications' ? 'Saving' : 'Save'}</Button>} />
              <div className="grid grid-cols-1 gap-6 p-5 lg:grid-cols-2">
                <div><div className="mb-2 text-sm font-bold text-[#2F3437]">Email Notifications</div><ToggleRow label="Leave Approved" checked={currentNotifications.email_notif_leave_approved} onChange={(value) => setNotificationDraft({ ...notificationDraft, email_notif_leave_approved: value })} /><ToggleRow label="Leave Rejected" checked={currentNotifications.email_notif_leave_rejected} onChange={(value) => setNotificationDraft({ ...notificationDraft, email_notif_leave_rejected: value })} /><ToggleRow label="Timesheet Approved" checked={currentNotifications.email_notif_timesheet_approved} onChange={(value) => setNotificationDraft({ ...notificationDraft, email_notif_timesheet_approved: value })} /><ToggleRow label="Timesheet Rejected" checked={currentNotifications.email_notif_timesheet_rejected} onChange={(value) => setNotificationDraft({ ...notificationDraft, email_notif_timesheet_rejected: value })} /><ToggleRow label="Allocation Changes" checked={currentNotifications.email_notif_allocation_changes} onChange={(value) => setNotificationDraft({ ...notificationDraft, email_notif_allocation_changes: value })} /></div>
                <div><div className="mb-2 text-sm font-bold text-[#2F3437]">In-App Notifications</div><ToggleRow label="Enable In-App Notifications" checked={currentNotifications.inapp_notifications_enabled} onChange={(value) => setNotificationDraft({ ...notificationDraft, inapp_notifications_enabled: value })} /><ToggleRow label="Company Announcements" checked={legacy.notification_company_announcements} onChange={(value) => setLegacy({ ...legacy, notification_company_announcements: value })} /><ToggleRow label="Attendance Reminders" checked={legacy.notification_attendance_reminders} onChange={(value) => setLegacy({ ...legacy, notification_attendance_reminders: value })} /><ToggleRow label="Task Assignments" checked={legacy.notification_task_assignments} onChange={(value) => setLegacy({ ...legacy, notification_task_assignments: value })} /><ToggleRow label="Training" checked={legacy.notification_training_notifications} onChange={(value) => setLegacy({ ...legacy, notification_training_notifications: value })} /><ToggleRow label="Project Allocation Updates" checked={legacy.notification_project_allocation_updates} onChange={(value) => setLegacy({ ...legacy, notification_project_allocation_updates: value })} /></div>
              </div>
            </Card>
          )}

          {activeTab === 'appearance' && (
            <Card>
              <CardHeader title="Appearance" icon={<Palette size={17} />} action={<Button icon={<Save size={16} />} disabled={!theme.isDirty || savingSection === 'appearance'} onClick={saveAppearance}>{savingSection === 'appearance' ? 'Saving' : 'Save'}</Button>} />
              <div className="space-y-6 p-5">
                <Field label="Theme Mode"><div className="grid gap-3 sm:grid-cols-3"><ThemeCard mode="light" selected={theme.themeMode === 'light'} onClick={() => theme.setThemeMode('light')} /><ThemeCard mode="dark" selected={theme.themeMode === 'dark'} onClick={() => theme.setThemeMode('dark')} /><ThemeCard mode="system" selected={theme.themeMode === 'system'} onClick={() => theme.setThemeMode('system')} /></div></Field>
                <Field label="Accent Color"><div className="flex flex-wrap gap-3">{accentOptions.map(([name, color]) => <button key={name} title={name} onClick={() => theme.setAccentColor(name)} className={cn('h-8 w-8 rounded-full border-2 transition-all', theme.accentColor === name ? 'border-white ring-2 ring-accent ring-offset-2' : 'border-transparent')} style={{ backgroundColor: color }} />)}</div></Field>
                <div className="rounded-xl border border-[#E5E7EB] bg-white p-4"><div className="mb-3 text-sm font-bold text-[#2F3437]">Live Preview</div><div className="flex flex-wrap items-center gap-3"><Button>Primary Button</Button><span className="rounded-md bg-accent-light px-2 py-1 text-xs font-bold text-accent">Badge</span><span className="text-sm font-bold text-accent">Active nav link</span></div></div>
                <Field label="Sidebar"><div className="grid gap-2 sm:grid-cols-2"><button onClick={() => theme.setSidebarCollapsed(false)} className={cn('rounded-lg border px-3 py-2 text-sm font-semibold', !theme.sidebarCollapsed ? 'border-accent bg-accent text-white' : 'border-[#E5E7EB] bg-white text-gray-500')}>Expanded</button><button onClick={() => theme.setSidebarCollapsed(true)} className={cn('rounded-lg border px-3 py-2 text-sm font-semibold', theme.sidebarCollapsed ? 'border-accent bg-accent text-white' : 'border-[#E5E7EB] bg-white text-gray-500')}>Collapsed</button></div></Field>
                <ToggleRow label="Compact Layout" checked={theme.compactMode} onChange={theme.setCompactMode} />
                {theme.isDirty && <div className="rounded-lg border border-status-warning/20 bg-status-warning/10 px-4 py-3 text-sm text-status-warning">Preview is active. Save to keep these appearance changes.</div>}
              </div>
            </Card>
          )}

          {activeTab === 'privacy' && (
            <Card>
              <CardHeader title="Privacy" icon={<Eye size={17} />} action={privacyAction} />
              <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-2">
                <Field label="Profile Visibility"><SelectField value={legacy.profile_visibility} options={privacyOptions} onChange={(profile_visibility) => setLegacy({ ...legacy, profile_visibility })} /></Field>
                <Field label="Phone Number Visibility"><SelectField value={legacy.phone_visibility} options={privacyOptions} onChange={(phone_visibility) => setLegacy({ ...legacy, phone_visibility })} /></Field>
                <Field label="Birthday Visibility"><SelectField value={legacy.birthday_visibility} options={privacyOptions} onChange={(birthday_visibility) => setLegacy({ ...legacy, birthday_visibility })} /></Field>
              </div>
            </Card>
          )}

          {activeTab === 'support' && (
            <div className="space-y-5">
              <Card><CardHeader title="Support" icon={<HelpCircle size={17} />} /><div className="grid grid-cols-1 gap-3 p-5 md:grid-cols-2"><SupportCard icon={<Monitor size={17} />} title="Contact IT" description="Email IT for access, devices, and app issues." onClick={() => { window.location.href = 'mailto:it@reknew.com'; }} /><SupportCard icon={<Headphones size={17} />} title="Raise Support Ticket" description="Create a tracked request for admin follow-up." onClick={() => setTicketModal(true)} /><SupportCard icon={<HelpCircle size={17} />} title="View User Guide" description="Open the ReKnew Orbit user guide." onClick={() => setGuideModal(true)} /></div></Card>
              <div className="text-right text-xs font-semibold text-gray-400">ReKnew Orbit v1.0.0</div>
            </div>
          )}
        </div>
      </div>

      {passwordModal && <Modal title="Change Password" onClose={() => setPasswordModal(false)}><div className="space-y-4">{passwordError && <div className="rounded-lg bg-status-error/10 px-3 py-2 text-sm text-status-error">{passwordError}</div>}<Field label="Current Password"><input type="password" value={passwordForm.current} onChange={(e) => setPasswordForm({ ...passwordForm, current: e.target.value })} className={inputClass()} /></Field><Field label="New Password"><input type="password" value={passwordForm.next} onChange={(e) => setPasswordForm({ ...passwordForm, next: e.target.value })} className={inputClass()} /></Field><Field label="Confirm Password"><input type="password" value={passwordForm.confirm} onChange={(e) => setPasswordForm({ ...passwordForm, confirm: e.target.value })} className={inputClass()} /></Field><div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setPasswordModal(false)}>Cancel</Button><Button icon={<LockKeyhole size={16} />} onClick={submitPasswordChange}>Validate</Button></div></div></Modal>}
      {ticketModal && <Modal title="Raise Support Ticket" onClose={() => setTicketModal(false)}><div className="space-y-4"><Field label="Category"><SelectField value={ticketForm.category} options={['HR', 'IT', 'Payroll', 'Access', 'Other']} onChange={(category) => setTicketForm({ ...ticketForm, category })} /></Field><Field label="Subject"><input value={ticketForm.subject} onChange={(e) => setTicketForm({ ...ticketForm, subject: e.target.value })} className={inputClass()} /></Field><Field label="Description"><textarea value={ticketForm.description} onChange={(e) => setTicketForm({ ...ticketForm, description: e.target.value })} rows={5} className={`${inputClass()} resize-none`} /></Field><div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setTicketModal(false)}>Cancel</Button><Button onClick={submitSupportTicket} disabled={savingSection === 'support'}>Submit Ticket</Button></div></div></Modal>}
      {guideModal && <Modal title="User Guide" onClose={() => setGuideModal(false)}><div className="rounded-lg border border-dashed border-[#E5E7EB] bg-hover-bg px-4 py-10 text-center text-sm font-semibold text-gray-500">User Guide Coming Soon</div></Modal>}
    </div>
  );
}

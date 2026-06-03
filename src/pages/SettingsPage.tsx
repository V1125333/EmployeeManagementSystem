import { useEffect, useMemo, useState } from 'react';
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
  LogOut,
  Monitor,
  Moon,
  Palette,
  Save,
  Shield,
  ShieldCheck,
  Sun,
  Users,
  X,
} from 'lucide-react';
import { Badge, Button, Card, CardHeader } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

type SettingsTab = 'general' | 'security' | 'notifications' | 'appearance' | 'privacy' | 'support';

interface UserSettings {
  time_zone: string;
  date_format: string;
  default_landing_page: string;
  theme: 'light' | 'dark' | 'system';
  sidebar_mode: 'expanded' | 'collapsed';
  dashboard_density: 'comfortable' | 'compact';
  mfa_enabled: boolean;
  notification_company_announcements: boolean;
  notification_leave_updates: boolean;
  notification_attendance_reminders: boolean;
  notification_task_assignments: boolean;
  notification_training_notifications: boolean;
  notification_project_allocation_updates: boolean;
  profile_visibility: string;
  phone_visibility: string;
  birthday_visibility: string;
}

const tabs: { key: SettingsTab; label: string; icon: ReactNode }[] = [
  { key: 'general', label: 'General', icon: <Globe2 size={16} /> },
  { key: 'security', label: 'Security', icon: <Shield size={16} /> },
  { key: 'notifications', label: 'Notifications', icon: <Bell size={16} /> },
  { key: 'appearance', label: 'Appearance', icon: <Palette size={16} /> },
  { key: 'privacy', label: 'Privacy', icon: <Eye size={16} /> },
  { key: 'support', label: 'Support', icon: <Headphones size={16} /> },
];

const defaultSettings: UserSettings = {
  time_zone: 'America/New_York',
  date_format: 'MM/DD/YYYY',
  default_landing_page: 'Dashboard',
  theme: 'system',
  sidebar_mode: 'expanded',
  dashboard_density: 'comfortable',
  mfa_enabled: false,
  notification_company_announcements: true,
  notification_leave_updates: true,
  notification_attendance_reminders: true,
  notification_task_assignments: true,
  notification_training_notifications: true,
  notification_project_allocation_updates: true,
  profile_visibility: 'Everyone',
  phone_visibility: 'Managers Only',
  birthday_visibility: 'Everyone',
};

const privacyOptions = ['Everyone', 'Managers Only', 'HR Only', 'Private'];

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold text-gray-500">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-xs text-gray-400">{hint}</span>}
    </label>
  );
}

function SelectField({ value, onChange, options }: { value: string; onChange: (value: string) => void; options: string[] }) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm font-medium text-[#2F3437] outline-none transition-colors focus:border-olive"
    >
      {options.map((option) => <option key={option} value={option}>{option}</option>)}
    </select>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-4 border-b border-[#E5E7EB] py-3 last:border-b-0">
      <span className="text-sm font-medium text-[#2F3437]">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 rounded border-[#D1D5DB] accent-olive"
      />
    </label>
  );
}

function SegmentedControl({ value, options, onChange }: { value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {options.map((option) => {
        const normalized = option.toLowerCase();
        return (
          <button
            key={option}
            onClick={() => onChange(normalized)}
            className={cn(
              'rounded-lg border px-3 py-2 text-sm font-semibold transition-all',
              value === normalized
                ? 'border-olive bg-olive text-white shadow-sm'
                : 'border-[#E5E7EB] bg-white text-gray-500 hover:bg-hover-bg hover:text-[#2F3437]'
            )}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 px-4">
      <div className="w-full max-w-lg rounded-xl border border-[#E5E7EB] bg-warm-card shadow-card-lg">
        <div className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-4">
          <div className="text-sm font-bold text-[#2F3437]">{title}</div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-hover-bg hover:text-[#2F3437]">
            <X size={16} />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function SupportCard({ icon, title, description, onClick }: { icon: ReactNode; title: string; description: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex min-h-[112px] flex-col items-start rounded-lg border border-[#E5E7EB] bg-white p-4 text-left transition-colors hover:bg-hover-bg">
      <span className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-olive/10 text-olive">{icon}</span>
      <span className="text-sm font-bold text-[#2F3437]">{title}</span>
      <span className="mt-1 text-xs leading-5 text-gray-500">{description}</span>
    </button>
  );
}

function headersFor(user: ReturnType<typeof useAuth>['user']) {
  return {
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': user?.role || '',
    'x-user-name': user?.name || '',
  };
}

export function SettingsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [settings, setSettings] = useState<UserSettings>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [savingSection, setSavingSection] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [passwordModal, setPasswordModal] = useState(false);
  const [guideModal, setGuideModal] = useState(false);
  const [ticketModal, setTicketModal] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' });
  const [passwordError, setPasswordError] = useState('');
  const [ticketForm, setTicketForm] = useState({ category: 'HR', subject: '', description: '' });

  const headers = useMemo(() => headersFor(user), [user]);

  useEffect(() => {
    async function loadSettings() {
      setLoading(true);
      setError('');
      try {
        const res = await fetch(`${API_BASE}/settings/me`, { headers });
        if (!res.ok) throw new Error('Could not load settings.');
        setSettings(await res.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load settings.');
      } finally {
        setLoading(false);
      }
    }
    if (user?.id || user?.email) loadSettings();
  }, [headers, user?.email, user?.id]);

  useEffect(() => {
    document.documentElement.dataset.theme = settings.theme;
    document.documentElement.dataset.dashboardDensity = settings.dashboard_density;
  }, [settings.theme, settings.dashboard_density]);

  async function patchSettings(section: SettingsTab, payload: Record<string, unknown>) {
    setSavingSection(section);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/settings/me/${section}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `Could not save ${section} settings.`);
      }
      setSettings(await res.json());
      showToast({ message: 'Settings saved successfully' });
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not save ${section} settings.`);
    } finally {
      setSavingSection(null);
    }
  }

  function validatePasswordForm() {
    if (!passwordForm.current || !passwordForm.next || !passwordForm.confirm) return 'All password fields are required.';
    if (passwordForm.next.length < 8) return 'New password must be at least 8 characters.';
    if (passwordForm.next !== passwordForm.confirm) return 'New password and confirmation must match.';
    return '';
  }

  function submitPasswordChange() {
    const nextError = validatePasswordForm();
    setPasswordError(nextError);
    if (nextError) return;
    // TODO: Wire this to the backend change-password API when that endpoint exists.
    showToast({ message: 'Password validation passed. Backend password API is pending.' });
    setPasswordModal(false);
    setPasswordForm({ current: '', next: '', confirm: '' });
  }

  async function submitSupportTicket() {
    if (!ticketForm.category.trim() || !ticketForm.subject.trim() || !ticketForm.description.trim()) {
      setError('Category, subject, and description are required.');
      return;
    }

    setSavingSection('support');
    setError('');
    try {
      const res = await fetch(`${API_BASE}/support-tickets`, {
        method: 'POST',
        headers,
        body: JSON.stringify(ticketForm),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || 'Could not submit support ticket.');
      }
      setTicketModal(false);
      setTicketForm({ category: 'HR', subject: '', description: '' });
      showToast({ message: 'Support ticket submitted successfully' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit support ticket.');
    } finally {
      setSavingSection(null);
    }
  }

  const sectionAction = (section: SettingsTab, label = 'Save') => (
    <Button
      onClick={() => {
        if (section === 'general') {
          patchSettings('general', {
            time_zone: settings.time_zone,
            date_format: settings.date_format,
            default_landing_page: settings.default_landing_page,
          });
        } else if (section === 'security') {
          patchSettings('security', { mfa_enabled: settings.mfa_enabled });
        } else if (section === 'notifications') {
          patchSettings('notifications', {
            notification_company_announcements: settings.notification_company_announcements,
            notification_leave_updates: settings.notification_leave_updates,
            notification_attendance_reminders: settings.notification_attendance_reminders,
            notification_task_assignments: settings.notification_task_assignments,
            notification_training_notifications: settings.notification_training_notifications,
            notification_project_allocation_updates: settings.notification_project_allocation_updates,
          });
        } else if (section === 'appearance') {
          patchSettings('appearance', {
            theme: settings.theme,
            sidebar_mode: settings.sidebar_mode,
            dashboard_density: settings.dashboard_density,
          });
        } else if (section === 'privacy') {
          patchSettings('privacy', {
            profile_visibility: settings.profile_visibility,
            phone_visibility: settings.phone_visibility,
            birthday_visibility: settings.birthday_visibility,
          });
        }
      }}
      disabled={savingSection === section}
      icon={<Save size={16} />}
    >
      {savingSection === section ? 'Saving' : label}
    </Button>
  );

  if (loading) {
    return <div className="py-20 text-center text-sm text-gray-500">Loading settings...</div>;
  }

  return (
    <div className="animate-fade-up">
      <div className="mb-7">
        <h1 className="mb-1 text-2xl font-bold tracking-tight text-[#2F3437]">Settings</h1>
        <p className="text-sm text-gray-500">Manage your account preferences, security, and notifications.</p>
      </div>

      {error && (
        <div className="mb-5 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <Card className="overflow-hidden">
          <div className="p-3">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  'mb-1 flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm font-semibold transition-all last:mb-0',
                  activeTab === tab.key ? 'bg-olive text-white shadow-sm' : 'text-gray-500 hover:bg-hover-bg hover:text-[#2F3437]'
                )}
              >
                <span className="flex items-center gap-2.5">{tab.icon}{tab.label}</span>
                {activeTab === tab.key && <ChevronRight size={15} />}
              </button>
            ))}
          </div>
        </Card>

        <div className="min-w-0">
          {activeTab === 'general' && (
            <Card>
              <CardHeader title="General" icon={<Globe2 size={17} />} action={sectionAction('general')} />
              <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-2">
                <Field label="Time Zone">
                  <SelectField value={settings.time_zone} options={['America/New_York', 'America/Chicago', 'America/Los_Angeles', 'Asia/Kolkata']} onChange={(time_zone) => setSettings({ ...settings, time_zone })} />
                </Field>
                <Field label="Date Format">
                  <SelectField value={settings.date_format} options={['MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD']} onChange={(date_format) => setSettings({ ...settings, date_format })} />
                </Field>
                <Field label="Default Landing Page">
                  <SelectField value={settings.default_landing_page} options={['Dashboard', 'Employees', 'Team Allocation', 'Time Off & Attendance', 'Assets & Access']} onChange={(default_landing_page) => setSettings({ ...settings, default_landing_page })} />
                </Field>
              </div>
            </Card>
          )}

          {activeTab === 'security' && (
            <Card>
              <CardHeader title="Security" icon={<ShieldCheck size={17} />} action={sectionAction('security')} />
              <div className="divide-y divide-[#E5E7EB] p-5">
                <div className="flex flex-col gap-3 pb-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-sm font-bold text-[#2F3437]">Password</div>
                    <div className="mt-1 text-sm text-gray-500">Update the password used to access your account.</div>
                  </div>
                  <Button variant="ghost" icon={<KeyRound size={16} />} onClick={() => setPasswordModal(true)}>Change Password</Button>
                </div>
                <div className="flex flex-col gap-3 py-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-sm font-bold text-[#2F3437]">Multi-Factor Authentication</div>
                    <div className="mt-1 text-sm text-gray-500">Add an extra verification step for sign in.</div>
                  </div>
                  <label className="flex items-center gap-2 text-sm font-semibold text-[#2F3437]">
                    <input type="checkbox" checked={settings.mfa_enabled} onChange={(event) => setSettings({ ...settings, mfa_enabled: event.target.checked })} className="h-4 w-4 accent-olive" />
                    MFA Enabled
                  </label>
                </div>
                <div className="pt-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <div className="text-sm font-bold text-[#2F3437]">Active Sessions</div>
                      <div className="mt-1 text-sm text-gray-500">Devices currently signed into your account.</div>
                    </div>
                    <Button variant="ghost" icon={<LogOut size={16} />}>Sign Out All Devices</Button>
                  </div>
                  <div className="rounded-lg border border-[#E5E7EB] bg-white px-4 py-3 text-sm text-gray-500">
                    Current browser session
                  </div>
                </div>
              </div>
            </Card>
          )}

          {activeTab === 'notifications' && (
            <Card>
              <CardHeader title="Notifications" icon={<Bell size={17} />} action={sectionAction('notifications')} />
              <div className="p-5">
                <ToggleRow label="Company Announcements" checked={settings.notification_company_announcements} onChange={(notification_company_announcements) => setSettings({ ...settings, notification_company_announcements })} />
                <ToggleRow label="Leave Updates" checked={settings.notification_leave_updates} onChange={(notification_leave_updates) => setSettings({ ...settings, notification_leave_updates })} />
                <ToggleRow label="Attendance Reminders" checked={settings.notification_attendance_reminders} onChange={(notification_attendance_reminders) => setSettings({ ...settings, notification_attendance_reminders })} />
                <ToggleRow label="Task Assignments" checked={settings.notification_task_assignments} onChange={(notification_task_assignments) => setSettings({ ...settings, notification_task_assignments })} />
                <ToggleRow label="Training Notifications" checked={settings.notification_training_notifications} onChange={(notification_training_notifications) => setSettings({ ...settings, notification_training_notifications })} />
                <ToggleRow label="Project Allocation Updates" checked={settings.notification_project_allocation_updates} onChange={(notification_project_allocation_updates) => setSettings({ ...settings, notification_project_allocation_updates })} />
              </div>
            </Card>
          )}

          {activeTab === 'appearance' && (
            <Card>
              <CardHeader title="Appearance" icon={<Palette size={17} />} action={sectionAction('appearance')} />
              <div className="space-y-6 p-5">
                <Field label="Theme">
                  <SegmentedControl value={settings.theme} options={['Light', 'Dark', 'System']} onChange={(theme) => setSettings({ ...settings, theme: theme as UserSettings['theme'] })} />
                </Field>
                <Field label="Sidebar Mode">
                  <SegmentedControl value={settings.sidebar_mode} options={['Expanded', 'Collapsed']} onChange={(sidebar_mode) => setSettings({ ...settings, sidebar_mode: sidebar_mode as UserSettings['sidebar_mode'] })} />
                </Field>
                <Field label="Dashboard Density">
                  <SegmentedControl value={settings.dashboard_density} options={['Comfortable', 'Compact']} onChange={(dashboard_density) => setSettings({ ...settings, dashboard_density: dashboard_density as UserSettings['dashboard_density'] })} />
                </Field>
                <div className="flex items-center gap-2 rounded-lg border border-[#E5E7EB] bg-hover-bg px-4 py-3 text-sm text-gray-500">
                  {settings.theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />}
                  Appearance choices apply immediately where supported.
                </div>
              </div>
            </Card>
          )}

          {activeTab === 'privacy' && (
            <Card>
              <CardHeader title="Privacy" icon={<Eye size={17} />} action={sectionAction('privacy')} />
              <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-2">
                <Field label="Profile Visibility" hint="TODO: Enforce this in employee directory/profile visibility logic.">
                  <SelectField value={settings.profile_visibility} options={privacyOptions} onChange={(profile_visibility) => setSettings({ ...settings, profile_visibility })} />
                </Field>
                <Field label="Phone Number Visibility" hint="TODO: Enforce this in employee directory/profile visibility logic.">
                  <SelectField value={settings.phone_visibility} options={privacyOptions} onChange={(phone_visibility) => setSettings({ ...settings, phone_visibility })} />
                </Field>
                <Field label="Birthday Visibility" hint="TODO: Enforce this in employee directory/profile visibility logic.">
                  <SelectField value={settings.birthday_visibility} options={privacyOptions} onChange={(birthday_visibility) => setSettings({ ...settings, birthday_visibility })} />
                </Field>
              </div>
            </Card>
          )}

          {activeTab === 'support' && (
            <div className="space-y-5">
              <Card>
                <CardHeader title="Support" icon={<HelpCircle size={17} />} />
                <div className="grid grid-cols-1 gap-3 p-5 md:grid-cols-2">
                  <SupportCard icon={<Users size={17} />} title="Contact HR" description="Email HR for policies, leave, and employee questions." onClick={() => { window.location.href = 'mailto:hr@reknew.com'; }} />
                  <SupportCard icon={<Monitor size={17} />} title="Contact IT" description="Email IT for access, devices, and app issues." onClick={() => { window.location.href = 'mailto:it@reknew.com'; }} />
                  <SupportCard icon={<Headphones size={17} />} title="Raise Support Ticket" description="Create a tracked request for admin follow-up." onClick={() => setTicketModal(true)} />
                  <SupportCard icon={<HelpCircle size={17} />} title="View User Guide" description="Open the ReKnew Orbit user guide." onClick={() => setGuideModal(true)} />
                </div>
              </Card>
              <div className="text-right text-xs font-semibold text-gray-400">ReKnew Orbit v1.0.0</div>
            </div>
          )}
        </div>
      </div>

      {passwordModal && (
        <Modal title="Change Password" onClose={() => setPasswordModal(false)}>
          <div className="space-y-4">
            {passwordError && <div className="rounded-lg bg-status-error/10 px-3 py-2 text-sm text-status-error">{passwordError}</div>}
            <Field label="Current Password"><input type="password" value={passwordForm.current} onChange={(e) => setPasswordForm({ ...passwordForm, current: e.target.value })} className="w-full rounded-lg border border-[#E5E7EB] px-3 py-2 text-sm outline-none focus:border-olive" /></Field>
            <Field label="New Password"><input type="password" value={passwordForm.next} onChange={(e) => setPasswordForm({ ...passwordForm, next: e.target.value })} className="w-full rounded-lg border border-[#E5E7EB] px-3 py-2 text-sm outline-none focus:border-olive" /></Field>
            <Field label="Confirm Password"><input type="password" value={passwordForm.confirm} onChange={(e) => setPasswordForm({ ...passwordForm, confirm: e.target.value })} className="w-full rounded-lg border border-[#E5E7EB] px-3 py-2 text-sm outline-none focus:border-olive" /></Field>
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setPasswordModal(false)}>Cancel</Button><Button icon={<LockKeyhole size={16} />} onClick={submitPasswordChange}>Validate</Button></div>
          </div>
        </Modal>
      )}

      {ticketModal && (
        <Modal title="Raise Support Ticket" onClose={() => setTicketModal(false)}>
          <div className="space-y-4">
            <Field label="Category"><SelectField value={ticketForm.category} options={['HR', 'IT', 'Payroll', 'Access', 'Other']} onChange={(category) => setTicketForm({ ...ticketForm, category })} /></Field>
            <Field label="Subject"><input value={ticketForm.subject} onChange={(e) => setTicketForm({ ...ticketForm, subject: e.target.value })} className="w-full rounded-lg border border-[#E5E7EB] px-3 py-2 text-sm outline-none focus:border-olive" /></Field>
            <Field label="Description"><textarea value={ticketForm.description} onChange={(e) => setTicketForm({ ...ticketForm, description: e.target.value })} rows={5} className="w-full resize-none rounded-lg border border-[#E5E7EB] px-3 py-2 text-sm outline-none focus:border-olive" /></Field>
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setTicketModal(false)}>Cancel</Button><Button onClick={submitSupportTicket} disabled={savingSection === 'support'}>Submit Ticket</Button></div>
          </div>
        </Modal>
      )}

      {guideModal && (
        <Modal title="User Guide" onClose={() => setGuideModal(false)}>
          <div className="rounded-lg border border-dashed border-[#E5E7EB] bg-hover-bg px-4 py-10 text-center text-sm font-semibold text-gray-500">
            User Guide Coming Soon
          </div>
        </Modal>
      )}
    </div>
  );
}

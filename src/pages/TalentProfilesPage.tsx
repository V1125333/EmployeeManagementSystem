import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Award, Briefcase, FileText, Search, Sparkles, UserRound } from 'lucide-react';
import { Avatar, Badge, Button, Card } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import {
  careerProfileCompleteness,
  getCareerProfile,
  getSeededCareerProfile,
  type CareerProfileData,
} from '@/lib/careerProfileStore';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface EmployeeRecord {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  name?: string | null;
  work_email?: string | null;
  email?: string | null;
  designation?: string | null;
  department?: string | null;
  profile_image_url?: string | null;
}

function employeeName(employee: EmployeeRecord) {
  return employee.name || `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || 'Unnamed employee';
}

function employeeEmail(employee: EmployeeRecord) {
  return employee.work_email || employee.email || '';
}

function initials(name: string) {
  return name.split(' ').map((part) => part[0]).join('').toUpperCase().slice(0, 2) || 'EP';
}

function canViewTalentProfiles(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return ['manager', 'lead', 'team_lead', 'super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalized);
}

function profileSearchText(employee: EmployeeRecord, profile: CareerProfileData) {
  return [
    employeeName(employee),
    employeeEmail(employee),
    employee.department,
    employee.designation,
    profile.summary,
    profile.targetRoles,
    profile.preferredSkills,
    profile.skills.map((skill) => skill.name).join(' '),
    profile.projects.map((project) => `${project.name} ${project.role} ${project.stack}`).join(' '),
  ].filter(Boolean).join(' ').toLowerCase();
}

export function TalentProfilesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [employees, setEmployees] = useState<EmployeeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const canView = canViewTalentProfiles(user?.role);

  useEffect(() => {
    const handleUpdate = () => setRefreshKey((value) => value + 1);
    window.addEventListener('reknew:career-profile-updated', handleUpdate);
    return () => window.removeEventListener('reknew:career-profile-updated', handleUpdate);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadEmployees = async () => {
      if (!canView) {
        setEmployees([]);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError('');
      try {
        const response = await fetch(`${API_BASE}/employees?limit=200`, {
          headers: {
            'x-user-id': user?.id || '',
            'x-user-email': user?.email || '',
            'x-user-role': user?.role || '',
          },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.detail || data.message || 'Could not load employees.');
        }
        const rows = Array.isArray(data.employees) ? data.employees : Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
        if (!cancelled) setEmployees(rows);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load employees.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadEmployees();
    return () => { cancelled = true; };
  }, [canView, user?.email, user?.id, user?.role]);

  const profiles = useMemo(() => {
    void refreshKey;
    return employees.map((employee) => {
      const profile = getSeededCareerProfile(employee.id, employeeName(employee), employeeEmail(employee));
      return { employee, profile, completeness: careerProfileCompleteness(profile) };
    });
  }, [employees, refreshKey]);

  const visibleProfiles = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return profiles;
    return profiles.filter(({ employee, profile }) => profileSearchText(employee, profile).includes(query));
  }, [profiles, search]);

  if (!canView) {
    return (
      <div className="p-6 lg:p-8">
        <Card className="p-8 text-center">
          <div className="text-lg font-bold text-[var(--color-brand-navy)]">Talent Profiles are restricted</div>
          <div className="mt-2 text-sm text-gray-500">Managers, leads, HR, and admins can use this directory to discover employee skills and experience.</div>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Talent Profiles</h1>
          <p className="mt-1 text-sm text-gray-500">Discover employee skills, project experience, resumes, and growth interests.</p>
        </div>
        <div className="relative w-full max-w-md">
          <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search skills, roles, employees..."
            className="w-full rounded-xl border border-[var(--color-border)] bg-white py-2.5 pl-10 pr-3 text-sm font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive"
          />
        </div>
      </div>

      {error && <div className="mb-4 rounded-xl border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm font-semibold text-status-error">{error}</div>}

      <div className="mb-5 grid gap-4 md:grid-cols-3">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light text-accent"><UserRound size={18} /></span>
            <div>
              <div className="text-2xl font-bold text-[var(--color-brand-navy)]">{employees.length}</div>
              <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Employees</div>
            </div>
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light text-accent"><Sparkles size={18} /></span>
            <div>
              <div className="text-2xl font-bold text-[var(--color-brand-navy)]">{profiles.filter((item) => item.completeness > 0).length}</div>
              <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Profiles Started</div>
            </div>
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light text-accent"><FileText size={18} /></span>
            <div>
              <div className="text-2xl font-bold text-[var(--color-brand-navy)]">{profiles.filter((item) => item.profile.resumeName.trim()).length}</div>
              <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Resume References</div>
            </div>
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="border-b border-[var(--color-border)] px-5 py-4">
          <div className="flex items-center gap-2 text-sm font-bold text-[var(--color-brand-navy)]">
            <Award size={16} className="text-olive" />
            Career Directory
          </div>
        </div>
        {loading ? (
          <div className="px-5 py-10 text-center text-sm text-gray-500">Loading talent profiles...</div>
        ) : visibleProfiles.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-gray-500">No talent profiles match your search.</div>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {visibleProfiles.map(({ employee, profile, completeness }) => {
              const name = employeeName(employee);
              const topSkills = profile.skills.map((skill) => skill.name).filter(Boolean).slice(0, 4);
              return (
                <div key={employee.id} className="grid gap-4 px-5 py-4 lg:grid-cols-[1.2fr_1.5fr_auto] lg:items-center">
                  <div className="flex min-w-0 items-center gap-3">
                    <Avatar initials={initials(name)} src={employee.profile_image_url || null} />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-bold text-[var(--color-brand-navy)]">{name}</div>
                      <div className="truncate text-sm text-gray-500">{employee.designation || 'Designation not recorded'}{employee.department ? ` · ${employee.department}` : ''}</div>
                      <div className="truncate text-xs text-gray-400">{employeeEmail(employee) || 'Email not recorded'}</div>
                    </div>
                  </div>

                  <div className="min-w-0">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Badge variant={completeness >= 75 ? 'success' : completeness >= 40 ? 'warning' : 'neutral'}>{completeness}% complete</Badge>
                      {profile.resumeName && <Badge variant="info">Resume added</Badge>}
                      {profile.projects.length > 0 && <Badge variant="sage">{profile.projects.length} project{profile.projects.length === 1 ? '' : 's'}</Badge>}
                    </div>
                    {topSkills.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {topSkills.map((skill) => <Badge key={skill} variant="neutral">{skill}</Badge>)}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-500">No skills added yet.</div>
                    )}
                    {profile.targetRoles && <div className="mt-2 truncate text-xs text-gray-500">Interested in: {profile.targetRoles}</div>}
                  </div>

                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={<Briefcase size={14} />}
                      onClick={() => navigate(`/profile?employee_id=${encodeURIComponent(employee.id)}&tab=career`)}
                    >
                      Career Profile
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => navigate(`/profile?employee_id=${encodeURIComponent(employee.id)}`)}
                    >
                      Employee Profile
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

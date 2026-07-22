import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, Search, Users } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';
import '@/styles/organization.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export interface OrganizationEmployee {
  id: string;
  name: string;
  designation: string;
  department: string;
  role: string;
  reporting_manager_id: string | null;
  reports_count: number;
  is_online: boolean;
  is_current_user: boolean;
}

interface OrganizationResponse {
  employees: OrganizationEmployee[];
  current_user_id: string;
  employee_count: number;
  department_count: number;
}

interface OrganizationChartProps {
  initialView?: 'my-line' | 'full';
  focusedEmployeeId?: string;
}

const USE_MOCK_HIERARCHY = import.meta.env.VITE_USE_MOCK_ORGANIZATION !== 'false';

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'NA';
}

function isLeadership(person: OrganizationEmployee) {
  const role = person.role.toLowerCase().replace(/[\s-]+/g, '_');
  return person.reports_count > 0 || ['manager', 'admin', 'hr_admin', 'super_admin', 'global_access'].includes(role);
}

function buildMockHierarchy(employees: OrganizationEmployee[], currentUserId: string) {
  if (employees.length < 2) return employees;
  const root = employees.find((person) => person.role.toLowerCase().replace(/[\s-]+/g, '_') === 'super_admin')
    || employees.find((person) => person.id === currentUserId)
    || employees[0];
  const leadershipRoles = new Set(['manager', 'admin', 'hr_admin', 'global_access']);
  const leaders = employees
    .filter((person) => person.id !== root.id)
    .filter((person) => {
      const role = person.role.toLowerCase().replace(/[\s-]+/g, '_');
      return leadershipRoles.has(role) || /\b(vp|lead|head|manager|director)\b/i.test(person.designation);
    })
    .slice(0, 5);
  const usableLeaders = leaders.length > 0 ? leaders : employees.filter((person) => person.id !== root.id).slice(0, 3);
  const leaderIds = new Set(usableLeaders.map((person) => person.id));
  const managerByEmployee = new Map<string, string | null>([[root.id, null]]);
  const mockTeamSizes = new Map<string, number>();
  usableLeaders.forEach((leader) => managerByEmployee.set(leader.id, root.id));
  usableLeaders.forEach((leader) => mockTeamSizes.set(leader.id, 0));

  employees
    .filter((person) => person.id !== root.id && !leaderIds.has(person.id))
    .forEach((person) => {
      const rankedLeaders = [...usableLeaders].sort((left, right) => {
        const leftSize = mockTeamSizes.get(left.id) || 0;
        const rightSize = mockTeamSizes.get(right.id) || 0;
        const leftDepartmentPenalty = left.department === person.department && leftSize < 4 ? 0 : 1;
        const rightDepartmentPenalty = right.department === person.department && rightSize < 4 ? 0 : 1;
        return leftDepartmentPenalty - rightDepartmentPenalty || leftSize - rightSize || left.name.localeCompare(right.name);
      });
      const manager = rankedLeaders[0];
      managerByEmployee.set(person.id, manager?.id || root.id);
      if (manager) mockTeamSizes.set(manager.id, (mockTeamSizes.get(manager.id) || 0) + 1);
    });

  const reportCounts = new Map<string, number>();
  managerByEmployee.forEach((managerId) => {
    if (managerId) reportCounts.set(managerId, (reportCounts.get(managerId) || 0) + 1);
  });
  return employees.map((person) => ({
    ...person,
    reporting_manager_id: managerByEmployee.get(person.id) ?? null,
    reports_count: reportCounts.get(person.id) || 0,
  }));
}

function PersonCard({ person, selected, onSelect }: { person: OrganizationEmployee; selected: boolean; onSelect: (person: OrganizationEmployee) => void }) {
  const reportLabel = `${person.reports_count} ${person.reports_count === 1 ? 'report' : 'reports'}`;
  return (
    <button
      type="button"
      data-org-person={person.id}
      onClick={() => onSelect(person)}
      className={cn('org-person-card', person.is_current_user && 'org-person-you', selected && 'org-person-selected')}
      aria-label={`${person.name}, ${person.designation}, ${person.department}, ${reportLabel}`}
    >
      {person.is_current_user && <span className="org-you-pill">YOU</span>}
      <span className={cn('org-avatar', person.is_current_user ? 'org-avatar-you' : isLeadership(person) ? 'org-avatar-leader' : 'org-avatar-member')}>
        {initials(person.name)}
        {person.is_online && <span className="org-online-dot" aria-label="Online" />}
      </span>
      <span className="org-person-name">{person.name}</span>
      <span className="org-person-role">{person.designation}</span>
      <span className="org-person-meta">
        <span className={cn('org-dept-chip', person.is_current_user && 'org-dept-chip-you')}>{person.department}</span>
        {person.reports_count > 0 && <span className="org-report-count">{reportLabel}⌄</span>}
      </span>
    </button>
  );
}

function FullTreeNode({ person, childrenByManager, selectedId, onSelect, ancestors = new Set<string>() }: {
  person: OrganizationEmployee;
  childrenByManager: Map<string, OrganizationEmployee[]>;
  selectedId: string;
  onSelect: (person: OrganizationEmployee) => void;
  ancestors?: Set<string>;
}) {
  if (ancestors.has(person.id)) return null;
  const nextAncestors = new Set(ancestors).add(person.id);
  const children = childrenByManager.get(person.id) || [];
  return (
    <li>
      <PersonCard person={person} selected={selectedId === person.id} onSelect={onSelect} />
      {children.length > 0 && (
        <ul>
          {children.map((child) => (
            <FullTreeNode key={child.id} person={child} childrenByManager={childrenByManager} selectedId={selectedId} onSelect={onSelect} ancestors={nextAncestors} />
          ))}
        </ul>
      )}
    </li>
  );
}

function Tier({ label, people, selectedId, onSelect }: { label: string; people: OrganizationEmployee[]; selectedId: string; onSelect: (person: OrganizationEmployee) => void }) {
  if (people.length === 0) return null;
  return (
    <div className="org-line-tier">
      <div className="org-tier-label">{label}</div>
      <div className="org-tier-row">
        {people.map((person) => <PersonCard key={person.id} person={person} selected={selectedId === person.id} onSelect={onSelect} />)}
      </div>
    </div>
  );
}

export function OrganizationChart({ initialView = 'my-line', focusedEmployeeId }: OrganizationChartProps) {
  const { user } = useAuth();
  const [data, setData] = useState<OrganizationResponse | null>(null);
  const [view, setView] = useState<'my-line' | 'full'>(initialView);
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const canvasRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await fetch(`${API_BASE}/employees/organization`, {
          headers: { 'x-user-id': user?.id || '', 'x-user-email': user?.email || '' },
        });
        const payload = await response.json().catch(() => null);
        if (!response.ok || !payload) throw new Error(payload?.detail || 'Could not load the organization chart.');
        if (!cancelled) {
          setData(payload);
          setSelectedId(focusedEmployeeId || payload.current_user_id);
        }
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : 'Could not load the organization chart.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [focusedEmployeeId, user?.email, user?.id]);

  const chartEmployees = useMemo(
    () => data && USE_MOCK_HIERARCHY ? buildMockHierarchy(data.employees, data.current_user_id) : data?.employees || [],
    [data],
  );
  const employeeMap = useMemo(() => new Map(chartEmployees.map((person) => [person.id, person])), [chartEmployees]);
  const childrenByManager = useMemo(() => {
    const map = new Map<string, OrganizationEmployee[]>();
    chartEmployees.forEach((person) => {
      if (!person.reporting_manager_id) return;
      const existing = map.get(person.reporting_manager_id) || [];
      existing.push(person);
      map.set(person.reporting_manager_id, existing);
    });
    map.forEach((people) => people.sort((a, b) => a.name.localeCompare(b.name)));
    return map;
  }, [chartEmployees]);

  const roots = useMemo(() => chartEmployees.filter((person) => !person.reporting_manager_id || !employeeMap.has(person.reporting_manager_id)), [chartEmployees, employeeMap]);
  const focusPerson = employeeMap.get(focusedEmployeeId || data?.current_user_id || '');
  const manager = focusPerson?.reporting_manager_id ? employeeMap.get(focusPerson.reporting_manager_id) : undefined;
  const peers = focusPerson
    ? chartEmployees.filter((person) => person.reporting_manager_id === focusPerson.reporting_manager_id)
    : [];
  const directReports = focusPerson ? childrenByManager.get(focusPerson.id) || [] : [];
  const matches = query.trim()
    ? chartEmployees.filter((person) => `${person.name} ${person.designation} ${person.department}`.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 6)
    : [];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !selectedId) return;
    const frame = window.requestAnimationFrame(() => {
      const target = canvas.querySelector<HTMLElement>(`[data-org-person="${selectedId}"]`);
      if (!target) return;
      const canvasRect = canvas.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      canvas.scrollTo({
        left: canvas.scrollLeft + targetRect.left + targetRect.width / 2 - canvasRect.left - canvasRect.width / 2,
        behavior: 'auto',
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [chartEmployees.length, selectedId, view]);

  const selectPerson = (person: OrganizationEmployee) => {
    setSelectedId(person.id);
    setQuery('');
    window.setTimeout(() => document.querySelector<HTMLElement>(`[data-org-person="${person.id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' }), 0);
  };

  const exportChart = () => {
    if (!data) return;
    const rows = [['Employee', 'Designation', 'Department', 'Reporting Manager', 'Direct Reports']];
    chartEmployees.forEach((person) => rows.push([
      person.name,
      person.designation,
      person.department,
      employeeMap.get(person.reporting_manager_id || '')?.name || '',
      String(person.reports_count),
    ]));
    const csv = rows.map((row) => row.map((value) => `"${value.replace(/"/g, '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `reknew-organization-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <div className="org-state">Loading organization chart...</div>;
  if (error || !data) return <div className="org-state org-state-error">{error || 'Organization chart is unavailable.'}</div>;

  return (
    <section className="org-chart-section">
      <div className="org-chart-header">
        <div>
          <h2>Organization Chart</h2>
          <p>The full company reporting structure · {data.employee_count} people across {data.department_count} departments.</p>
        </div>
        <div className="org-chart-controls">
          <div className="org-segmented" aria-label="Organization chart view">
            <button type="button" className={view === 'my-line' ? 'active' : ''} onClick={() => setView('my-line')}>My line</button>
            <button type="button" className={view === 'full' ? 'active' : ''} onClick={() => setView('full')}>Full org chart</button>
          </div>
          <div className="org-search-wrap">
            <Search size={14} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a person..." aria-label="Find a person" />
            {matches.length > 0 && (
              <div className="org-search-results">
                {matches.map((person) => <button type="button" key={person.id} onClick={() => selectPerson(person)}><strong>{person.name}</strong><span>{person.designation} · {person.department}</span></button>)}
              </div>
            )}
          </div>
          <button type="button" className="org-export" onClick={exportChart}><Download size={14} /> Export</button>
        </div>
      </div>

      <div ref={canvasRef} className="org-chart-canvas">
        {view === 'full' ? (
          <div className="org-tree-inner">
            <ul className="org-tree">
              {roots.map((person) => <FullTreeNode key={person.id} person={person} childrenByManager={childrenByManager} selectedId={selectedId} onSelect={selectPerson} />)}
            </ul>
          </div>
        ) : focusPerson ? (
          <div className="org-my-line">
            {manager && <Tier label="Reports to" people={[manager]} selectedId={selectedId} onSelect={selectPerson} />}
            {manager && <div className="org-tier-connector" />}
            <Tier label="Manager's team" people={peers.length ? peers : [focusPerson]} selectedId={selectedId} onSelect={selectPerson} />
            {directReports.length > 0 && <div className="org-tier-connector" />}
            <Tier label="Reports to you" people={directReports} selectedId={selectedId} onSelect={selectPerson} />
          </div>
        ) : (
          <div className="org-empty"><Users size={22} />Your employee record was not found in the organization chart.</div>
        )}
      </div>
    </section>
  );
}

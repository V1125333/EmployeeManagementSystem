import { authenticatedFetch } from '@/services/apiClient';
import { useEffect, useMemo, useState } from 'react';
import { RefreshCw, SearchX } from 'lucide-react';
import { Avatar, Badge, Button, Card } from '@/components/ui';
import { Drawer } from '@/components/ui/Drawer';
import { useToast } from '@/components/ui/Toast';
import { AssignEmployeeModal } from '@/components/projects/AssignEmployeeModal';
import { useAuth } from '@/hooks/useAuth';
import '@/styles/bench.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface ProjectRecord {
  id: string;
  name: string;
  code: string;
  status?: string;
}

interface BenchAllocationSlice {
  allocation_id: string;
  project_id: string | null;
  project_name: string;
  allocation_percentage: number;
  allocation_role: string;
  billing_type: string;
  end_date: string | null;
  status: string;
}

interface BenchSummaryCounts {
  ending_soon_count: number;
  multiple_allocations_count: number;
  on_bench_count: number;
  in_projects_count: number;
}

interface BenchEndingSoon {
  employee_id: string;
  employee_name: string;
  designation: string | null;
  profile_image_url: string | null;
  current_project_name: string;
  allocation_end_date: string;
  days_until_end: number;
  available_capacity_percentage: number;
}

interface BenchMultipleAllocation {
  employee_id: string;
  employee_name: string;
  designation: string | null;
  profile_image_url: string | null;
  allocations: BenchAllocationSlice[];
  total_active_allocation_percentage: number;
  available_capacity_percentage: number;
}

interface BenchNowAvailable {
  employee_id: string;
  employee_name: string;
  department: string | null;
  designation: string | null;
  profile_image_url: string | null;
  available_capacity_percentage: number;
}

interface BenchInProject {
  employee_id: string;
  employee_name: string;
  designation: string | null;
  profile_image_url: string | null;
  current_project_name: string;
  allocation_percentage: number;
  allocation_end_date: string | null;
  available_capacity_percentage: number;
}

interface BenchOverviewResponse {
  summary: BenchSummaryCounts;
  ending_soon: BenchEndingSoon[];
  multiple_allocations: BenchMultipleAllocation[];
  on_bench: BenchNowAvailable[];
  in_projects: BenchInProject[];
}

interface ActiveAllocationDetail {
  id: string;
  project_id: string | null;
  project_name: string | null;
  project_code: string | null;
  manager_name: string | null;
  allocation_percentage: number;
  allocation_role: string;
  billing_type: string;
  start_date: string;
  end_date: string | null;
  status: string;
}

interface ActionIntent {
  employeeId: string;
  employeeName: string;
  allocationPercentage: number;
  startDate: string;
  buttonLabel: string;
}

function normalizeRole(role: string | undefined) {
  return (role || '').toLowerCase().replace(/\s+/g, '_');
}

function canViewBench(role: string | undefined) {
  return ['super_admin', 'hr_admin', 'admin', 'global_access', 'manager'].includes(normalizeRole(role));
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toUpperCase() || 'NA';
}

function formatDate(value: string | null) {
  if (!value) return 'Open-ended';
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatCompactDate(value: string | null) {
  if (!value) return 'Open-ended';
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

function nextDay(value: string | null) {
  if (!value) return new Date().toISOString().slice(0, 10);
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + 1);
  return date.toISOString().slice(0, 10);
}

function billingLabel(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function EmptySection({ message }: { message: string }) {
  return (
    <div className="px-5 py-8 text-center text-sm text-[#96917F]">
      {message}
    </div>
  );
}

function SectionHead({
  dotColor,
  background,
  title,
  subtitle,
  countLabel,
}: {
  dotColor: string;
  background: string;
  title: string;
  subtitle: string;
  countLabel?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-[#EDE6D8] px-5 py-4" style={{ backgroundColor: background }}>
      <div className="flex min-w-0 items-center gap-3">
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: dotColor }} />
        <div className="text-sm font-bold text-[#23241F]">{title}</div>
        <div className="text-xs text-[#96917F]">{subtitle}</div>
      </div>
      {countLabel ? (
        <span className="shrink-0 rounded-full bg-white/85 px-2.5 py-1 text-[11px] font-semibold text-[#5B584D]">
          {countLabel}
        </span>
      ) : null}
    </div>
  );
}

export function BenchPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [overview, setOverview] = useState<BenchOverviewResponse | null>(null);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [projectError, setProjectError] = useState('');
  const [actionIntent, setActionIntent] = useState<ActionIntent | null>(null);
  const [splitTarget, setSplitTarget] = useState<BenchMultipleAllocation | null>(null);
  const [splitAllocations, setSplitAllocations] = useState<ActiveAllocationDetail[]>([]);
  const [splitLoading, setSplitLoading] = useState(false);
  const [splitError, setSplitError] = useState('');

  const loadOverview = async () => {
    if (!canViewBench(user?.role)) return;
    setLoading(true);
    setError('');
    try {
      const res = await authenticatedFetch(`${API_BASE}/allocations/bench/overview`);
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) throw new Error(data?.detail || 'Unable to load bench availability.');
      setOverview(data);
    } catch (err) {
      setOverview(null);
      setError(err instanceof Error ? err.message : 'Unable to load bench availability.');
    } finally {
      setLoading(false);
    }
  };

  const loadProjects = async () => {
    if (!canViewBench(user?.role)) return;
    setProjectError('');
    try {
      const params = new URLSearchParams({ status: 'active', limit: '250' });
      const res = await authenticatedFetch(`${API_BASE}/projects/?${params.toString()}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Unable to load active projects.');
      setProjects(Array.isArray(data.projects) ? data.projects : []);
    } catch (err) {
      setProjects([]);
      setProjectError(err instanceof Error ? err.message : 'Unable to load active projects.');
    }
  };

  const openSplit = async (row: BenchMultipleAllocation) => {
    setSplitTarget(row);
    setSplitLoading(true);
    setSplitError('');
    try {
      const res = await authenticatedFetch(`${API_BASE}/allocations/employee/${row.employee_id}/active`);
      const data = await res.json().catch(() => null);
      if (!res.ok || !Array.isArray(data)) throw new Error(data?.detail || 'Unable to load active allocations.');
      setSplitAllocations(data);
    } catch (err) {
      setSplitAllocations([]);
      setSplitError(err instanceof Error ? err.message : 'Unable to load active allocations.');
    } finally {
      setSplitLoading(false);
    }
  };

  useEffect(() => {
    void loadOverview();
    void loadProjects();
  }, [user?.id, user?.email, user?.role]);

  const summaryCards = useMemo(() => {
    if (!overview) return [];
    return [
      {
        key: 'ending-soon',
        label: 'ENDING SOON',
        value: overview.summary.ending_soon_count,
        suffix: 'people',
        background: '#FBE7DE',
        color: '#B84A26',
      },
      {
        key: 'multiple-allocations',
        label: 'MULTIPLE ALLOCATIONS',
        value: overview.summary.multiple_allocations_count,
        suffix: 'people',
        background: '#EDEAF6',
        color: '#4E4A99',
      },
      {
        key: 'on-bench',
        label: 'ON BENCH',
        value: overview.summary.on_bench_count,
        suffix: 'people',
        background: '#E6F2EE',
        color: '#146B5D',
      },
      {
        key: 'in-projects',
        label: 'IN PROJECTS',
        value: overview.summary.in_projects_count,
        suffix: 'people',
        background: '#FBF1DC',
        color: '#96772A',
      },
    ];
  }, [overview]);

  if (!canViewBench(user?.role)) {
    return (
      <div className="animate-fade-up text-[#23241F] bench-plus-jakarta">
        <div className="mb-7">
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Bench &amp; Availability</h1>
          <p className="text-sm text-gray-500">Everyone worth knowing about today — no filtering required.</p>
        </div>
        <div className="rounded-[24px] border border-[#EEE4D6] bg-white p-6 shadow-[0_10px_30px_rgba(36,28,16,0.04)]">
          <Card className="p-10 text-center">
            <div className="text-[15px] font-semibold text-[#23241F]">Access restricted</div>
            <div className="mt-1 text-sm text-[#8A8677]">Only Super Admin, Admin, HR Admin, and managers can view bench availability.</div>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-up text-[#23241F] bench-plus-jakarta">
      <div className="mb-7 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Bench &amp; Availability</h1>
          <p className="text-sm text-gray-500">Everyone worth knowing about today — no filtering required.</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={14} />}
          className="self-start border-[#DDD4C2] bg-white text-[#23241F] hover:bg-[#F9F4EA]"
          onClick={() => void loadOverview()}
        >
          Refresh
        </Button>
      </div>

      <div className="flex flex-col gap-6 rounded-[24px] border border-[#EEE4D6] bg-white p-6 shadow-[0_10px_30px_rgba(36,28,16,0.04)]">
        {loading ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-[92px] animate-pulse rounded-[12px] bg-white/75" />
            ))}
          </div>
        ) : summaryCards.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {summaryCards.map((card) => (
              <div
                key={card.key}
                className="flex min-h-[96px] flex-col justify-center rounded-[18px] px-[18px] py-[16px]"
                style={{ backgroundColor: card.background }}
              >
                <div className="text-[12px] font-extrabold leading-none tracking-[0.02em]" style={{ color: card.color }}>
                  {card.label}
                </div>
                <div className="mt-[14px] flex items-baseline gap-[6px] leading-none text-[#23241F]">
                  <span className="text-[40px] font-extrabold tracking-[-0.03em]">{card.value}</span>
                  <span className="text-[16px] font-bold text-[#23241F]">{card.suffix}</span>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {error ? (
          <Card className="rounded-[14px] border-[#EDE6D8] bg-white p-12 text-center shadow-none">
            <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-[#F3EEE4] text-[#146B5D]">
              <SearchX size={20} />
            </div>
            <div className="text-[15px] font-semibold text-[#23241F]">Could not load bench availability</div>
            <div className="mt-1 text-sm text-[#8A8677]">{error}</div>
          </Card>
        ) : overview ? (
          <>
            <div className="overflow-hidden rounded-[14px] border border-[#EDE6D8] bg-white shadow-none">
              <SectionHead
                dotColor="#E2643A"
                background="#FBF3EE"
                title="Allocation ending soon"
                subtitle="within 14 days — plan their next assignment"
              />
              {overview.ending_soon.length === 0 ? (
                <EmptySection message="No allocation endings need attention in the next 14 days." />
              ) : (
                overview.ending_soon.map((row) => (
                  <div key={row.employee_id} className="grid items-center gap-4 border-t border-[#F3EEE4] px-5 py-3 md:grid-cols-[2fr_1.2fr_1.4fr_1fr]">
                    <div className="flex items-center gap-3">
                      <Avatar initials={initials(row.employee_name)} src={row.profile_image_url} variant="filled" />
                      <div className="min-w-0">
                        <div className="truncate text-[13px] font-semibold text-[#23241F]">{row.employee_name}</div>
                        <div className="truncate text-[11.5px] text-[#96917F]">{row.designation || 'Team member'}</div>
                      </div>
                    </div>
                    <div className="truncate text-[12.5px] text-[#5B584D]">{row.current_project_name}</div>
                    <div>
                      <span className="inline-flex items-center rounded-full bg-[#FBE7DE] px-[11px] py-[5px] text-[11px] font-semibold text-[#B84A26]">
                        {row.days_until_end} {row.days_until_end === 1 ? 'day' : 'days'} left
                      </span>
                    </div>
                    <button
                      type="button"
                      disabled={projects.length === 0}
                      onClick={() => setActionIntent({
                        employeeId: row.employee_id,
                        employeeName: row.employee_name,
                        allocationPercentage: 100,
                        startDate: nextDay(row.allocation_end_date),
                        buttonLabel: 'Plan next role',
                      })}
                      className="justify-self-start rounded-full bg-[#23241F] px-[11px] py-[5px] text-[11px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 md:justify-self-end"
                    >
                      Plan next role
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="overflow-hidden rounded-[14px] border border-[#EDE6D8] bg-white shadow-none">
              <SectionHead
                dotColor="#4E4A99"
                background="#F1EFF9"
                title="Working across multiple allocations"
                subtitle="split across 2+ active projects"
              />
              {overview.multiple_allocations.length === 0 ? (
                <EmptySection message="No employees are currently split across multiple active allocations." />
              ) : (
                overview.multiple_allocations.map((row) => (
                  <div key={row.employee_id} className="bench-multi-row">
                    <div className="bench-multi-person">
                      <Avatar initials={initials(row.employee_name)} src={row.profile_image_url} variant="filled" size="lg" />
                      <div className="min-w-0">
                        <div className="bench-multi-name">{row.employee_name}</div>
                        <div className="bench-multi-role">{row.designation || 'Team member'}</div>
                      </div>
                    </div>
                    <div className="bench-multi-allocations">
                      {row.allocations.slice(0, 2).map((allocation) => (
                        <div key={allocation.allocation_id} className="bench-multi-allocation">
                          <div className="bench-multi-allocation-top">
                            <span className="bench-multi-project">{allocation.project_name}</span>
                            <span className="bench-multi-percent">{allocation.allocation_percentage}%</span>
                          </div>
                          <div className="bench-multi-bar-track">
                            <div className="bench-multi-bar-fill" style={{ width: `${Math.max(4, Math.min(100, allocation.allocation_percentage))}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="bench-multi-actions">
                      {row.allocations.length > 2 ? <span className="bench-multi-more">+{row.allocations.length - 2} more</span> : null}
                      <button
                        type="button"
                        onClick={() => void openSplit(row)}
                        className="bench-multi-button"
                      >
                        View split
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="overflow-hidden rounded-[14px] border border-[#EDE6D8] bg-white shadow-none">
              <SectionHead
                dotColor="#146B5D"
                background="#EEF6F3"
                title="On the bench — available now"
                subtitle="no active allocation, ready to staff"
                countLabel={`${overview.on_bench.length} members`}
              />
              <div className="bench-open-header">
                <div>EMPLOYEE</div>
                <div>DEPARTMENT</div>
                <div>DESIGNATION</div>
                <div>AVAILABLE</div>
                <div>ACTION</div>
              </div>
              {overview.on_bench.length === 0 ? (
                <EmptySection message="No employees are currently fully on the bench." />
              ) : (
                <div className="bench-open-scroll">
                  {overview.on_bench.map((row) => (
                    <div key={row.employee_id} className="bench-open-row">
                      <div className="bench-open-person">
                        <Avatar initials={initials(row.employee_name)} src={row.profile_image_url} variant="filled" />
                        <div className="min-w-0">
                          <div className="bench-open-name">{row.employee_name}</div>
                          <div className="bench-open-role">Bench</div>
                        </div>
                      </div>
                      <div className="bench-open-cell">{row.department || 'Not assigned'}</div>
                      <div className="bench-open-cell">{row.designation || 'Team member'}</div>
                      <div className="bench-open-available">{row.available_capacity_percentage}%</div>
                      <button
                        type="button"
                        disabled={projects.length === 0}
                        onClick={() => setActionIntent({
                          employeeId: row.employee_id,
                          employeeName: row.employee_name,
                          allocationPercentage: 100,
                          startDate: new Date().toISOString().slice(0, 10),
                          buttonLabel: 'Assign',
                        })}
                        className="bench-open-button disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Assign
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="overflow-hidden rounded-[14px] border border-[#EDE6D8] bg-white shadow-none">
              <SectionHead
                dotColor="#96772A"
                background="#FBF6EA"
                title="Currently in projects"
                subtitle="single active allocation"
              />
              <div className="bench-project-header">
                <div>EMPLOYEE</div>
                <div>PROJECT</div>
                <div>ALLOCATION</div>
                <div>AVAILABLE</div>
                <div>END DATE</div>
              </div>
              {overview.in_projects.length === 0 ? (
                <EmptySection message="No employees currently sit in the single-allocation project bucket." />
              ) : (
                <div className="bench-project-scroll">
                  {overview.in_projects.map((row) => (
                    <div key={row.employee_id} className="bench-project-row">
                      <div className="bench-project-person">
                        <Avatar initials={initials(row.employee_name)} src={row.profile_image_url} variant="filled" />
                        <div className="min-w-0">
                          <div className="bench-project-name">{row.employee_name}</div>
                          <div className="bench-project-role">{row.designation || 'Team member'}</div>
                        </div>
                      </div>
                      <div className="bench-project-cell">{row.current_project_name}</div>
                      <div className="bench-project-percent">{row.allocation_percentage}%</div>
                      <div className="bench-project-available">{row.available_capacity_percentage}%</div>
                      <div className="bench-project-end">
                        {row.allocation_end_date ? `until ${formatCompactDate(row.allocation_end_date)}` : 'Open-ended'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : null}

        {projectError && (
          <div className="rounded-[12px] border border-[#F0D8CC] bg-[#FBF3EE] px-4 py-3 text-sm text-[#B84A26]">
            Assignment is temporarily unavailable: {projectError}
          </div>
        )}
      </div>

      <Drawer
        open={Boolean(splitTarget)}
        onClose={() => {
          setSplitTarget(null);
          setSplitAllocations([]);
          setSplitError('');
        }}
        title={splitTarget ? `${splitTarget.employee_name} allocation split` : 'Allocation split'}
        subtitle={splitTarget ? `${splitTarget.available_capacity_percentage}% available across ${splitTarget.allocations.length} active allocations` : undefined}
        footer={splitTarget ? (
          <div className="flex justify-end">
            <Button variant="soft" onClick={() => setSplitTarget(null)}>Close</Button>
          </div>
        ) : undefined}
        width="w-[620px]"
      >
        {splitLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="h-24 animate-pulse rounded-2xl bg-[#F7F2E8]" />
            ))}
          </div>
        ) : splitError ? (
          <div className="rounded-2xl border border-[#F0D8CC] bg-[#FBF3EE] px-4 py-4 text-sm text-[#B84A26]">{splitError}</div>
        ) : (
          <div className="space-y-3">
            {splitAllocations.map((allocation) => (
              <div key={allocation.id} className="rounded-2xl border border-[#EDE6D8] bg-white px-4 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-bold text-[#23241F]">
                      {allocation.project_name || 'Untitled project'}
                    </div>
                    <div className="mt-1 text-xs text-[#8A8677]">
                      {allocation.allocation_role} · {billingLabel(allocation.billing_type)} · {allocation.manager_name || 'No manager assigned'}
                    </div>
                  </div>
                  <Badge variant="info">{allocation.allocation_percentage}%</Badge>
                </div>
                <div className="mt-3 h-[6px] overflow-hidden rounded-full bg-[#F3EEE4]">
                  <div className="h-full rounded-full bg-[#4E4A99]" style={{ width: `${Math.max(4, Math.min(100, allocation.allocation_percentage))}%` }} />
                </div>
                <div className="mt-3 grid gap-2 text-xs text-[#5B584D] md:grid-cols-3">
                  <div>
                    <div className="font-semibold text-[#23241F]">Project</div>
                    <div>{allocation.project_code || 'No code'}</div>
                  </div>
                  <div>
                    <div className="font-semibold text-[#23241F]">Start</div>
                    <div>{formatDate(allocation.start_date)}</div>
                  </div>
                  <div>
                    <div className="font-semibold text-[#23241F]">End</div>
                    <div>{formatDate(allocation.end_date)}</div>
                  </div>
                </div>
              </div>
            ))}
            {!splitAllocations.length && <EmptySection message="No active allocations were returned for this employee." />}
          </div>
        )}
      </Drawer>

      <AssignEmployeeModal
        open={Boolean(actionIntent)}
        project={null}
        projects={projects}
        user={user}
        initialEmployeeId={actionIntent?.employeeId || ''}
        initialAllocationPercentage={actionIntent?.allocationPercentage || 100}
        initialStartDate={actionIntent?.startDate || ''}
        lockEmployee
        onClose={() => setActionIntent(null)}
        onAssigned={() => {
          showToast({ message: `${actionIntent?.employeeName || 'Employee'} assignment saved.` });
          setActionIntent(null);
          void loadOverview();
        }}
      />
    </div>
  );
}

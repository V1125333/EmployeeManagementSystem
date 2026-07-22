import { useEffect, useMemo, useRef, useState, type ElementType } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Award, BriefcaseBusiness, Cake, CalendarDays, UserPlus } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface KpiDetail {
  employee_id: string;
  name: string;
  date: string;
  subtitle?: string;
}

interface KpiMetric {
  label: string;
  value: string | number | null | undefined;
  trend?: string;
  icon: string;
  color: string;
  details?: KpiDetail[];
}

const fallbackKpis: KpiMetric[] = [
  { label: 'Total Employees', value: 0, icon: 'Users', color: '#d97a34' },
  { label: 'Active Employees', value: 0, icon: 'UserCheck', color: '#3f8a48' },
  { label: 'Inactive', value: 0, icon: 'UserX', color: '#8a8371' },
  { label: 'Pending Leave', value: 0, icon: 'Calendar', color: '#d97a34' },
  { label: "Today's Attendance", value: 0, icon: 'CheckCircle', color: '#d97a34' },
  { label: 'New This Month', value: 0, trend: 'this month', icon: 'UserPlus', color: '#d97a34', details: [] },
  { label: 'Upcoming Birthdays', value: 0, trend: 'this week', icon: 'Cake', color: '#d97a34', details: [] },
  { label: 'Work Anniversaries', value: 0, trend: 'this month', icon: 'Award', color: '#d97a34', details: [] },
  { label: 'Bench Capacity', value: 0, trend: 'available now', icon: 'BriefcaseBusiness', color: '#d97a34' },
];

function numericValue(metric: KpiMetric | undefined) {
  const parsed = Number(String(metric?.value ?? 0).replace('%', ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function DetailsPopover({ metric, onClose }: { metric: KpiMetric; onClose: () => void }) {
  return (
    <div className="absolute left-5 right-5 top-[calc(100%-12px)] z-[80] rounded-2xl border border-[#ece0cb] bg-white p-2 shadow-[0_24px_70px_rgba(60,40,10,.18)]">
      <div className="flex items-center justify-between px-2 py-1.5">
        <div className="text-[11px] font-bold uppercase tracking-[.08em] text-[#a99e8a]">{metric.label}</div>
        <button type="button" onClick={onClose} className="text-xs font-semibold text-[#d97a34]">Close</button>
      </div>
      <div className="max-h-[220px] overflow-y-auto">
        {metric.details?.length ? metric.details.slice(0, 8).map((item) => (
          <div key={`${metric.label}-${item.employee_id}`} className="rounded-xl px-2 py-2 hover:bg-[#fbf5ea]">
            <div className="text-[13px] font-bold text-[#1f2430]">{item.name}</div>
            <div className="mt-0.5 text-[12px] text-[#8a8371]">
              {new Date(`${item.date}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              {item.subtitle ? ` · ${item.subtitle}` : ''}
            </div>
          </div>
        )) : <div className="px-2 py-5 text-center text-sm text-[#8a8371]">No employees in this period.</div>}
      </div>
    </div>
  );
}

function FeatureMetricCard({
  metric,
  icon: Icon,
  label,
  action,
  onAction,
  open,
  onClose,
}: {
  metric: KpiMetric;
  icon: ElementType;
  label: string;
  action: string;
  onAction: () => void;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <div className="relative flex min-h-[188px] flex-col justify-between rounded-[22px] border border-[#ece0cb] bg-white p-6 shadow-[0_3px_10px_rgba(60,40,10,.025)]">
      <div className="flex items-start justify-between">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#fbeee1] text-[#d97a34]"><Icon size={17} /></div>
        <div className="text-[12px] font-medium text-[#a99e8a]">{metric.trend}</div>
      </div>
      <div>
        <div className="text-[32px] font-bold leading-none tracking-[-.03em] text-[#1f2430]">{numericValue(metric)}</div>
        <div className="mt-2 text-[15px] text-[#8a6a4b]">{label}</div>
        <button type="button" data-kpi-trigger onClick={onAction} className="mt-3 inline-flex items-center text-[13px] font-bold text-[#df681d] hover:underline">
          {action} →
        </button>
      </div>
      {open && <DetailsPopover metric={metric} onClose={onClose} />}
    </div>
  );
}

export function KpiCards() {
  const navigate = useNavigate();
  const [kpis, setKpis] = useState<KpiMetric[]>(fallbackKpis);
  const [openDetail, setOpenDetail] = useState<string | null>(null);
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/kpis`)
      .then((response) => {
        if (!response.ok) throw new Error(`Dashboard metrics failed (${response.status})`);
        return response.json();
      })
      .then((data) => setKpis(data.kpis?.length ? data.kpis : fallbackKpis))
      .catch(() => setKpis(fallbackKpis));
  }, []);

  useEffect(() => {
    if (!openDetail) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!sectionRef.current?.contains(event.target as Node)) setOpenDetail(null);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpenDetail(null);
    };
    document.addEventListener('pointerdown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [openDetail]);

  const metrics = useMemo(() => new Map(kpis.map((metric) => [metric.label, metric])), [kpis]);
  const getMetric = (label: string) => metrics.get(label) || fallbackKpis.find((metric) => metric.label === label)!;
  const total = getMetric('Total Employees');
  const active = getMetric('Active Employees');
  const inactive = getMetric('Inactive');
  const pendingLeave = getMetric('Pending Leave');
  const attendance = getMetric("Today's Attendance");
  const attendanceRate = numericValue(attendance);
  const featureMetrics = [
    { metric: getMetric('New This Month'), icon: UserPlus, label: 'New this month', action: 'View' },
    { metric: getMetric('Upcoming Birthdays'), icon: Cake, label: 'Upcoming Birthday', action: 'View people' },
    { metric: getMetric('Work Anniversaries'), icon: Award, label: 'Work Anniversary', action: 'View people' },
    { metric: getMetric('Bench Capacity'), icon: BriefcaseBusiness, label: 'Bench Capacity', action: 'View bench' },
  ];

  const openMetric = (metric: KpiMetric) => {
    if (metric.label === 'Bench Capacity') {
      navigate('/bench');
      return;
    }
    if (metric.details) setOpenDetail((current) => current === metric.label ? null : metric.label);
    else navigate('/employees');
  };

  return (
    <div ref={sectionRef} className="grid gap-5 xl:grid-cols-[1.08fr_1fr]">
      <section className="relative flex min-h-[400px] flex-col overflow-hidden rounded-[24px] border border-[#ece0cb] bg-[#fffdf9] p-8 shadow-[0_3px_12px_rgba(60,40,10,.025)]">
        <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(217,122,52,.12),rgba(217,122,52,.025)_55%,transparent_72%)]" />
        <div className="relative flex items-start justify-between gap-4">
          <div>
            <div className="text-[15px] font-medium text-[#8a6a4b]">Headcount</div>
            <div className="mt-3 flex flex-wrap items-end gap-x-4 gap-y-1">
              <div className="text-[64px] font-bold leading-[.9] tracking-[-.055em] text-[#1f2430]">{numericValue(total)}</div>
              <div className="pb-1 text-[14px] font-semibold">
                <span className="text-[#29943a]">{numericValue(active)} active</span>
                <span className="mx-1 text-[#b8ad9a]">·</span>
                <span className="text-[#637a35]">{numericValue(inactive)} inactive</span>
              </div>
            </div>
          </div>
          <button type="button" onClick={() => navigate('/employees')} className="rounded-full bg-[#f7f1e6] px-4 py-2 text-[12px] font-medium text-[#9a704b] hover:bg-[#f1e6d6]">
            Total employees
          </button>
        </div>

        <div className="relative mt-auto grid gap-3 md:grid-cols-2">
          <button type="button" onClick={() => navigate('/time-off?tab=leave')} className="rounded-2xl border border-[#ece0cb] bg-white px-5 py-4 text-left transition-transform hover:-translate-y-0.5">
            <div className="flex items-center gap-2 text-[14px] text-[#8a6a4b]"><CalendarDays size={15} className="text-[#d97a34]" /> Pending Leave</div>
            <div className="mt-2 text-[31px] font-bold leading-none text-[#1f2430]">{numericValue(pendingLeave)}</div>
          </button>
          <button type="button" onClick={() => navigate('/time-off?tab=attendance')} className={`rounded-2xl border px-5 py-4 text-left transition-transform hover:-translate-y-0.5 ${attendanceRate < 75 ? 'border-[#f2b8b5] bg-[#fff0f0]' : 'border-[#d6e8d3] bg-[#f2faf0]'}`}>
            <div className={`flex items-center gap-2 text-[14px] ${attendanceRate < 75 ? 'text-[#d34a43]' : 'text-[#477b43]'}`}><Activity size={15} /> Today&apos;s Attendance</div>
            <div className="mt-2 flex flex-wrap items-end gap-2">
              <div className={`text-[31px] font-bold leading-none ${attendanceRate < 75 ? 'text-[#df403b]' : 'text-[#39773c]'}`}>{attendanceRate}%</div>
              <div className={`text-[12px] ${attendanceRate < 75 ? 'text-[#ca514e]' : 'text-[#5d8759]'}`}>{attendanceRate < 75 ? '▼ needs attention' : 'On track'}</div>
            </div>
          </button>
        </div>
      </section>

      <div className="grid gap-5 sm:grid-cols-2">
        {featureMetrics.map(({ metric, icon, label, action }) => (
          <FeatureMetricCard
            key={metric.label}
            metric={metric}
            icon={icon}
            label={label}
            action={action}
            open={openDetail === metric.label}
            onClose={() => setOpenDetail(null)}
            onAction={() => openMetric(metric)}
          />
        ))}
      </div>
    </div>
  );
}

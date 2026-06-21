import { useState, useEffect } from 'react';
import {
  Users, UserCheck, UserX, Calendar, CheckCircle, Cake, Award,
} from 'lucide-react';
import { Card } from '@/components/ui';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const iconMap: Record<string, React.ElementType> = {
  Users, UserCheck, UserX, Calendar, CheckCircle, Cake, Award,
};

interface KpiMetric {
  label: string;
  value: string | number | null | undefined;
  trend?: string;
  icon: string;
  color: string;
  details?: Array<{
    employee_id: string;
    name: string;
    date: string;
    subtitle?: string;
  }>;
}

function formatKpiValue(kpi: KpiMetric) {
  if (kpi.label !== "Today's Attendance") {
    return kpi.value ?? '0';
  }

  if (kpi.value === null || kpi.value === undefined) {
    return '0%';
  }

  const rawValue = String(kpi.value).trim();
  if (!rawValue) {
    return '0%';
  }

  const numericValue = Number(rawValue.replace(/%/g, ''));
  if (!Number.isFinite(numericValue)) {
    return '0%';
  }

  return `${numericValue}%`;
}

export function KpiCards() {
  const [kpis, setKpis] = useState<KpiMetric[]>([]);
  const [openDetail, setOpenDetail] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/kpis`)
      .then((res) => res.json())
      .then((data) => setKpis(data.kpis || []))
      .catch(() => {
        // Fallback to zeros if backend is down
        setKpis([
          { label: 'Total Employees', value: '0', icon: 'Users', color: '#66785F' },
          { label: 'Active Employees', value: '0', icon: 'UserCheck', color: '#7BAE7F' },
          { label: 'Inactive', value: '0', icon: 'UserX', color: '#9CA3AF' },
          { label: 'Pending Leave', value: '0', icon: 'Calendar', color: '#D6A85F' },
          { label: "Today's Attendance", value: '0%', icon: 'CheckCircle', color: '#7E9BB7' },
          { label: 'Upcoming Birthdays', value: '0', trend: 'this week', icon: 'Cake', color: '#D97C7C' },
          { label: 'Work Anniversaries', value: '0', trend: 'this month', icon: 'Award', color: '#A3B18A' },
        ]);
      });
  }, []);

  return (
    <div className="relative z-20 grid grid-cols-7 gap-3 overflow-visible">
      {kpis.map((kpi) => {
        const IconComp = iconMap[kpi.icon] || CheckCircle;
        const hasDetails = !!kpi.details?.length;
        const isOpen = openDetail === kpi.label;
        return (
          <Card key={kpi.label} className={cn('relative overflow-visible px-4 py-[18px]', hasDetails && 'cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-card-md')}>
            <button
              type="button"
              disabled={!hasDetails}
              onClick={() => setOpenDetail((current) => current === kpi.label ? null : kpi.label)}
              className="w-full text-left disabled:cursor-default"
              aria-expanded={isOpen}
            >
              <div className="flex items-center justify-between mb-3">
                <div
                  className="w-[34px] h-[34px] rounded-[9px] flex items-center justify-center"
                  style={{ backgroundColor: `${kpi.color}12` }}
                >
                  <IconComp size={16} style={{ color: kpi.color }} />
                </div>
                {kpi.trend && (
                  <span className="text-[10.5px] text-gray-400 font-medium">
                    {kpi.trend}
                  </span>
                )}
              </div>
              <div className="text-2xl font-bold text-[#2F3437] tracking-tight mb-0.5">
                {formatKpiValue(kpi)}
              </div>
              <div className="text-xs text-gray-500 font-medium">{kpi.label}</div>
              {hasDetails && (
                <div className="mt-2 text-[11px] font-semibold text-olive">
                  {isOpen ? 'Hide people' : 'View people'}
                </div>
              )}
            </button>
            {isOpen && hasDetails && (
              <div className="absolute right-0 top-[calc(100%+10px)] z-[80] w-[280px] rounded-2xl border border-[#DDE3EA] bg-white p-2 shadow-[0_24px_70px_rgba(17,24,39,0.18)]">
                <div className="px-2 py-1.5 text-[11px] font-bold uppercase tracking-wide text-gray-400">{kpi.label}</div>
                <div className="max-h-[220px] overflow-y-auto">
                  {kpi.details!.slice(0, 8).map((item) => (
                    <div key={`${kpi.label}-${item.employee_id}`} className="rounded-xl px-2 py-2 hover:bg-hover-bg">
                      <div className="text-[13px] font-bold text-[#2F3437]">{item.name}</div>
                      <div className="mt-0.5 text-[12px] text-gray-500">
                        {new Date(`${item.date}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        {item.subtitle ? ` · ${item.subtitle}` : ''}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

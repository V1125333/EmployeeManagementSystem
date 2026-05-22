import { useState, useEffect } from 'react';
import {
  Users, UserCheck, UserX, Calendar, CheckCircle, Cake, Award,
} from 'lucide-react';
import { Card } from '@/components/ui';
import { cn } from '@/utils/cn';

const API_BASE = 'http://localhost:8000/api/v1';

const iconMap: Record<string, React.ElementType> = {
  Users, UserCheck, UserX, Calendar, CheckCircle, Cake, Award,
};

interface KpiMetric {
  label: string;
  value: string;
  trend?: string;
  icon: string;
  color: string;
}

export function KpiCards() {
  const [kpis, setKpis] = useState<KpiMetric[]>([]);

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
    <div className="grid grid-cols-7 gap-3">
      {kpis.map((kpi) => {
        const IconComp = iconMap[kpi.icon] || CheckCircle;
        return (
          <Card key={kpi.label} className="px-4 py-[18px]">
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
              {kpi.value}
            </div>
            <div className="text-xs text-gray-500 font-medium">{kpi.label}</div>
          </Card>
        );
      })}
    </div>
  );
}

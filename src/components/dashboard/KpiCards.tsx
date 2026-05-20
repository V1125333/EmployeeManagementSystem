import {
  Users, UserCheck, UserX, Calendar, CheckCircle, Cake, Award,
} from 'lucide-react';
import { Card } from '@/components/ui';
import { kpiMetrics } from '@/data/mockData';
import { cn } from '@/utils/cn';

const iconMap: Record<string, React.ElementType> = {
  Users, UserCheck, UserX, Calendar, CheckCircle, Cake, Award,
};

export function KpiCards() {
  return (
    <div className="grid grid-cols-7 gap-3">
      {kpiMetrics.map((kpi, i) => {
        const IconComp = iconMap[kpi.icon] || CheckCircle;
        return (
          <Card
            key={kpi.label}
            className="px-4 py-[18px] animate-fade-up"
            style={{ animationDelay: `${i * 50}ms` }}
          >
            <div className="flex items-center justify-between mb-3">
              <div
                className="w-[34px] h-[34px] rounded-[9px] flex items-center justify-center"
                style={{ backgroundColor: `${kpi.color}12` }}
              >
                <IconComp size={16} style={{ color: kpi.color }} />
              </div>
              {kpi.trendUp !== null ? (
                <span
                  className={cn(
                    'text-[11px] font-semibold flex items-center gap-0.5',
                    kpi.trendUp ? 'text-status-success' : 'text-status-error'
                  )}
                >
                  {kpi.trendUp ? '↑' : '↓'} {kpi.trend}
                </span>
              ) : (
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

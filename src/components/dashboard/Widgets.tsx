import { CalendarDays } from 'lucide-react';
import { Card, CardHeader, Avatar, Badge, Button } from '@/components/ui';
import { leaveCalendar, onLeaveToday } from '@/data/mockData';
import { cn } from '@/utils/cn';

// ─── Team Leave Calendar ───
export function TeamLeaveCalendar() {
  const dayNames = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  const startDay = 4; // May 2026 starts Thursday

  return (
    <Card>
      <CardHeader
        title="Team Leave Calendar — May 2026"
        icon={<CalendarDays size={16} />}
        action={<Button variant="ghost" size="sm">Full View</Button>}
      />
      <div className="px-5 py-3.5">
        <div className="grid grid-cols-7 gap-1 text-center">
          {dayNames.map((d, i) => (
            <div key={i} className="text-[10px] font-semibold text-gray-400 py-1">
              {d}
            </div>
          ))}
          {Array.from({ length: startDay }, (_, i) => (
            <div key={`e${i}`} />
          ))}
          {leaveCalendar.map((d) => (
            <div
              key={d.day}
              className={cn(
                'w-8 h-8 mx-auto rounded-lg flex items-center justify-center text-xs relative',
                d.count > 2
                  ? 'bg-status-warning/15 text-status-warning font-semibold'
                  : d.count > 0
                  ? 'bg-sage/15 text-olive font-semibold'
                  : 'text-gray-500',
                d.count > 0 && 'cursor-pointer hover:ring-1 hover:ring-olive/20'
              )}
            >
              {d.day}
              {d.count > 0 && (
                <span
                  className={cn(
                    'absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full',
                    d.count > 2 ? 'bg-status-warning' : 'bg-sage'
                  )}
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

// ─── On Leave Today ───
const leaveTypeVariant: Record<string, 'info' | 'error' | 'sage'> = {
  Vacation: 'info',
  'Sick Leave': 'error',
  Personal: 'sage',
};

export function OnLeaveToday() {
  return (
    <Card>
      <CardHeader
        title="On Leave Today"
        icon={<CalendarDays size={16} />}
        action={<Badge variant="warning">{onLeaveToday.length} employees</Badge>}
      />
      <div className="py-1">
        {onLeaveToday.map((l, i) => (
          <div
            key={l.name}
            className={cn(
              'flex items-center gap-3 px-5 py-2.5 hover:bg-hover-bg transition-colors cursor-pointer',
              i < onLeaveToday.length - 1 && 'border-b border-[#E5E7EB]'
            )}
          >
            <Avatar initials={l.avatar} size="md" />
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold text-[#2F3437] truncate">
                {l.name}
              </div>
              <div className="text-[11.5px] text-gray-500">{l.duration}</div>
            </div>
            <Badge variant={leaveTypeVariant[l.type] || 'neutral'}>
              {l.type}
            </Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}

import { useState, useEffect } from 'react';
import { Card, CardHeader, Avatar, Badge } from '@/components/ui';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// ─── On Leave Today ───

interface LeaveEntry {
  name: string;
  avatar: string;
  type: string;
  duration: string;
}

export function OnLeaveToday() {
  const [entries, setEntries] = useState<LeaveEntry[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/on-leave-today`)
      .then((res) => res.json())
      .then((data) => setEntries(data.on_leave || []))
      .catch(() => setEntries([]));
  }, []);

  return (
    <Card className="flex-1">
      <CardHeader title="On Leave Today" badge={`${entries.length}`} />
      <div className="px-5 pb-4">
        {entries.length === 0 ? (
          <div className="text-center py-6 text-[13px] text-gray-400">No one is on leave today</div>
        ) : (
          <div className="flex flex-col gap-2">
            {entries.map((entry) => (
              <div key={entry.name} className="flex items-center gap-3 py-2 px-3 rounded-xl bg-warm-bg">
                <Avatar initials={entry.avatar} size="sm" />
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold text-[var(--color-brand-navy)] truncate">{entry.name}</div>
                  <div className="text-[11px] text-gray-400">{entry.duration}</div>
                </div>
                <Badge variant="warning">{entry.type}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

// ─── Team Leave Calendar ───

interface CalendarDay {
  day: number;
  count: number;
}

export function TeamLeaveCalendar() {
  const [days, setDays] = useState<CalendarDay[]>([]);
  const [month, setMonth] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/leave-calendar`)
      .then((res) => res.json())
      .then((data) => {
        setDays(data.calendar || []);
        setMonth(data.month || '');
      })
      .catch(() => setDays([]));
  }, []);

  const today = new Date().getDate();
  const monthStart = month ? new Date(`${month} 1`) : null;
  const leadingBlankDays = monthStart && Number.isFinite(monthStart.getTime()) ? monthStart.getDay() : 0;
  const calendarCells = [
    ...Array.from({ length: leadingBlankDays }, (_, index) => ({ key: `blank-${index}`, day: null as number | null, count: 0 })),
    ...days.map((day) => ({ key: `day-${day.day}`, day: day.day, count: day.count })),
  ];

  return (
    <Card className="flex-1">
      <CardHeader title="Team Leave Calendar" badge={month} />
      <div className="px-5 pb-4">
        <div className="grid grid-cols-7 overflow-hidden rounded-t-lg border border-b-0 border-[var(--color-border)] bg-warm-bg">
          {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
            <div
              key={i}
              className={cn(
                'border-b border-[var(--color-border)] py-2 text-center text-[10px] font-semibold text-gray-400',
                i < 6 && 'border-r border-[var(--color-border)]'
              )}
            >
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 overflow-hidden rounded-b-lg border border-t-0 border-[var(--color-border)]">
          {calendarCells.map((d, index) => (
            <div
              key={d.key}
              className={cn(
                'relative flex aspect-square items-center justify-center border-b border-r border-[var(--color-border)] text-[11px] font-medium transition-colors',
                (index + 1) % 7 === 0 && 'border-r-0',
                index >= calendarCells.length - 7 && 'border-b-0',
                !d.day && 'bg-warm-bg text-transparent',
                d.day === today
                  ? 'bg-accent-light text-[var(--color-nav-active-text)] ring-1 ring-inset ring-accent-mid'
                  : d.count > 0
                    ? 'bg-status-warning/10 text-[var(--color-brand-navy)]'
                    : 'text-gray-500 hover:bg-hover-bg'
              )}
            >
              {d.day}
              {d.count > 0 && d.day !== today && (
                <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-status-warning" />
              )}
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

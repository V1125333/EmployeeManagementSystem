import { useState, useEffect } from 'react';
import { Card, CardHeader, Avatar, Badge } from '@/components/ui';
import { cn } from '@/utils/cn';

const API_BASE = 'http://localhost:8000/api/v1';

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
                  <div className="text-[13px] font-semibold text-[#2F3437] truncate">{entry.name}</div>
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

  return (
    <Card className="flex-1">
      <CardHeader title="Team Leave Calendar" badge={month} />
      <div className="px-5 pb-4">
        <div className="grid grid-cols-7 gap-1 mb-1.5">
          {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
            <div key={i} className="text-center text-[10px] font-bold text-gray-400 py-1">{d}</div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {days.map((d) => (
            <div
              key={d.day}
              className={cn(
                'aspect-square rounded-md flex items-center justify-center text-[11px] font-medium relative transition-colors',
                d.day === today
                  ? 'bg-olive text-white'
                  : d.count > 0
                  ? 'bg-status-warning/10 text-[#2F3437]'
                  : 'text-gray-400 hover:bg-hover-bg'
              )}
            >
              {d.day}
              {d.count > 0 && d.day !== today && (
                <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-status-warning" />
              )}
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

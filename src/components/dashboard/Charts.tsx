import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, CartesianGrid,
} from 'recharts';
import { Card, CardHeader } from '@/components/ui';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const deptChartColors = [
  'var(--color-brand-orange)', 'var(--color-brand-orange)', 'var(--color-brand-navy)', 'var(--color-brand-orange)',
  'var(--color-brand-orange)', 'var(--color-brand-orange)', 'var(--color-text-muted)', 'var(--color-text-muted)',
];

export function DeptChart() {
  const [data, setData] = useState<{ dept: string; count: number }[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/department-chart`)
      .then((res) => res.json())
      .then((d) => setData(d.departments || []))
      .catch(() => setData([]));
  }, []);

  return (
    <Card className="flex-1">
      <CardHeader title="Department Headcount" />
      <div className="px-5 pb-5 h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barSize={28}>
            <XAxis dataKey="dept" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} axisLine={false} tickLine={false} allowDecimals={false} />
            <Tooltip
              contentStyle={{
                background: 'var(--color-brand-surface)', border: '1px solid var(--color-border)',
                borderRadius: 12, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
              }}
            />
            <Bar
              dataKey="count"
              radius={[6, 6, 0, 0]}
              fill="var(--color-brand-orange)"
              // Color each bar differently
              shape={(props: any) => {
                const { x, y, width, height, index } = props;
                return (
                  <rect
                    x={x} y={y} width={width} height={height}
                    fill={deptChartColors[index % deptChartColors.length]}
                    rx={6} ry={6}
                  />
                );
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export function AttendanceTrend() {
  const [data, setData] = useState<{ day: string; rate: number }[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/attendance-trend`)
      .then((res) => res.json())
      .then((d) => setData(d.trend || []))
      .catch(() => setData([]));
  }, []);

  return (
    <Card className="flex-1">
      <CardHeader title="Attendance Trend" badge="10 days" />
      <div className="px-5 pb-5 h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="attendanceGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-brand-orange)" stopOpacity={0.15} />
                <stop offset="100%" stopColor="var(--color-brand-orange)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
            <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} axisLine={false} tickLine={false} />
            <YAxis domain={[60, 100]} tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                background: 'var(--color-brand-surface)', border: '1px solid var(--color-border)',
                borderRadius: 12, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
              }}
              formatter={(value: number) => [`${value}%`, 'Attendance']}
            />
            <Area
              type="monotone" dataKey="rate" stroke="var(--color-brand-orange)" strokeWidth={2}
              fill="url(#attendanceGrad)" dot={{ fill: 'var(--color-brand-orange)', r: 3 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

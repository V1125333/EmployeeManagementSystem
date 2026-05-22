import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, CartesianGrid,
} from 'recharts';
import { Card, CardHeader } from '@/components/ui';

const API_BASE = 'http://localhost:8000/api/v1';

const deptChartColors = [
  '#66785F', '#A3B18A', '#7E9BB7', '#D6A85F',
  '#D97C7C', '#7BAE7F', '#8B9F82', '#B8C4A8',
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
            <XAxis dataKey="dept" tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} allowDecimals={false} />
            <Tooltip
              contentStyle={{
                background: '#FEFEFC', border: '1px solid #E5E7EB',
                borderRadius: 12, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
              }}
            />
            <Bar
              dataKey="count"
              radius={[6, 6, 0, 0]}
              fill="#66785F"
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
                <stop offset="0%" stopColor="#66785F" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#66785F" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
            <YAxis domain={[60, 100]} tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                background: '#FEFEFC', border: '1px solid #E5E7EB',
                borderRadius: 12, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
              }}
              formatter={(value: number) => [`${value}%`, 'Attendance']}
            />
            <Area
              type="monotone" dataKey="rate" stroke="#66785F" strokeWidth={2}
              fill="url(#attendanceGrad)" dot={{ fill: '#66785F', r: 3 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

import { Users, CheckCircle } from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { Card, CardHeader, Button } from '@/components/ui';
import { departmentData, attendanceData, deptChartColors } from '@/data/mockData';

// Shared custom tooltip
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-warm-card border border-[#E5E7EB] rounded-[10px] px-3.5 py-2 shadow-card-md text-xs">
      <div className="text-gray-500 mb-0.5">{label}</div>
      <div className="text-[#2F3437] font-semibold">{payload[0].value}</div>
    </div>
  );
}

export function DeptChart() {
  return (
    <Card className="h-full">
      <CardHeader
        title="Department Headcount"
        icon={<Users size={16} />}
        action={<Button variant="ghost" size="sm">View All</Button>}
      />
      <div className="px-4 pt-4 pb-2">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={departmentData} barSize={28}>
            <XAxis
              dataKey="dept"
              tick={{ fontSize: 11, fill: '#6B7280' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#9CA3AF' }}
              axisLine={false}
              tickLine={false}
              width={35}
            />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
              {departmentData.map((_, i) => (
                <Cell key={i} fill={deptChartColors[i % deptChartColors.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export function AttendanceTrend() {
  return (
    <Card className="h-full">
      <CardHeader
        title="Attendance Trend"
        icon={<CheckCircle size={16} />}
        action={<Button variant="ghost" size="sm">Last 2 Weeks</Button>}
      />
      <div className="px-4 pt-4 pb-2">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={attendanceData}>
            <XAxis
              dataKey="day"
              tick={{ fontSize: 11, fill: '#6B7280' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[80, 100]}
              tick={{ fontSize: 11, fill: '#9CA3AF' }}
              axisLine={false}
              tickLine={false}
              width={35}
            />
            <Tooltip content={<ChartTooltip />} />
            <Line
              type="monotone"
              dataKey="rate"
              stroke="#66785F"
              strokeWidth={2.5}
              dot={{ r: 3.5, fill: '#FEFEFC', stroke: '#66785F', strokeWidth: 2 }}
              activeDot={{ r: 5, fill: '#66785F' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

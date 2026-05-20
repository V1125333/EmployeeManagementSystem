import { useState } from 'react';
import { UserPlus, CheckCircle, Megaphone } from 'lucide-react';
import { Button } from '@/components/ui';
import {
  KpiCards,
  PendingTasks,
  DeptChart,
  AttendanceTrend,
  TeamLeaveCalendar,
  OnLeaveToday,
} from '@/components/dashboard';
import { AddEmployeeDrawer } from '@/components/dashboard/AddEmployeeDrawer';

export function DashboardPage() {
  const [showAddEmployee, setShowAddEmployee] = useState(false);

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-start justify-between mb-7 animate-fade-up">
        <div>
          <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">
            Workforce Hub
          </h1>
          <p className="text-sm text-gray-500 leading-relaxed max-w-xl">
            Manage workforce operations and activity.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button
            icon={<UserPlus size={14} />}
            onClick={() => setShowAddEmployee(true)}
          >
            Add Employee
          </Button>
          <Button icon={<CheckCircle size={14} />}>Approve Leave</Button>
          <Button icon={<Megaphone size={14} />}>Create Announcement</Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="mb-6">
        <KpiCards />
      </div>

      {/* Pending Tasks */}
      <div className="mb-6 animate-fade-up" style={{ animationDelay: '100ms' }}>
        <PendingTasks />
      </div>

      {/* Analytics — Department Headcount + Attendance Trend */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="animate-fade-up" style={{ animationDelay: '150ms' }}>
          <DeptChart />
        </div>
        <div className="animate-fade-up" style={{ animationDelay: '200ms' }}>
          <AttendanceTrend />
        </div>
      </div>

      {/* Leave — Team Leave Calendar + On Leave Today */}
      <div className="grid grid-cols-2 gap-4">
        <div className="animate-fade-up" style={{ animationDelay: '250ms' }}>
          <TeamLeaveCalendar />
        </div>
        <div className="animate-fade-up" style={{ animationDelay: '300ms' }}>
          <OnLeaveToday />
        </div>
      </div>

      {/* Add Employee Drawer */}
      <AddEmployeeDrawer
        open={showAddEmployee}
        onClose={() => setShowAddEmployee(false)}
      />
    </div>
  );
}

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader } from '@/components/ui';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface Task {
  label: string;
  count: number;
  urgent: number;
  color: string;
}

const taskRoutes: Record<string, string> = {
  'Leave Approvals': '/time-off?tab=leave',
  'Attendance Corrections': '/time-off?tab=corrections',
  'Onboarding Tasks': '/onboarding',
  'Profile Updates': '/employees?filter=profile-updates',
};

export function PendingTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/pending-tasks`)
      .then((res) => res.json())
      .then((data) => setTasks(data.tasks || []))
      .catch(() => setTasks([]));
  }, []);

  const totalUrgent = tasks.reduce((sum, t) => sum + t.urgent, 0);

  return (
    <Card>
      <CardHeader
        title="Pending Tasks"
        badge={totalUrgent > 0 ? `${totalUrgent} urgent` : undefined}
        badgeColor="warning"
      />
      <div className="grid gap-4 px-5 pb-5 pt-4 sm:grid-cols-2 xl:grid-cols-4">
        {tasks.map((task) => {
          const route = taskRoutes[task.label];
          return (
          <button
            type="button"
            key={task.label}
            onClick={() => route && navigate(route)}
            disabled={!route}
            title={route ? `Open ${task.label}` : undefined}
            className={cn(
              'flex min-h-[112px] flex-col items-center justify-center rounded-xl border border-[var(--color-border)] bg-warm-bg px-3 py-4 text-center transition-all',
              route
                ? 'cursor-pointer hover:-translate-y-0.5 hover:border-[var(--color-nav-active-bar)]/30 hover:bg-accent-light/50 focus:outline-none focus:ring-2 focus:ring-[var(--color-nav-active-bar)]/25'
                : 'cursor-default'
            )}
          >
            <div
              className="mb-1 text-2xl font-semibold"
              style={{ color: task.color }}
            >
              {task.count}
            </div>
            <div className="text-[11.5px] text-gray-500 font-medium text-center leading-tight">
              {task.label}
            </div>
            {task.urgent > 0 && (
              <div className="mt-1.5 text-[10px] font-bold text-status-error bg-status-error/10 px-2 py-0.5 rounded-full">
                {task.urgent} urgent
              </div>
            )}
          </button>
          );
        })}
      </div>
    </Card>
  );
}

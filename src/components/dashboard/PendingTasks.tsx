import { useState, useEffect } from 'react';
import { Card, CardHeader } from '@/components/ui';

const API_BASE = 'http://localhost:8000/api/v1';

interface Task {
  label: string;
  count: number;
  urgent: number;
  color: string;
}

export function PendingTasks() {
  const [tasks, setTasks] = useState<Task[]>([]);

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
        {tasks.map((task) => (
          <div
            key={task.label}
            className="flex min-h-[112px] flex-col items-center justify-center rounded-xl border border-[#E5E7EB] bg-warm-bg px-3 py-4 transition-colors hover:border-olive/20"
          >
            <div
              className="text-2xl font-bold mb-1"
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
          </div>
        ))}
      </div>
    </Card>
  );
}

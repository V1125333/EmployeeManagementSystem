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
      <div className="px-5 pb-4 grid grid-cols-4 gap-3">
        {tasks.map((task) => (
          <div
            key={task.label}
            className="flex flex-col items-center py-4 px-3 rounded-xl bg-warm-bg border border-[#E5E7EB] hover:border-olive/20 transition-colors cursor-pointer"
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

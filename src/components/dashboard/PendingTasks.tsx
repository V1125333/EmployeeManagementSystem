import { Settings2 } from 'lucide-react';
import { Card, CardHeader, Badge, Button, StatusDot } from '@/components/ui';
import { pendingTasks } from '@/data/mockData';

export function PendingTasks() {
  return (
    <Card>
      <CardHeader
        title="Pending Tasks"
        icon={<Settings2 size={16} />}
        action={<Button variant="ghost" size="sm">Customize</Button>}
      />
      <div className="grid grid-cols-2 gap-2.5 p-5 sm:grid-cols-4">
        {pendingTasks.map((task) => (
          <div
            key={task.label}
            className="flex items-center justify-between px-4 py-3.5 rounded-btn bg-warm-bg border border-[#E5E7EB] hover:bg-hover-bg cursor-pointer transition-colors"
          >
            <div>
              <div className="text-[13px] font-medium text-[#2F3437] mb-1">
                {task.label}
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xl font-bold text-olive">{task.count}</span>
                {task.urgent > 0 && (
                  <Badge variant="error">{task.urgent} urgent</Badge>
                )}
              </div>
            </div>
            <StatusDot color={task.color} />
          </div>
        ))}
      </div>
    </Card>
  );
}

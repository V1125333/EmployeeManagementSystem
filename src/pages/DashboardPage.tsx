import { useState } from 'react';
import { AnnouncementsPanel } from '@/components/dashboard';
import { AddEmployeeDrawer } from '@/components/dashboard/AddEmployeeDrawer';
import { WorkforceOverview } from '@/components/dashboard/WorkforceOverview';

export function DashboardPage() {
  const [showAddEmployee, setShowAddEmployee] = useState(false);
  const [showAnnouncement, setShowAnnouncement] = useState(false);
  return (
    <div className="animate-fade-up">
      <WorkforceOverview
        onAddEmployee={() => setShowAddEmployee(true)}
        onCreateAnnouncement={() => setShowAnnouncement(true)}
      />
      <div className="hidden">
        <AnnouncementsPanel
          createOpen={showAnnouncement}
          onCreateOpen={() => setShowAnnouncement(true)}
          onCreateClose={() => setShowAnnouncement(false)}
        />
      </div>
      <AddEmployeeDrawer
        open={showAddEmployee}
        onClose={() => setShowAddEmployee(false)}
      />
    </div>
  );
}

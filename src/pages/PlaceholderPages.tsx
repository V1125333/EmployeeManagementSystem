import { Card } from '@/components/ui';

interface PlaceholderProps {
  title: string;
  description: string;
}

function PlaceholderPage({ title, description }: PlaceholderProps) {
  return (
    <div className="animate-fade-up">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">
          {title}
        </h1>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
      <Card className="flex items-center justify-center py-32">
        <div className="text-center">
          <div className="text-4xl mb-3">🚀</div>
          <div className="text-lg font-semibold text-[#2F3437] mb-1">
            Coming Soon
          </div>
          <div className="text-sm text-gray-500">
            This page is under development
          </div>
        </div>
      </Card>
    </div>
  );
}

export function EmployeesPage() {
  return (
    <PlaceholderPage
      title="Employees"
      description="View, manage, and search the complete employee directory."
    />
  );
}

export function OnboardingPage() {
  return (
    <PlaceholderPage
      title="Onboarding Center"
      description="Track and manage employee onboarding workflows."
    />
  );
}

export function ClientOnboardingPage() {
  return (
    <PlaceholderPage
      title="Client Onboarding"
      description="Manage client onboarding processes and milestones."
    />
  );
}

export function TimeOffPage() {
  return (
    <PlaceholderPage
      title="Time Off & Attendance"
      description="Track attendance, manage leave requests, and view attendance reports."
    />
  );
}

export function TeamAllocationPage() {
  return (
    <PlaceholderPage
      title="Team Allocation"
      description="View and manage team allocations across projects and departments."
    />
  );
}

export function AssetsPage() {
  return (
    <PlaceholderPage
      title="Assets & Access"
      description="Manage hardware assets, software licenses, and access permissions."
    />
  );
}

export function UserManagementPage() {
  return (
    <PlaceholderPage
      title="User Management"
      description="Manage portal users, roles, and access levels."
    />
  );
}

export function RolesPage() {
  return (
    <PlaceholderPage
      title="Roles & Permissions"
      description="Configure role-based access control and permission sets."
    />
  );
}

export function PoliciesPage() {
  return (
    <PlaceholderPage
      title="Policies"
      description="Create and manage organizational policies and guidelines."
    />
  );
}

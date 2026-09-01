import { describe, expect, it } from 'vitest';

import addEmployeeSource from './components/dashboard/AddEmployeeDrawer.tsx?raw';
import announcementsSource from './components/dashboard/Announcements.tsx?raw';
import topNavSource from './components/layout/TopNav.tsx?raw';
import organizationSource from './components/organization/OrganizationChart.tsx?raw';
import assignEmployeeSource from './components/projects/AssignEmployeeModal.tsx?raw';
import portalSource from './pages/EmployeePortalPages.tsx?raw';
import employeesSource from './pages/EmployeesPage.tsx?raw';
import profileSource from './pages/ProfilePage.tsx?raw';
import projectDetailSource from './pages/ProjectDetailPage.tsx?raw';
import projectsSource from './pages/ProjectsPage.tsx?raw';
import benchSource from './pages/BenchPage.tsx?raw';
import requestsSource from './pages/RequestsPage.tsx?raw';
import settingsSource from './pages/SettingsPage.tsx?raw';
import staffingDetailSource from './pages/StaffingRequestDetailPage.tsx?raw';
import staffingSource from './pages/StaffingRequestsPage.tsx?raw';
import talentSource from './pages/TalentProfilesPage.tsx?raw';
import forecastSource from './pages/WorkforceForecastPage.tsx?raw';


const fullyMigratedSources = [
  addEmployeeSource,
  announcementsSource,
  topNavSource,
  organizationSource,
  assignEmployeeSource,
  employeesSource,
  profileSource,
  projectsSource,
  benchSource,
  requestsSource,
  settingsSource,
  staffingDetailSource,
  staffingSource,
  talentSource,
  forecastSource,
  portalSource,
];


function callWindows(source: string, route: RegExp): string[] {
  const lines = source.split('\n');
  return lines.flatMap((line, index) => line.includes('API_BASE') && route.test(line)
    ? [lines.slice(Math.max(0, index - 1), index + 7).join('\n')]
    : []);
}


describe('Foundation Phase 0 Task 6 bearer transport', () => {
  it('removes compatibility identity headers from fully migrated callers', () => {
    for (const source of fullyMigratedSources) {
      expect(source.toLowerCase()).not.toMatch(/x-user-(id|email|name)/);
    }
  });

  it('uses authenticatedFetch for employee, project, allocation, forecast, staffing, request, inbox, and announcement calls', () => {
    const sources = [...fullyMigratedSources, projectDetailSource, portalSource];
    const migratedRoute = /\/(employees|projects|allocations|forecasting|staffing-requests|requests|announcements|inbox\/leave-requests|inbox\/attendance-corrections|leaves\/approvals|timesheets\/approvals|timesheets\/.*\/allocation-compliance)/;
    const calls = sources.flatMap((source) => callWindows(source, migratedRoute));
    expect(calls.length).toBeGreaterThan(25);
    for (const call of calls) {
      expect(call).toContain('authenticatedFetch');
      expect(call).not.toMatch(/(^|[^A-Za-z])fetch\s*\(/);
    }
  });

  it('keeps Task 6 project calls free of identity headers after the Task 7 audit migration', () => {
    for (const call of callWindows(projectDetailSource, /\/(projects|allocations)/)) {
      expect(call.toLowerCase()).not.toMatch(/x-user-(id|email|name)/);
      expect(call).not.toContain('legacyAuditHeaders');
    }
    expect(projectDetailSource).not.toContain('legacyAuditHeaders');
    expect(projectDetailSource).toContain('/audit-logs');
  });

  it('does not send legacy approval headers on migrated request workflow calls', () => {
    for (const call of callWindows(portalSource, /\/requests/)) {
      expect(call.toLowerCase()).not.toMatch(/x-user-(id|email|name)/);
    }
    expect(portalSource).toContain('authenticatedFetch(`${API_BASE}/requests/queue`)');
    expect(portalSource).toContain('headers,');
  });

  it('preserves target IDs, authenticated downloads, and browser-managed multipart uploads', () => {
    expect(projectDetailSource).toContain('/projects/${projectId}/documents/${doc.id}/download');
    expect(requestsSource).toContain('/requests/${request.id}/attachments/${attachmentId}/download');
    expect(requestsSource).toContain('body: formData');
    expect(profileSource).toContain('body: imageData');
    expect(employeesSource).toContain('body: formData');
    for (const source of [projectDetailSource, requestsSource, profileSource, employeesSource]) {
      expect(source).not.toContain("'Content-Type': 'multipart/form-data'");
    }
  });
});

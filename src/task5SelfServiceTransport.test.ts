import { describe, expect, it } from 'vitest';

import topNavSource from './components/layout/TopNav.tsx?raw';
import themeSource from './hooks/useTheme.tsx?raw';
import askOrbitSource from './pages/AskOrbitAIPage.tsx?raw';
import documentsSource from './pages/EmployeeDocumentsPage.tsx?raw';
import portalSource from './pages/EmployeePortalPages.tsx?raw';
import settingsSource from './pages/SettingsPage.tsx?raw';


const migratedPath = /(attendance\/me|leaves\/me|timesheets\/me|holidays|documents|settings\/(?:me|preferences|activity|profile)|dashboard\/employee-context|support-tickets|inbox|notifications)/;


function migratedCallWindows(source: string): string[] {
  const lines = source.split('\n');
  return lines.flatMap((line, index) => line.includes('API_BASE') && migratedPath.test(line) ? [lines.slice(index, index + 6).join('\n')] : []);
}


describe('Foundation Phase 0 Task 5 self-service transport', () => {
  const sources = [topNavSource, themeSource, askOrbitSource, documentsSource, portalSource, settingsSource];

  it('uses the shared authenticated transport for every migrated caller', () => {
    for (const source of sources) {
      for (const call of migratedCallWindows(source)) {
        if (!call.includes('API_BASE')) continue;
        expect(call).toContain('authenticatedFetch');
        expect(call).not.toMatch(/(^|[^A-Za-z])fetch\s*\(/);
      }
    }
  });

  it('does not attach caller-controlled identity headers to migrated calls', () => {
    for (const source of sources) {
      for (const call of migratedCallWindows(source)) {
        expect(call.toLowerCase()).not.toContain('x-user-id');
        expect(call.toLowerCase()).not.toContain('x-user-email');
        expect(call.toLowerCase()).not.toContain('x-user-name');
      }
    }
  });

  it('keeps document FormData browser-managed and protected downloads authenticated', () => {
    expect(documentsSource).toContain('authenticatedFetch(target, { method: updateDocument ? \'PUT\' : \'POST\', body: formData })');
    expect(documentsSource).toContain('authenticatedFetch(`${API_BASE}/documents/${document.id}/download`)');
    expect(documentsSource).not.toContain("'Content-Type': 'multipart/form-data'");
  });

  it('keeps settings self-service calls free of compatibility identity headers', () => {
    expect(settingsSource).toContain('authenticatedFetch(`${API_BASE}/employees/${profile.id}`');
    expect(settingsSource.toLowerCase()).not.toContain('x-user-id');
    expect(settingsSource.toLowerCase()).not.toContain('x-user-email');
    expect(settingsSource.toLowerCase()).not.toContain('x-user-name');
  });

  it('keeps HR-managed identity fields read-only for employees and out of their update payload', () => {
    expect(settingsSource).toContain('readOnly={!canEditManagedIdentity}');
    expect(settingsSource).toContain("Managed by HR/Admin.");
    expect(settingsSource).toContain('...(canEditManagedIdentity ? {');
    expect(settingsSource).toContain("data?.detail || data?.message || 'Could not save profile.'");
  });

  it('uses the shared header search instead of duplicating search on the employee dashboard', () => {
    expect(portalSource).not.toContain('Search people, projects, docs...');
    expect(topNavSource).toContain('placeholder="Search..."');
  });
});

import { describe, expect, it } from 'vitest';
import appSource from './App.tsx?raw';
import layoutSource from './layouts/AppLayout.tsx?raw';
import employeePortalSource from './pages/EmployeePortalPages.tsx?raw';

describe('Version 1 general employee management boundary', () => {
  it('keeps legacy AI pages disabled while allowing the authenticated floating assistant', () => {
    expect(appSource).not.toContain("import { AskOrbitAIPage }");
    expect(appSource).not.toContain("import { AIPlatformPreviewPage }");
    expect(layoutSource).not.toContain('OrbitAIBriefing');
    expect(layoutSource).toContain('OrbitFloatingAssistant');
    expect(layoutSource).toContain('OrbitFloatingAssistant />');
  });

  it('redirects old AI bookmarks into the role-based EMS home', () => {
    expect(appSource).toContain('<Route path="/ask-orbit-ai" element={<Navigate to="/" replace />} />');
    expect(appSource).toContain('<Route path="/ai-platform-preview" element={<Navigate to="/" replace />} />');
  });

  it('uses deterministic EMS dashboard navigation without AI branding', () => {
    expect(employeePortalSource).not.toContain("navigate('/ask-orbit-ai')");
    expect(employeePortalSource).not.toContain('Orbit AI · Your day');
    expect(employeePortalSource).toContain("navigate('/employee/timesheets')");
    expect(employeePortalSource).toContain("navigate('/employee/apply-leave')");
  });
});

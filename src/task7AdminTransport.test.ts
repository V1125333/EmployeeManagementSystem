import { describe, expect, it } from 'vitest';

import auditTimelineSource from './components/audit/AuditTimeline.tsx?raw';
import auditTrailSource from './pages/AuditTrailPage.tsx?raw';
import certificateGeneratorSource from './pages/CertificateGeneratorPage.tsx?raw';
import certificateVerificationSource from './pages/CertificateVerificationPage.tsx?raw';
import hrDocumentsSource from './pages/HRDocumentsPage.tsx?raw';
import placeholdersSource from './pages/PlaceholderPages.tsx?raw';
import projectDetailSource from './pages/ProjectDetailPage.tsx?raw';
import securityCenterSource from './pages/SecurityCenterPage.tsx?raw';


const managementSources = [
  auditTimelineSource,
  auditTrailSource,
  certificateGeneratorSource,
  hrDocumentsSource,
  placeholdersSource,
  projectDetailSource,
  securityCenterSource,
];


function callWindows(source: string, route: RegExp): string[] {
  const lines = source.split('\n');
  return lines.flatMap((line, index) => line.includes('API_BASE') && route.test(line)
    ? [lines.slice(Math.max(0, index - 1), index + 7).join('\n')]
    : []);
}


describe('Foundation Phase 0 Task 7 administrative transport', () => {
  it('removes compatibility identity headers from all migrated administrative callers', () => {
    for (const source of managementSources) {
      expect(source.toLowerCase()).not.toMatch(/x-user-(id|email|name|role)/);
    }
  });

  it('uses authenticated transport for every Task 7 management domain', () => {
    const route = /\/(admin\/security|admin\/time-off|audit-logs|certificates(?!\/verify)|hr-documents|admin\/client-onboarding)/;
    const calls = managementSources.flatMap((source) => callWindows(source, route));
    expect(calls.length).toBeGreaterThan(20);
    for (const call of calls) {
      expect(call).toContain('authenticatedFetch');
      expect(call).not.toMatch(/(^|[^A-Za-z])fetch\s*\(/);
      expect(call).not.toContain('publicFetch');
    }
  });

  it('keeps public certificate verification isolated from Orbit bearer transport', () => {
    expect(certificateVerificationSource).toContain('publicFetch(`${API_BASE}/certificates/verify/');
    expect(certificateVerificationSource).not.toContain('authenticatedFetch');
    expect(certificateVerificationSource.toLowerCase()).not.toMatch(/x-user-(id|email|name|role)/);
  });

  it('keeps management downloads authenticated and request bodies intact', () => {
    expect(certificateGeneratorSource).toContain('/certificates/${encodeURIComponent(record.certificate_code)}/download');
    expect(certificateGeneratorSource).toContain('authenticatedFetch');
    expect(hrDocumentsSource).toContain("method: 'POST'");
    expect(hrDocumentsSource).toContain("'Content-Type': 'application/json'");
    expect(placeholdersSource).toContain('JSON.stringify(cleaned)');
    expect(placeholdersSource).toContain('JSON.stringify({ decision: pending.decision, reason: reason.trim() || null })');
  });

  it('retains target resource identifiers without treating them as authentication', () => {
    expect(securityCenterSource).toContain('/admin/security/locked-accounts/${row.id}/unlock');
    expect(projectDetailSource).toContain('/audit-logs/entity/project/${projectId}');
    expect(placeholdersSource).toContain('/admin/client-onboarding/${detail.client.id}');
    expect(placeholdersSource).toContain('/admin/time-off/leave-balances/${editing.id}');
  });
});

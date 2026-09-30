import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/hooks/useAuth';
import { ThemeProvider } from '@/hooks/useTheme';
import { ToastProvider } from '@/components/ui/Toast';
import { PermissionRoute, ProtectedRoute, RoleHomeRedirect } from '@/components/layout/ProtectedRoute';
import { AppLayout } from '@/layouts/AppLayout';
import { LoginPage } from '@/pages/LoginPage';
import { BrandPreviewPage } from '@/pages/BrandPreviewPage';
import { ForceChangePasswordPage } from '@/pages/ForceChangePasswordPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { EmployeesPage } from '@/pages/EmployeesPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { OrganizationPage } from '@/pages/OrganizationPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { CertificateGeneratorPage } from '@/pages/CertificateGeneratorPage';
import { CertificateVerificationPage } from '@/pages/CertificateVerificationPage';
import { AuditTrailPage } from '@/pages/AuditTrailPage';
import { SecurityCenterPage } from '@/pages/SecurityCenterPage';
import { HRDocumentsPage } from '@/pages/HRDocumentsPage';
import { BenchPage } from '@/pages/BenchPage';
import { TalentProfilesPage } from '@/pages/TalentProfilesPage';
import { WorkforceForecastPage } from '@/pages/WorkforceForecastPage';
import { StaffingRequestDetailPage } from '@/pages/StaffingRequestDetailPage';
import { StaffingRequestsPage } from '@/pages/StaffingRequestsPage';
import { RequestsPage } from '@/pages/RequestsPage';
import { ProjectDetailPage } from '@/pages/ProjectDetailPage';
import { ProjectsPage } from '@/pages/ProjectsPage';
import { AuthCallbackPage } from '@/pages/AuthCallbackPage';
import { EmployeeDocumentsPage } from '@/pages/EmployeeDocumentsPage';
import {
  OnboardingPage,
  ClientOnboardingPage,
  TimeOffPage,
  TeamAllocationPage,
  AssetsPage,
  UserManagementPage,
  RolesPage,
  PoliciesPage,
} from '@/pages/PlaceholderPages';
import {
  ApplyLeavePage,
  CheckInOutPage,
  CompanyHandbookPage,
  EmployeeDashboardPage,
  EmployeeNotificationsPage,
  HolidaysPage,
  LeaveApprovalsPage,
  TimesheetsPage,
} from '@/pages/EmployeePortalPages';
import { MyCareerProfilePage } from '@/pages/MyCareerProfilePage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ThemeProvider>
        <ToastProvider>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/brand-preview" element={<BrandPreviewPage />} />
            <Route path="/force-change-password" element={<ForceChangePasswordPage />} />
            <Route path="/verify/:certificateCode" element={<CertificateVerificationPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />

            {/* Protected routes */}
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<RoleHomeRedirect />} />
                <Route element={<PermissionRoute permission="portal.access" />}>
                  <Route path="/profile" element={<ProfilePage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/notifications" element={<EmployeeNotificationsPage />} />
                  <Route path="/employee" element={<EmployeeDashboardPage />} />
                  <Route path="/employee/apply-leave" element={<ApplyLeavePage />} />
                  <Route path="/employee/leave-balance" element={<Navigate to="/employee/apply-leave" replace />} />
                  <Route path="/employee/check-in" element={<CheckInOutPage />} />
                  <Route path="/employee/attendance" element={<Navigate to="/employee/check-in" replace />} />
                  <Route path="/employee/requests" element={<RequestsPage />} />
                  <Route path="/employee/documents" element={<EmployeeDocumentsPage />} />
                  <Route path="/employee/company-handbook" element={<CompanyHandbookPage />} />
                  <Route path="/employee/holidays" element={<HolidaysPage />} />
                  <Route path="/employee/career-profile" element={<MyCareerProfilePage />} />
                  <Route path="/employee/notifications" element={<Navigate to="/notifications" replace />} />
                </Route>
                <Route element={<PermissionRoute permission="employee.read" scopes={['direct_reports', 'organization']} />}>
                  <Route path="/organization" element={<OrganizationPage />} />
                </Route>
                <Route element={<PermissionRoute permission="timesheet.manage" />}>
                  <Route path="/timesheets" element={<TimesheetsPage />} />
                  <Route path="/employee/timesheets" element={<TimesheetsPage />} />
                </Route>
                <Route path="/ask-orbit-ai" element={<Navigate to="/" replace />} />
                <Route path="/ai-platform-preview" element={<Navigate to="/" replace />} />
                <Route element={<PermissionRoute permission="allocation.read" scopes={['direct_reports', 'organization']} />}>
                  <Route path="/bench" element={<BenchPage />} />
                </Route>
                <Route element={<PermissionRoute permission="project.read" />}>
                  <Route path="/projects" element={<ProjectsPage />} />
                  <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
                </Route>
                <Route element={<PermissionRoute permission="staffing.request" />}>
                  <Route path="/staffing-requests" element={<StaffingRequestsPage />} />
                  <Route path="/staffing-requests/:requestId" element={<StaffingRequestDetailPage />} />
                </Route>
                <Route element={<PermissionRoute permission="forecast.read" />}>
                  <Route path="/forecasting" element={<WorkforceForecastPage />} />
                </Route>
                <Route element={<PermissionRoute permission="talent.read" />}>
                  <Route path="/talent-profiles" element={<TalentProfilesPage />} />
                </Route>
                <Route element={<PermissionRoute permission="leave.approve" />}>
                  <Route path="/employee/approvals" element={<LeaveApprovalsPage />} />
                </Route>
                <Route element={<PermissionRoute permission="employee.read" scopes={['organization']} />}>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/employees" element={<EmployeesPage />} />
                </Route>
                <Route element={<PermissionRoute permission="onboarding.manage" />}>
                  <Route path="/onboarding" element={<OnboardingPage />} />
                </Route>
                <Route element={<PermissionRoute permission="client.manage" />}>
                  <Route path="/client-onboarding" element={<ClientOnboardingPage />} />
                </Route>
                <Route element={<PermissionRoute permission="leave.manage" scopes={['organization']} />}>
                  <Route path="/time-off" element={<TimeOffPage />} />
                </Route>
                <Route element={<PermissionRoute permission="allocation.manage" />}>
                  <Route path="/team-allocation" element={<TeamAllocationPage />} />
                </Route>
                <Route element={<PermissionRoute permission="asset.manage" />}>
                  <Route path="/assets" element={<AssetsPage />} />
                </Route>
                <Route element={<PermissionRoute permission="security.account.manage" />}>
                  <Route path="/admin/users" element={<UserManagementPage />} />
                  <Route path="/admin/security" element={<SecurityCenterPage />} />
                </Route>
                <Route element={<PermissionRoute permission="role.manage" />}>
                  <Route path="/admin/roles" element={<RolesPage />} />
                </Route>
                <Route element={<PermissionRoute permission="hr_policy.manage" />}>
                  <Route path="/admin/policies" element={<PoliciesPage />} />
                </Route>
                <Route element={<PermissionRoute permission="certificate.manage" />}>
                  <Route path="/admin/certificates" element={<CertificateGeneratorPage />} />
                </Route>
                <Route element={<PermissionRoute permission="document.manage_hr" />}>
                  <Route path="/admin/hr-documents" element={<HRDocumentsPage />} />
                </Route>
                <Route element={<PermissionRoute anyOf={['audit.read_hr', 'audit.read_security']} />}>
                  <Route path="/admin/audit-trail" element={<AuditTrailPage />} />
                </Route>
              </Route>
            </Route>

            {/* Catch-all redirect to login */}
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </ToastProvider>
        </ThemeProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

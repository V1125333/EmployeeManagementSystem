import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/hooks/useAuth';
import { ThemeProvider } from '@/hooks/useTheme';
import { ToastProvider } from '@/components/ui/Toast';
import { AdminRoute, EmployeeRoute, ProtectedRoute, RoleHomeRedirect } from '@/components/layout/ProtectedRoute';
import { AppLayout } from '@/layouts/AppLayout';
import { LoginPage } from '@/pages/LoginPage';
import { ForceChangePasswordPage } from '@/pages/ForceChangePasswordPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { EmployeesPage } from '@/pages/EmployeesPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { SettingsPage } from '@/pages/SettingsPage';
import { CertificateGeneratorPage } from '@/pages/CertificateGeneratorPage';
import { CertificateVerificationPage } from '@/pages/CertificateVerificationPage';
import { AuditTrailPage } from '@/pages/AuditTrailPage';
import { SecurityCenterPage } from '@/pages/SecurityCenterPage';
import { HRDocumentsPage } from '@/pages/HRDocumentsPage';
import { BenchPage } from '@/pages/BenchPage';
import { WorkforceForecastPage } from '@/pages/WorkforceForecastPage';
import { StaffingRequestDetailPage } from '@/pages/StaffingRequestDetailPage';
import { StaffingRequestsPage } from '@/pages/StaffingRequestsPage';
import { RequestsPage } from '@/pages/RequestsPage';
import { ProjectDetailPage } from '@/pages/ProjectDetailPage';
import { ProjectsPage } from '@/pages/ProjectsPage';
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
  AttendanceHistoryPage,
  CheckInOutPage,
  CompanyHandbookPage,
  EmployeeDashboardPage,
  EmployeeDocumentsPage,
  EmployeeNotificationsPage,
  HolidaysPage,
  LeaveApprovalsPage,
  TimesheetsPage,
} from '@/pages/EmployeePortalPages';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ThemeProvider>
        <ToastProvider>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/force-change-password" element={<ForceChangePasswordPage />} />
            <Route path="/verify/:certificateCode" element={<CertificateVerificationPage />} />

            {/* Protected routes */}
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<RoleHomeRedirect />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/notifications" element={<EmployeeNotificationsPage />} />
                <Route path="/bench" element={<BenchPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
                <Route path="/staffing-requests" element={<StaffingRequestsPage />} />
                <Route path="/staffing-requests/:requestId" element={<StaffingRequestDetailPage />} />
                <Route path="/forecasting" element={<WorkforceForecastPage />} />

                <Route element={<EmployeeRoute />}>
                  <Route path="/employee" element={<EmployeeDashboardPage />} />
                  <Route path="/employee/apply-leave" element={<ApplyLeavePage />} />
                  <Route path="/employee/leave-balance" element={<Navigate to="/employee/apply-leave" replace />} />
                  <Route path="/employee/approvals" element={<LeaveApprovalsPage />} />
                  <Route path="/employee/timesheets" element={<TimesheetsPage />} />
                  <Route path="/employee/check-in" element={<CheckInOutPage />} />
                  <Route path="/employee/attendance" element={<AttendanceHistoryPage />} />
                  <Route path="/employee/requests" element={<RequestsPage />} />
                  <Route path="/employee/documents" element={<EmployeeDocumentsPage />} />
                  <Route path="/employee/company-handbook" element={<CompanyHandbookPage />} />
                  <Route path="/employee/holidays" element={<HolidaysPage />} />
                  <Route path="/employee/notifications" element={<Navigate to="/notifications" replace />} />
                </Route>

                <Route element={<AdminRoute />}>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/employees" element={<EmployeesPage />} />
                  <Route path="/onboarding" element={<OnboardingPage />} />
                  <Route path="/client-onboarding" element={<ClientOnboardingPage />} />
                  <Route path="/time-off" element={<TimeOffPage />} />
                  <Route path="/team-allocation" element={<TeamAllocationPage />} />
                  <Route path="/assets" element={<AssetsPage />} />
                  <Route path="/admin/users" element={<UserManagementPage />} />
                  <Route path="/admin/roles" element={<RolesPage />} />
                  <Route path="/admin/policies" element={<PoliciesPage />} />
                  <Route path="/admin/certificates" element={<CertificateGeneratorPage />} />
                  <Route path="/admin/hr-documents" element={<HRDocumentsPage />} />
                  <Route path="/admin/audit-trail" element={<AuditTrailPage />} />
                  <Route path="/admin/security" element={<SecurityCenterPage />} />
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

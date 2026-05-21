import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/hooks/useAuth';
import { ToastProvider } from '@/components/ui/Toast';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { AppLayout } from '@/layouts/AppLayout';
import { LoginPage } from '@/pages/LoginPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { EmployeesPage } from '@/pages/EmployeesPage';
import { ProfilePage } from '@/pages/ProfilePage';
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

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected routes */}
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/employees" element={<EmployeesPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/onboarding" element={<OnboardingPage />} />
                <Route path="/client-onboarding" element={<ClientOnboardingPage />} />
                <Route path="/time-off" element={<TimeOffPage />} />
                <Route path="/team-allocation" element={<TeamAllocationPage />} />
                <Route path="/assets" element={<AssetsPage />} />
                <Route path="/admin/users" element={<UserManagementPage />} />
                <Route path="/admin/roles" element={<RolesPage />} />
                <Route path="/admin/policies" element={<PoliciesPage />} />
              </Route>
            </Route>

            {/* Catch-all redirect to login */}
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

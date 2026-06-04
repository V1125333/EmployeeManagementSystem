import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

function isAdminRole(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalized);
}

export function ProtectedRoute() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

export function AdminRoute() {
  const { user } = useAuth();

  if (!isAdminRole(user?.role)) {
    return <Navigate to="/employee" replace />;
  }

  return <Outlet />;
}

export function EmployeeRoute() {
  const { user } = useAuth();

  if (isAdminRole(user?.role)) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

export function RoleHomeRedirect() {
  const { user } = useAuth();

  if (isAdminRole(user?.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Navigate to="/employee" replace />;
}

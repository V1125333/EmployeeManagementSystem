import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { canAccess, type PermissionScope } from '@/auth/rbac';

export function ProtectedRoute() {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (user?.forcePasswordChange) {
    return <Navigate to="/force-change-password" replace />;
  }

  return <Outlet />;
}

export function PermissionRoute({
  permission,
  anyOf,
  scopes,
}: {
  permission?: string;
  anyOf?: readonly string[];
  scopes?: readonly PermissionScope[];
}) {
  const { user } = useAuth();
  const allowed = permission
    ? canAccess(user, permission, scopes)
    : Boolean(anyOf?.some((item) => canAccess(user, item, scopes)));
  if (!allowed) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

export function RoleHomeRedirect() {
  const { user } = useAuth();

  if (canAccess(user, 'employee.read', ['organization'])) return <Navigate to="/dashboard" replace />;
  if (canAccess(user, 'security.account.manage')) return <Navigate to="/admin/security" replace />;
  if (canAccess(user, 'staffing.manage')) return <Navigate to="/bench" replace />;
  return <Navigate to="/employee" replace />;
}

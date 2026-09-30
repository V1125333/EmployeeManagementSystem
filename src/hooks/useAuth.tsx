import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ORBIT_PASSWORD_CHANGE_REQUIRED_EVENT,
  ORBIT_SESSION_EXPIRED_EVENT,
  authenticatedFetch,
  clearOrbitSession,
  publicFetch,
  readOrbitSession,
  writeOrbitSession,
  type OrbitSession,
} from '@/services/apiClient';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export interface AuthUser {
  id?: string;
  name: string;
  role: string;
  email: string;
  initials: string;
  profileImageUrl?: string | null;
  forcePasswordChange?: boolean;
  permissions?: string[];
  scopes?: Record<string, string[]>;
}

interface AuthContextType {
  user: AuthUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  loginWithApi: (email: string, password: string, totpCode: string) => Promise<{ success: boolean; message: string }>;
  logout: () => void;
  setUserFromApi: (employee: any, token?: string) => void;
  updateUser: (updates: Partial<AuthUser>) => void;
  refreshCurrentUser: () => Promise<AuthUser | null>;
}

const AuthContext = createContext<AuthContextType | null>(null);

function makeInitials(name: string): string {
  return name.split(' ').map((word) => word[0]).join('').toUpperCase().slice(0, 2);
}

interface CurrentUserProfile {
  id: string;
  first_name: string;
  last_name: string;
  work_email: string;
  role: string;
  profile_image_url?: string | null;
  force_password_change?: boolean;
  permissions?: string[];
  scopes?: Record<string, string[]>;
}

function currentProfileToAuthUser(profile: CurrentUserProfile): AuthUser {
  const name = `${profile.first_name} ${profile.last_name}`.trim();
  return {
    id: profile.id,
    name,
    email: profile.work_email,
    role: profile.role || 'employee',
    initials: makeInitials(name),
    profileImageUrl: profile.profile_image_url || null,
    forcePasswordChange: Boolean(profile.force_password_change),
    permissions: Array.isArray(profile.permissions) ? profile.permissions : [],
    scopes: profile.scopes || {},
  };
}

function readInitialSession(): OrbitSession<AuthUser> | null {
  const restored = readOrbitSession<AuthUser>();
  if (!restored) return null;
  const { user } = restored;
  if (typeof user.name !== 'string' || !user.name.trim()
    || typeof user.email !== 'string' || !user.email.trim()
    || typeof user.role !== 'string' || !user.role.trim()) {
    clearOrbitSession();
    return null;
  }
  return restored;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [session, setSession] = useState<OrbitSession<AuthUser> | null>(readInitialSession);
  const user = session?.user || null;
  const accessToken = session?.token || null;

  useEffect(() => {
    const isPublicPath = () => ['/login', '/auth/callback', '/brand-preview'].includes(location.pathname)
      || location.pathname.startsWith('/verify/');
    const expireSession = () => {
      clearOrbitSession();
      setSession(null);
      if (!isPublicPath()) navigate('/login', { replace: true });
    };
    const requirePasswordChange = () => {
      if (location.pathname !== '/force-change-password') navigate('/force-change-password', { replace: true });
    };
    window.addEventListener(ORBIT_SESSION_EXPIRED_EVENT, expireSession);
    window.addEventListener(ORBIT_PASSWORD_CHANGE_REQUIRED_EVENT, requirePasswordChange);
    return () => {
      window.removeEventListener(ORBIT_SESSION_EXPIRED_EVENT, expireSession);
      window.removeEventListener(ORBIT_PASSWORD_CHANGE_REQUIRED_EVENT, requirePasswordChange);
    };
  }, [location.pathname, navigate]);

  const loginWithApi = async (email: string, password: string, totpCode: string) => {
    const normalizedEmail = email.trim().toLowerCase();
    try {
      const passwordResponse = await publicFetch(`${API_BASE}/auth/login/verify-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail, password }),
      });
      let result = await passwordResponse.json();
      if (passwordResponse.ok && result.success && result.login_challenge_token) {
        const mfaResponse = await publicFetch(`${API_BASE}/auth/login/verify-mfa`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ login_challenge_token: result.login_challenge_token, totp_code: totpCode }),
        });
        result = await mfaResponse.json();
      }
      if (result.success && result.employee) {
        const authUser: AuthUser = {
          id: result.employee.id,
          name: result.employee.name,
          email: result.employee.email,
          role: result.employee.role || 'employee',
          initials: makeInitials(result.employee.name),
          profileImageUrl: result.employee.profile_image_url || null,
          forcePasswordChange: Boolean(result.force_password_change),
          permissions: result.employee.permissions || [],
          scopes: result.employee.scopes || {},
        };
        const token = typeof result.token === 'string' ? result.token.trim() : '';
        if (!token) return { success: false, message: 'Login did not return a valid session.' };
        const nextSession = { user: authUser, token };
        writeOrbitSession(nextSession);
        setSession(nextSession);
        return { success: true, message: result.message };
      }
      return { success: false, message: result.message || 'Login failed' };
    } catch {
      return { success: false, message: 'Cannot connect to server' };
    }
  };

  const setUserFromApi = (employee: any, token?: string) => {
    const name = employee.name || `${employee.first_name} ${employee.last_name}`;
    const authUser: AuthUser = {
      id: employee.id,
      name,
      email: employee.email || employee.work_email,
      role: employee.role || 'employee',
      initials: makeInitials(name),
      profileImageUrl: employee.profile_image_url || null,
      forcePasswordChange: Boolean(employee.force_password_change),
      permissions: employee.permissions || [],
      scopes: employee.scopes || {},
    };
    const orbitAccessToken = token?.trim() || '';
    if (!orbitAccessToken) {
      clearOrbitSession();
      setSession(null);
      return;
    }
    const nextSession = { user: authUser, token: orbitAccessToken };
    writeOrbitSession(nextSession);
    setSession(nextSession);
  };

  const logout = () => {
    setSession(null);
    clearOrbitSession();
  };

  const updateUser = (updates: Partial<AuthUser>) => {
    setSession((current) => {
      if (!current) return current;
      const next = { ...current, user: { ...current.user, ...updates } };
      writeOrbitSession(next);
      return next;
    });
  };

  const refreshCurrentUser = useCallback(async (): Promise<AuthUser | null> => {
    if (!accessToken) return null;
    const response = await authenticatedFetch(`${API_BASE}/auth/me`, {}, accessToken);
    if (!response.ok) return null;
    const data = await response.json();
    if (!data?.success || !data.employee) return null;
    const authUser = currentProfileToAuthUser(data.employee);
    const nextSession = { user: authUser, token: accessToken };
    setSession(nextSession);
    writeOrbitSession(nextSession);
    return authUser;
  }, [accessToken]);

  useEffect(() => {
    if (accessToken && user && !user.forcePasswordChange) {
      void refreshCurrentUser().catch(() => undefined);
    }
  }, [accessToken, refreshCurrentUser]);

  return (
    <AuthContext.Provider value={{
      user,
      accessToken,
      isAuthenticated: Boolean(user && accessToken),
      loginWithApi,
      logout,
      setUserFromApi,
      updateUser,
      refreshCurrentUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}

import { createContext, useContext, useState, type ReactNode } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const STORAGE_KEY = 'reknew_orbit_auth';

// ─── Types ───
export interface AuthUser {
  id?: string;
  name: string;
  role: string;
  email: string;
  initials: string;
  profileImageUrl?: string | null;
  forcePasswordChange?: boolean;
}

interface AuthContextType {
  user: AuthUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  loginWithApi: (email: string, password: string, totpCode: string) => Promise<{ success: boolean; message: string }>;
  logout: () => void;
  setUserFromApi: (employee: any, token?: string) => void;
  updateUser: (updates: Partial<AuthUser>) => void;
}

// ─── Context ───
const AuthContext = createContext<AuthContextType | null>(null);

function makeInitials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function readStoredUser(): AuthUser | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    const parsed = stored ? JSON.parse(stored) : null;
    return parsed?.user || null;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function readStoredToken(): string | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    const parsed = stored ? JSON.parse(stored) : null;
    return typeof parsed?.token === 'string' ? parsed.token : null;
  } catch {
    return null;
  }
}

// ─── Provider ───
export function AuthProvider({ children }: { children: ReactNode }) {
  // Hydrate before the first protected-route render so bookmarks and refreshes keep their route.
  const [user, setUser] = useState<AuthUser | null>(readStoredUser);
  const [accessToken, setAccessToken] = useState<string | null>(readStoredToken);

  // Login via backend API (email + password + TOTP)
  const loginWithApi = async (email: string, password: string, totpCode: string) => {
    const normalizedEmail = email.trim().toLowerCase();
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail, password, totp_code: totpCode }),
      });

      const result = await response.json();

      if (result.success && result.employee) {
        const authUser: AuthUser = {
          id: result.employee.id,
          name: result.employee.name,
          email: result.employee.email,
          role: result.employee.role || 'Employee',
          initials: makeInitials(result.employee.name),
          profileImageUrl: result.employee.profile_image_url || null,
          forcePasswordChange: Boolean(result.force_password_change),
        };
        setUser(authUser);
        setAccessToken(result.token || null);
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: authUser, token: result.token }));
        return { success: true, message: result.message };
      }

      return { success: false, message: result.message || 'Login failed' };
    } catch {
      return { success: false, message: 'Cannot connect to server' };
    }
  };

  // Set user from API response (used after first-time setup completes)
  const setUserFromApi = (employee: any, token?: string) => {
    const authUser: AuthUser = {
      id: employee.id,
      name: employee.name || `${employee.first_name} ${employee.last_name}`,
      email: employee.email || employee.work_email,
      role: employee.role || 'Employee',
      initials: makeInitials(employee.name || `${employee.first_name} ${employee.last_name}`),
      profileImageUrl: employee.profile_image_url || null,
      forcePasswordChange: Boolean(employee.force_password_change),
    };
    setUser(authUser);
    setAccessToken(token || null);
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: authUser, token: token || null }));
  };

  const logout = () => {
    setUser(null);
    setAccessToken(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  const updateUser = (updates: Partial<AuthUser>) => {
    setUser((current) => {
      if (!current) return current;
      const next = { ...current, ...updates };
      const stored = localStorage.getItem(STORAGE_KEY);
      const parsed = stored ? JSON.parse(stored) : {};
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...parsed, user: next }));
      return next;
    });
  };

  return (
    <AuthContext.Provider
      value={{ user, accessToken, isAuthenticated: user !== null, loginWithApi, logout, setUserFromApi, updateUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ───
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}

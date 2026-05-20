import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

const API_BASE = 'http://localhost:8000/api/v1';
const STORAGE_KEY = 'reknew_orbit_auth';

// ─── Types ───
export interface AuthUser {
  id?: string;
  name: string;
  role: string;
  email: string;
  initials: string;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  loginWithApi: (email: string, password: string, totpCode: string) => Promise<{ success: boolean; message: string }>;
  loginAdmin: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  setUserFromApi: (employee: any) => void;
}

// ─── Context ───
const AuthContext = createContext<AuthContextType | null>(null);

function makeInitials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

// ─── Provider ───
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);

  // Check localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed?.user) {
          setUser(parsed.user);
        }
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // Login via backend API (email + password + TOTP)
  const loginWithApi = async (email: string, password: string, totpCode: string) => {
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, totp_code: totpCode }),
      });

      const result = await response.json();

      if (result.success && result.employee) {
        const authUser: AuthUser = {
          id: result.employee.id,
          name: result.employee.name,
          email: result.employee.email,
          role: result.employee.role || 'Employee',
          initials: makeInitials(result.employee.name),
        };
        setUser(authUser);
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: authUser, token: result.token }));
        return { success: true, message: result.message };
      }

      return { success: false, message: result.message || 'Login failed' };
    } catch {
      return { success: false, message: 'Cannot connect to server' };
    }
  };

  // Simple admin login (superadmin fallback — no TOTP required)
  const loginAdmin = async (email: string, password: string): Promise<boolean> => {
    // Try API first for admin without TOTP
    try {
      const checkRes = await fetch(`${API_BASE}/auth/check-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const checkData = await checkRes.json();

      if (checkData.exists && !checkData.is_first_login) {
        // For super admin without TOTP, use a simplified login
        const authUser: AuthUser = {
          name: 'Super Admin',
          email,
          role: 'Global Access',
          initials: 'SA',
        };
        setUser(authUser);
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: authUser, token: 'admin-token' }));
        return true;
      }
    } catch {
      // Backend not available — use hardcoded fallback
    }

    // Hardcoded fallback for when backend is down
    if (email === 'superadmin@reknew.ai' && password === 'test') {
      const authUser: AuthUser = {
        name: 'Super Admin',
        email: 'superadmin@reknew.ai',
        role: 'Global Access',
        initials: 'SA',
      };
      setUser(authUser);
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: authUser, token: 'mock-token' }));
      return true;
    }
    return false;
  };

  // Set user from API response (used after first-time setup completes)
  const setUserFromApi = (employee: any) => {
    const authUser: AuthUser = {
      id: employee.id,
      name: employee.name || `${employee.first_name} ${employee.last_name}`,
      email: employee.email || employee.work_email,
      role: employee.role || 'Employee',
      initials: makeInitials(employee.name || `${employee.first_name} ${employee.last_name}`),
    };
    setUser(authUser);
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: authUser, token: 'session-token' }));
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: user !== null, loginWithApi, loginAdmin, logout, setUserFromApi }}
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

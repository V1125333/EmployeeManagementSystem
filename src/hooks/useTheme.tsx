import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useAuth } from '@/hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

type ThemeMode = 'light' | 'dark' | 'system';

export interface UserPreferences {
  user_id: string;
  theme_mode: ThemeMode;
  accent_color: string;
  sidebar_collapsed: boolean;
  compact_mode: boolean;
  timezone: string;
  date_format: string;
  default_landing_page: string;
  language: string;
  email_notif_leave_approved: boolean;
  email_notif_leave_rejected: boolean;
  email_notif_timesheet_approved: boolean;
  email_notif_timesheet_rejected: boolean;
  email_notif_allocation_changes: boolean;
  inapp_notifications_enabled: boolean;
}

interface ThemeContextValue {
  preferences: UserPreferences | null;
  themeMode: ThemeMode;
  accentColor: string;
  sidebarCollapsed: boolean;
  compactMode: boolean;
  setThemeMode: (mode: string) => void;
  setAccentColor: (color: string) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setCompactMode: (compact: boolean) => void;
  setPreferencesDraft: (patch: Partial<UserPreferences>) => void;
  savePreferences: () => Promise<UserPreferences | null>;
  saveAppearancePatch: (patch: Partial<UserPreferences>) => Promise<UserPreferences | null>;
  revertPreferences: () => void;
  refreshPreferences: () => Promise<void>;
  isDirty: boolean;
  loading: boolean;
}

const defaultPreferences: UserPreferences = {
  user_id: '',
  theme_mode: 'light',
  accent_color: 'olive',
  sidebar_collapsed: false,
  compact_mode: false,
  timezone: 'Asia/Kolkata',
  date_format: 'DD/MM/YYYY',
  default_landing_page: 'Dashboard',
  language: 'en-US',
  email_notif_leave_approved: true,
  email_notif_leave_rejected: true,
  email_notif_timesheet_approved: true,
  email_notif_timesheet_rejected: true,
  email_notif_allocation_changes: true,
  inapp_notifications_enabled: true,
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function headersFor(user: ReturnType<typeof useAuth>['user']) {
  return {
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': user?.role || '',
    'x-user-name': user?.name || '',
  };
}

function effectiveTheme(mode: ThemeMode) {
  if (mode !== 'system') return mode;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(preferences: UserPreferences) {
  document.documentElement.dataset.theme = effectiveTheme(preferences.theme_mode);
  document.documentElement.dataset.themeMode = preferences.theme_mode;
  document.documentElement.dataset.accent = preferences.accent_color;
  document.documentElement.dataset.compact = String(preferences.compact_mode);
}

function changed(saved: UserPreferences, draft: UserPreferences) {
  return JSON.stringify(saved) !== JSON.stringify(draft);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [savedPreferences, setSavedPreferences] = useState<UserPreferences>(defaultPreferences);
  const [draftPreferences, setDraftPreferences] = useState<UserPreferences>(defaultPreferences);
  const [loading, setLoading] = useState(false);
  const headers = useMemo(() => headersFor(user), [user]);

  const refreshPreferences = useCallback(async () => {
    if (!user?.id && !user?.email) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/settings/preferences`, { headers });
      if (!res.ok) throw new Error('Could not load preferences.');
      const data = await res.json();
      const next = { ...defaultPreferences, ...data };
      setSavedPreferences(next);
      setDraftPreferences(next);
      applyTheme(next);
    } finally {
      setLoading(false);
    }
  }, [headers, user?.email, user?.id]);

  useEffect(() => {
    refreshPreferences().catch(() => undefined);
  }, [refreshPreferences]);

  useEffect(() => {
    applyTheme(draftPreferences);
  }, [draftPreferences]);

  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)');
    const listener = () => applyTheme(draftPreferences);
    query.addEventListener('change', listener);
    return () => query.removeEventListener('change', listener);
  }, [draftPreferences]);

  const setPreferencesDraft = useCallback((patch: Partial<UserPreferences>) => {
    setDraftPreferences((current) => ({ ...current, ...patch }));
  }, []);

  const saveAppearancePatch = useCallback(async (patch: Partial<UserPreferences>) => {
    const nextDraft = { ...draftPreferences, ...patch };
    setDraftPreferences(nextDraft);
    const res = await fetch(`${API_BASE}/settings/preferences/appearance`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({
        theme_mode: patch.theme_mode,
        accent_color: patch.accent_color,
        sidebar_collapsed: patch.sidebar_collapsed,
        compact_mode: patch.compact_mode,
      }),
    });
    if (!res.ok) throw new Error('Could not save appearance preferences.');
    const data = await res.json();
    const next = { ...nextDraft, ...data };
    setSavedPreferences(next);
    setDraftPreferences(next);
    return next;
  }, [draftPreferences, headers]);

  const savePreferences = useCallback(async () => {
    const res = await fetch(`${API_BASE}/settings/preferences/appearance`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({
        theme_mode: draftPreferences.theme_mode,
        accent_color: draftPreferences.accent_color,
        sidebar_collapsed: draftPreferences.sidebar_collapsed,
        compact_mode: draftPreferences.compact_mode,
      }),
    });
    if (!res.ok) throw new Error('Could not save appearance preferences.');
    const data = await res.json();
    const next = { ...draftPreferences, ...data };
    setSavedPreferences(next);
    setDraftPreferences(next);
    return next;
  }, [draftPreferences, headers]);

  const revertPreferences = useCallback(() => {
    setDraftPreferences(savedPreferences);
    applyTheme(savedPreferences);
  }, [savedPreferences]);

  const value = useMemo<ThemeContextValue>(() => ({
    preferences: draftPreferences,
    themeMode: draftPreferences.theme_mode,
    accentColor: draftPreferences.accent_color,
    sidebarCollapsed: draftPreferences.sidebar_collapsed,
    compactMode: draftPreferences.compact_mode,
    setThemeMode: (theme_mode) => setPreferencesDraft({ theme_mode: theme_mode as ThemeMode }),
    setAccentColor: (accent_color) => setPreferencesDraft({ accent_color }),
    setSidebarCollapsed: (sidebar_collapsed) => setPreferencesDraft({ sidebar_collapsed }),
    setCompactMode: (compact_mode) => setPreferencesDraft({ compact_mode }),
    setPreferencesDraft,
    savePreferences,
    saveAppearancePatch,
    revertPreferences,
    refreshPreferences,
    isDirty: changed(savedPreferences, draftPreferences),
    loading,
  }), [draftPreferences, loading, refreshPreferences, revertPreferences, saveAppearancePatch, savePreferences, savedPreferences, setPreferencesDraft]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used inside ThemeProvider');
  }
  return context;
}

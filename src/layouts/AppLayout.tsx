import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Bot } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopNav } from '@/components/layout/TopNav';
import { cn } from '@/utils/cn';
import { useTheme } from '@/hooks/useTheme';

export function AppLayout() {
  const { sidebarCollapsed, compactMode } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const showAskOrbitLauncher = location.pathname !== '/ask-orbit-ai';

  return (
    <div className="min-h-screen bg-warm-bg font-sans" data-compact={compactMode}>
      <Sidebar />

      <div
        className={cn(
          'transition-all duration-250 min-h-screen',
          sidebarCollapsed ? 'ml-16' : 'ml-60'
        )}
      >
        <TopNav />

        <main className="px-[var(--layout-main-padding-x)] py-[var(--layout-main-padding-y)]">
          <Outlet />
        </main>
      </div>

      {showAskOrbitLauncher && (
        <button
          type="button"
          onClick={() => navigate('/ask-orbit-ai')}
          title="Ask Orbit AI"
          aria-label="Open Ask Orbit AI"
          className="fixed bottom-7 right-7 z-50 flex h-16 w-16 items-center justify-center rounded-2xl border border-accent-mid bg-[var(--color-text-primary)] text-accent shadow-[0_22px_55px_color-mix(in_srgb,var(--color-brand-navy)_28%,transparent)] transition-all duration-150 hover:-translate-y-0.5 hover:bg-accent hover:text-[var(--color-text-primary)] focus:outline-none focus:ring-4 focus:ring-accent-light active:scale-95"
        >
          <Bot size={29} />
        </button>
      )}
    </div>
  );
}

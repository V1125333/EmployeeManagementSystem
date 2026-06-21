import { Outlet } from 'react-router-dom';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopNav } from '@/components/layout/TopNav';
import { cn } from '@/utils/cn';
import { useTheme } from '@/hooks/useTheme';

export function AppLayout() {
  const { sidebarCollapsed, compactMode } = useTheme();

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
    </div>
  );
}

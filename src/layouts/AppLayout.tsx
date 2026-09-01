import { Outlet } from 'react-router-dom';
import { OrbitFloatingAssistant } from '@/components/ai/OrbitFloatingAssistant';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopNav } from '@/components/layout/TopNav';
import { cn } from '@/utils/cn';
import { useTheme } from '@/hooks/useTheme';

export function AppLayout() {
  const { sidebarCollapsed, compactMode } = useTheme();

  return (
    <div className="min-h-screen bg-warm-bg font-sans" data-compact={compactMode}>
      <div className="min-h-screen">
        <Sidebar />
        <div className={cn('min-h-screen transition-all duration-250', sidebarCollapsed ? 'ml-16' : 'ml-60')}>
          <TopNav />
          <main className="px-[var(--layout-main-padding-x)] pb-[var(--layout-main-padding-y)] pt-[var(--layout-main-padding-y)]">
            <Outlet />
          </main>
          <OrbitFloatingAssistant />
        </div>
      </div>
    </div>
  );
}

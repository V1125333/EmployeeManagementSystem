import { Outlet } from 'react-router-dom';
import { OrbitFloatingAssistant } from '@/components/ai/OrbitFloatingAssistant';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopNav } from '@/components/layout/TopNav';
import { cn } from '@/utils/cn';
import { useTheme } from '@/hooks/useTheme';
import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';

export function AppLayout() {
  const { sidebarCollapsed, compactMode } = useTheme();
  const location = useLocation();
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);

  useEffect(() => setMobileNavigationOpen(false), [location.pathname]);

  return (
    <div className="min-h-screen overflow-x-hidden bg-warm-bg font-sans" data-compact={compactMode}>
      <div className="min-h-screen">
        <Sidebar mobileOpen={mobileNavigationOpen} onMobileClose={() => setMobileNavigationOpen(false)} />
        <div className={cn('min-h-screen min-w-0 transition-all duration-250', sidebarCollapsed ? 'md:ml-16' : 'md:ml-60')}>
          <TopNav onOpenMobileNavigation={() => setMobileNavigationOpen(true)} />
          <main className="min-w-0 px-[var(--layout-main-padding-x)] pb-[var(--layout-main-padding-y)] pt-[var(--layout-main-padding-y)]">
            <Outlet />
          </main>
          <OrbitFloatingAssistant />
        </div>
      </div>
    </div>
  );
}

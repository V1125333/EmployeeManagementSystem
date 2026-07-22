import { useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, UserPlus, Briefcase, CalendarDays,
  Network, Package, Settings, Shield, FileText,
  PanelLeftClose, PanelLeftOpen, Award, Files, CalendarPlus,
  WalletCards, ClipboardCheck, Clock3, LogIn, Send, PartyPopper,
  BookOpen, CalendarClock, ClipboardList, Bot,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { mainNavItems, adminNavItems, employeeNavItems, resourceNavItems } from '@/data/mockData';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { ProfileDropdown } from '@/components/ui/ProfileDropdown';

const iconMap: Record<string, React.ElementType> = {
  LayoutDashboard, Users, UserPlus, Briefcase, CalendarDays,
  Network, Package, Settings, Shield, FileText, Award, Files,
  CalendarPlus, WalletCards, ClipboardCheck, Clock3, LogIn, Send,
  PartyPopper, BookOpen, CalendarClock, ClipboardList,
  Bot,
};

function isAdminRole(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalized);
}

function isManagerRole(role?: string) {
  return (role || '').toLowerCase().replace(/\s+/g, '_') === 'manager';
}

function canReviewApprovals(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return ['manager', 'super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalized);
}

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { sidebarCollapsed: collapsed, saveAppearancePatch } = useTheme();
  const showAdminNavigation = isAdminRole(user?.role);
  const showManagerResources = isManagerRole(user?.role);
  const employeeNavigation = employeeNavItems.filter((item) => (
    item.key !== 'leave-approvals' || canReviewApprovals(user?.role)
  ));
  const careerNavigationKeys = new Set(['projects', 'career-profile']);
  const primaryEmployeeNavigation = employeeNavigation.filter((item) => !careerNavigationKeys.has(item.key));
  const careerEmployeeNavigation = employeeNavigation.filter((item) => careerNavigationKeys.has(item.key));
  const currentUser = user || {
    name: 'User',
    role: 'Employee',
    email: 'user@reknew.ai',
    initials: 'U',
    profileImageUrl: null,
  };

  const handleViewProfile = () => navigate('/profile');
  const handleSettings = () => navigate('/settings');
  const handleSignOut = () => {
    logout();
    navigate('/login');
  };
  const handleToggle = () => {
    saveAppearancePatch({ sidebar_collapsed: !collapsed }).catch(() => undefined);
  };

  const NavButton = ({ item }: { item: typeof mainNavItems[0] }) => {
    const active = location.pathname === item.path;
    const IconComp = iconMap[item.icon] || LayoutDashboard;
    const displayLabel = item.key === 'projects' && showManagerResources ? 'Projects' : item.label;

    return (
      <button
        onClick={() => navigate(item.path)}
        title={collapsed ? displayLabel : undefined}
        className={cn(
          'relative w-full flex items-center gap-2.5 rounded-lg text-[13.5px] font-medium transition-all duration-150 mb-0.5',
          collapsed ? 'justify-center px-0 py-2.5' : 'px-3.5 py-2.5',
          active
            ? 'border border-accent-mid bg-accent-light text-[var(--color-nav-active-text)] shadow-sm'
            : 'border border-transparent text-gray-500 hover:border-accent-mid hover:bg-hover-bg hover:text-[var(--color-nav-active-text)]'
        )}
      >
        {active && <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-[var(--color-nav-active-bar)]" />}
        <IconComp size={18} className={cn('shrink-0', active ? 'text-[var(--color-nav-active-bar)]' : 'text-gray-500')} />
        {!collapsed && <span className="truncate">{displayLabel}</span>}
      </button>
    );
  };

  return (
    <aside
      className={cn(
        'fixed top-0 left-0 h-screen bg-warm-card border-r border-[var(--color-border)] z-50 flex flex-col transition-all duration-250',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Logo */}
      <div
        className={cn(
          'flex h-14 shrink-0 items-center border-b border-[var(--color-border)]',
          collapsed ? 'justify-center px-2' : 'justify-between px-5'
        )}
      >
        <div className={cn('flex items-center overflow-hidden', collapsed && 'hidden')}>
          <img
            src="/reknew-orbit.png"
            alt="Reknew Orbit"
            className="h-10 w-[166px] object-contain object-left"
          />
        </div>

        {/* Collapse button — only when expanded */}
        <button
          onClick={handleToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cn(
            'h-8 w-8 rounded-lg flex items-center justify-center text-gray-400 hover:bg-hover-bg hover:text-accent transition-all duration-150',
            collapsed && 'h-10 w-10 border border-[var(--color-border)] bg-warm-card p-1'
          )}
        >
          {collapsed ? (
            <img src="/reknew-logo-icon.png" alt="" className="h-full w-full object-contain" />
          ) : (
            <PanelLeftClose size={16} />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className={cn('flex-1 overflow-y-auto', collapsed ? 'px-2 py-3' : 'px-3 py-3')}>
        {showAdminNavigation ? (
          <>
            {mainNavItems.map((item) => (
              <NavButton key={item.key} item={item} />
            ))}

            <div className={cn('my-3', collapsed ? 'px-1' : 'px-3.5')}>
              {!collapsed && (
                <div className="text-[10px] font-semibold text-gray-400 tracking-widest uppercase">
                  Resource Management
                </div>
              )}
              {collapsed && <div className="h-px bg-[var(--color-border)]" />}
            </div>

            {resourceNavItems.map((item) => (
              <NavButton key={item.key} item={item} />
            ))}

            {/* Admin section divider */}
            <div className={cn('my-3', collapsed ? 'px-1' : 'px-3.5')}>
              {!collapsed && (
                <div className="text-[10px] font-semibold text-gray-400 tracking-widest uppercase">
                  Admin Console
                </div>
              )}
              {collapsed && <div className="h-px bg-[var(--color-border)]" />}
            </div>

            {adminNavItems.map((item) => (
              <NavButton key={item.key} item={item} />
            ))}
          </>
        ) : (
          <>
            {primaryEmployeeNavigation.map((item) => (
              <NavButton key={item.key} item={item} />
            ))}
            {careerEmployeeNavigation.length > 0 && (
              <>
                <div className={cn('my-3', collapsed ? 'px-1' : 'px-3.5')}>
                  {!collapsed && (
                    <div className="text-[10px] font-semibold text-gray-400 tracking-widest uppercase">
                      Career & Work
                    </div>
                  )}
                  {collapsed && <div className="h-px bg-[var(--color-border)]" />}
                </div>
                {careerEmployeeNavigation.map((item) => (
                  <NavButton key={item.key} item={item} />
                ))}
              </>
            )}
            {showManagerResources && (
              <>
                <div className={cn('my-3', collapsed ? 'px-1' : 'px-3.5')}>
                  {!collapsed && (
                    <div className="text-[10px] font-semibold text-gray-400 tracking-widest uppercase">
                      Resource Management
                    </div>
                  )}
                  {collapsed && <div className="h-px bg-[var(--color-border)]" />}
                </div>
                {resourceNavItems.map((item) => (
                  <NavButton key={item.key} item={item} />
                ))}
              </>
            )}
          </>
        )}
      </nav>

      <div className="shrink-0 border-t border-[var(--color-border)] px-3 py-3">
        <ProfileDropdown
          user={currentUser}
          variant={collapsed ? 'collapsed' : 'sidebar'}
          placement="top-left"
          onViewProfile={handleViewProfile}
          onSettings={handleSettings}
          onSignOut={handleSignOut}
        />
      </div>
    </aside>
  );
}

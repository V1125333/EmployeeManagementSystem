import { useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, UserPlus, Briefcase, CalendarDays,
  Network, Package, Settings, Shield, FileText,
  PanelLeftClose, PanelLeftOpen, Award, Files, CalendarPlus,
  WalletCards, ClipboardCheck, Clock3, LogIn, Send, PartyPopper,
  BookOpen, CalendarClock, ClipboardList, Bot, X,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { mainNavItems, adminNavItems, employeeNavItems, resourceNavItems } from '@/data/mockData';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { ProfileDropdown } from '@/components/ui/ProfileDropdown';
import { canAccess, type PermissionScope } from '@/auth/rbac';
import type { NavItem } from '@/types';

const iconMap: Record<string, React.ElementType> = {
  LayoutDashboard, Users, UserPlus, Briefcase, CalendarDays,
  Network, Package, Settings, Shield, FileText, Award, Files,
  CalendarPlus, WalletCards, ClipboardCheck, Clock3, LogIn, Send,
  PartyPopper, BookOpen, CalendarClock, ClipboardList,
  Bot,
};

const NAV_ACCESS: Record<string, { permission: string; scopes?: PermissionScope[] }> = {
  '/employee': { permission: 'portal.access' },
  '/employee/apply-leave': { permission: 'leave.request' },
  '/employee/approvals': { permission: 'leave.approve' },
  '/employee/timesheets': { permission: 'timesheet.manage' },
  '/employee/check-in': { permission: 'attendance.read' },
  '/employee/requests': { permission: 'portal.access' },
  '/employee/documents': { permission: 'document.read' },
  '/employee/career-profile': { permission: 'portal.access' },
  '/employee/company-handbook': { permission: 'portal.access' },
  '/employee/holidays': { permission: 'portal.access' },
  '/dashboard': { permission: 'employee.read', scopes: ['organization'] },
  '/employees': { permission: 'employee.read', scopes: ['organization'] },
  '/onboarding': { permission: 'onboarding.manage' },
  '/client-onboarding': { permission: 'client.manage' },
  '/projects': { permission: 'project.read' },
  '/time-off': { permission: 'leave.manage', scopes: ['organization'] },
  '/timesheets': { permission: 'timesheet.manage' },
  '/team-allocation': { permission: 'allocation.manage' },
  '/assets': { permission: 'asset.manage' },
  '/bench': { permission: 'allocation.read', scopes: ['direct_reports', 'organization'] },
  '/staffing-requests': { permission: 'staffing.request' },
  '/forecasting': { permission: 'forecast.read' },
  '/talent-profiles': { permission: 'talent.read' },
  '/admin/users': { permission: 'security.account.manage' },
  '/admin/roles': { permission: 'role.manage' },
  '/admin/policies': { permission: 'hr_policy.manage' },
  '/admin/security': { permission: 'security.account.manage' },
  '/admin/certificates': { permission: 'certificate.manage' },
  '/admin/hr-documents': { permission: 'document.manage_hr' },
  '/admin/audit-trail': { permission: 'audit.read_hr' },
};

interface SidebarProps {
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({ mobileOpen = false, onMobileClose }: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { sidebarCollapsed: collapsed, saveAppearancePatch } = useTheme();
  const visible = (items: NavItem[]) => items.filter((item) => {
    const access = NAV_ACCESS[item.path];
    if (item.path === '/admin/audit-trail') {
      return canAccess(user, 'audit.read_hr') || canAccess(user, 'audit.read_security');
    }
    return Boolean(access && canAccess(user, access.permission, access.scopes));
  });
  const employeeNavigation = visible(employeeNavItems);
  const overviewNavigation = visible(mainNavItems).filter((item) => item.path === '/dashboard');
  const hasOrganizationWorkspace = canAccess(user, 'employee.read', ['organization']);
  const operationsNavigation = visible(mainNavItems).filter((item) => {
    if (item.path === '/dashboard') return false;
    // Organization-level users get the administrative Projects and My
    // Timesheets entries. Self-service users get their workspace equivalents
    // below, so neither audience sees two links to the same page.
    if (!hasOrganizationWorkspace && ['/projects', '/timesheets'].includes(item.path)) return false;
    return true;
  });
  const careerNavigationKeys = new Set(['projects', 'career-profile']);
  const primaryEmployeeNavigation = employeeNavigation.filter((item) => {
    if (careerNavigationKeys.has(item.key)) return false;
    return !(hasOrganizationWorkspace && item.path === '/employee/timesheets');
  });
  const careerEmployeeNavigation = employeeNavigation.filter((item) => {
    if (!careerNavigationKeys.has(item.key)) return false;
    return !(hasOrganizationWorkspace && item.path === '/projects');
  });
  const currentUser = user || {
    name: 'User',
    role: 'Employee',
    email: 'user@reknew.ai',
    initials: 'U',
    profileImageUrl: null,
    permissions: [],
    scopes: {},
  };

  const goTo = (path: string) => {
    navigate(path);
    onMobileClose?.();
  };
  const handleViewProfile = () => goTo('/profile');
  const handleSettings = () => goTo('/settings');
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
    const displayLabel = item.label;

    return (
      <button
        onClick={() => goTo(item.path)}
        title={collapsed ? displayLabel : undefined}
        className={cn(
          'relative w-full flex items-center gap-2.5 rounded-lg text-[13.5px] font-medium transition-all duration-150 mb-0.5',
          collapsed ? 'px-3.5 py-2.5 md:justify-center md:px-0' : 'px-3.5 py-2.5',
          active
            ? 'border border-accent-mid bg-accent-light text-[var(--color-nav-active-text)] shadow-sm'
            : 'border border-transparent text-gray-500 hover:border-accent-mid hover:bg-hover-bg hover:text-[var(--color-nav-active-text)]'
        )}
      >
        {active && <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-[var(--color-nav-active-bar)]" />}
        <IconComp size={18} className={cn('shrink-0', active ? 'text-[var(--color-nav-active-bar)]' : 'text-gray-500')} />
        <span className={cn('truncate', collapsed && 'md:hidden')}>{displayLabel}</span>
      </button>
    );
  };

  return (
    <>
      {mobileOpen && (
        <button type="button" aria-label="Close navigation" onClick={onMobileClose} className="fixed inset-0 z-40 bg-black/35 backdrop-blur-[1px] md:hidden" />
      )}
    <aside
      className={cn(
        'fixed left-0 top-0 z-50 flex h-[100dvh] w-[min(20rem,86vw)] flex-col border-r border-[var(--color-border)] bg-warm-card transition-all duration-250',
        mobileOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full',
        'md:translate-x-0 md:shadow-none',
        collapsed ? 'md:w-16' : 'md:w-60'
      )}
    >
      {/* Logo */}
      <div
        className={cn(
          'flex h-14 shrink-0 items-center border-b border-[var(--color-border)]',
          collapsed ? 'justify-between px-5 md:justify-center md:px-2' : 'justify-between px-5'
        )}
      >
        <div className={cn('flex items-center overflow-hidden', collapsed && 'md:hidden')}>
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
            collapsed && 'md:h-10 md:w-10 md:border md:border-[var(--color-border)] md:bg-warm-card md:p-1',
            'hidden md:flex'
          )}
        >
          {collapsed ? (
            <img src="/reknew-logo-icon.png" alt="" className="h-full w-full object-contain" />
          ) : (
            <PanelLeftClose size={16} />
          )}
        </button>
        <button type="button" onClick={onMobileClose} aria-label="Close navigation" className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-500 hover:bg-hover-bg md:hidden">
          <X size={20} />
        </button>
      </div>

      {/* Navigation */}
      <nav className={cn('flex-1 overflow-y-auto overscroll-contain', collapsed ? 'px-3 py-3 md:px-2' : 'px-3 py-3')}>
        <>
            {overviewNavigation.map((item) => (
              <NavButton key={item.key} item={item} />
            ))}
            <div className={cn('px-3.5 pb-2 text-[10px] font-semibold uppercase tracking-widest text-gray-400', collapsed && 'md:hidden')}>My Workspace</div>
            {primaryEmployeeNavigation.map((item) => (
              <NavButton key={item.key} item={item} />
            ))}
            {careerEmployeeNavigation.length > 0 && (
              <>
                <div className={cn('my-3', collapsed ? 'px-1' : 'px-3.5')}>
                  {(!collapsed || mobileOpen) && (
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
            {visible(resourceNavItems).length > 0 && (
              <>
                <div className={cn('my-3', collapsed ? 'px-1' : 'px-3.5')}>
                  {(!collapsed || mobileOpen) && (
                    <div className="text-[10px] font-semibold text-gray-400 tracking-widest uppercase">
                      Resource Management
                    </div>
                  )}
                  {collapsed && <div className="h-px bg-[var(--color-border)]" />}
                </div>
                {visible(resourceNavItems).map((item) => (
                  <NavButton key={item.key} item={item} />
                ))}
              </>
            )}
            {operationsNavigation.length > 0 && (
              <>
                <div className={cn('my-3', collapsed ? 'px-1' : 'px-3.5')}>
                  {(!collapsed || mobileOpen) && <div className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">HR & Operations</div>}
                  {collapsed && <div className="h-px bg-[var(--color-border)]" />}
                </div>
                {operationsNavigation.map((item) => <NavButton key={item.key} item={item} />)}
              </>
            )}
            {visible(adminNavItems).length > 0 && (
              <>
                <div className={cn('my-3', collapsed ? 'px-1' : 'px-3.5')}>
                  {(!collapsed || mobileOpen) && <div className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">Administration & Security</div>}
                  {collapsed && <div className="h-px bg-[var(--color-border)]" />}
                </div>
                {visible(adminNavItems).map((item) => <NavButton key={item.key} item={item} />)}
              </>
            )}
          </>
      </nav>

      <div className="shrink-0 border-t border-[var(--color-border)] px-3 py-3">
        <ProfileDropdown
          user={currentUser}
          variant={collapsed && !mobileOpen ? 'collapsed' : 'sidebar'}
          placement="top-left"
          onViewProfile={handleViewProfile}
          onSettings={handleSettings}
          onSignOut={handleSignOut}
        />
      </div>
    </aside>
    </>
  );
}

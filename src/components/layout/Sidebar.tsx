import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, UserPlus, Briefcase, CalendarDays,
  Network, Package, Settings, Shield, FileText,
  PanelLeftClose, PanelLeftOpen, Award, Files, CalendarPlus,
  WalletCards, ClipboardCheck, Clock3, LogIn, Send, PartyPopper,
  BookOpen,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { mainNavItems, adminNavItems, employeeNavItems } from '@/data/mockData';
import { useAuth } from '@/hooks/useAuth';

const iconMap: Record<string, React.ElementType> = {
  LayoutDashboard, Users, UserPlus, Briefcase, CalendarDays,
  Network, Package, Settings, Shield, FileText, Award, Files,
  CalendarPlus, WalletCards, ClipboardCheck, Clock3, LogIn, Send,
  PartyPopper, BookOpen,
};

function isAdminRole(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalized);
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const showAdminNavigation = isAdminRole(user?.role);

  const NavButton = ({ item }: { item: typeof mainNavItems[0] }) => {
    const active = location.pathname === item.path;
    const IconComp = iconMap[item.icon] || LayoutDashboard;

    return (
      <button
        onClick={() => navigate(item.path)}
        title={collapsed ? item.label : undefined}
        className={cn(
          'w-full flex items-center gap-2.5 rounded-lg text-[13.5px] font-medium transition-all duration-150 mb-0.5',
          collapsed ? 'justify-center px-0 py-2.5' : 'px-3.5 py-2.5',
          active
            ? 'bg-olive text-white'
            : 'text-gray-500 hover:bg-hover-bg hover:text-[#2F3437]'
        )}
      >
        <IconComp size={18} className="shrink-0" />
        {!collapsed && <span className="truncate">{item.label}</span>}
      </button>
    );
  };

  return (
    <aside
      className={cn(
        'fixed top-0 left-0 h-screen bg-warm-card border-r border-[#E5E7EB] z-50 flex flex-col transition-all duration-250',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Logo */}
      <div
        className={cn(
          'flex items-center border-b border-[#E5E7EB] shrink-0',
          collapsed ? 'justify-center px-2 py-5' : 'justify-between px-5 py-5'
        )}
      >
        <div className={cn('flex items-center gap-2.5 overflow-hidden', collapsed && 'hidden')}>
          <div className="w-8 h-8 rounded-lg bg-olive flex items-center justify-center text-white font-extrabold text-sm shrink-0">
            R
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-[15px] font-bold text-[#2F3437] tracking-tight leading-tight">
                Reknew <span className="text-olive">Orbit</span>
              </div>
              <div className="text-[10px] text-gray-400 font-medium tracking-wide">
                Employee Management
              </div>
            </div>
          )}
        </div>

        {/* Collapse button — only when expanded */}
        <button
          onClick={onToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cn(
            'h-8 w-8 rounded-lg flex items-center justify-center text-gray-400 hover:bg-hover-bg hover:text-olive transition-all duration-150',
            collapsed && 'border border-[#E5E7EB] bg-white'
          )}
        >
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>
      </div>

      {/* Navigation */}
      <nav className={cn('flex-1 overflow-y-auto', collapsed ? 'px-2 py-3' : 'px-3 py-3')}>
        {showAdminNavigation ? (
          <>
            {mainNavItems.map((item) => (
              <NavButton key={item.key} item={item} />
            ))}

            {/* Admin section divider */}
            <div className={cn('my-3', collapsed ? 'px-1' : 'px-3.5')}>
              {!collapsed && (
                <div className="text-[10px] font-bold text-gray-400 tracking-widest uppercase">
                  Admin Console
                </div>
              )}
              {collapsed && <div className="h-px bg-[#E5E7EB]" />}
            </div>

            {adminNavItems.map((item) => (
              <NavButton key={item.key} item={item} />
            ))}
          </>
        ) : (
          employeeNavItems.map((item) => (
            <NavButton key={item.key} item={item} />
          ))
        )}
      </nav>

      {/* Expand button — only when collapsed, sits at bottom */}
    </aside>
  );
}

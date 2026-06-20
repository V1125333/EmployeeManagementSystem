import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { ChevronDown, LogOut, Settings, User } from 'lucide-react';
import { Avatar } from '@/components/ui';
import { cn } from '@/utils/cn';

interface ProfileUser {
  name: string;
  role: string;
  email: string;
  initials: string;
  profileImageUrl?: string | null;
}

interface ProfileDropdownProps {
  user: ProfileUser;
  onViewProfile?: () => void;
  onSettings?: () => void;
  onSignOut?: () => void;
  variant?: 'header' | 'sidebar' | 'collapsed';
  placement?: 'bottom-right' | 'top-left' | 'top-right';
}

interface MenuItemProps {
  icon: React.ReactNode;
  label: string;
  onClick?: () => void;
  variant?: 'default' | 'danger';
}

function MenuItem({ icon, label, onClick, variant = 'default' }: MenuItemProps) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={cn(
        'group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-[13.5px] font-semibold outline-none transition-all duration-150',
        'focus-visible:ring-2 focus-visible:ring-olive/30 focus-visible:ring-offset-1 focus-visible:ring-offset-warm-card',
        variant === 'danger'
          ? 'text-status-error hover:bg-status-error/10 focus-visible:bg-status-error/10'
          : 'text-[#2F3437] hover:bg-hover-bg focus-visible:bg-hover-bg'
      )}
    >
      <span
        className={cn(
          'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors',
          variant === 'danger' ? 'text-status-error' : 'text-gray-400 group-hover:text-olive'
        )}
      >
        {icon}
      </span>
      <span className="truncate">{label}</span>
    </button>
  );
}

export function ProfileDropdown({
  user,
  onViewProfile,
  onSettings,
  onSignOut,
  variant = 'header',
  placement = 'bottom-right',
}: ProfileDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  const handleAction = (callback?: () => void) => {
    setIsOpen(false);
    callback?.();
  };

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setIsOpen((current) => !current);
      return;
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setIsOpen(true);
      window.setTimeout(() => {
        menuRef.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
      }, 0);
    }
  };

  const handleMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Tab') return;

    const focusableItems = Array.from(
      menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') || []
    );
    if (!focusableItems.length) return;

    const firstItem = focusableItems[0];
    const lastItem = focusableItems[focusableItems.length - 1];

    if (event.shiftKey && document.activeElement === firstItem) {
      event.preventDefault();
      lastItem.focus();
    } else if (!event.shiftKey && document.activeElement === lastItem) {
      event.preventDefault();
      firstItem.focus();
    }
  };

  const isCollapsed = variant === 'collapsed';
  const isSidebar = variant === 'sidebar';
  const panelPosition = placement === 'top-left'
    ? 'left-0 bottom-full'
    : placement === 'top-right'
      ? 'right-0 bottom-full'
      : 'right-0 top-full mt-2';
  const panelWidth = isSidebar ? 'w-full' : 'w-[280px]';

  return (
    <div ref={dropdownRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label="Open profile menu"
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={handleTriggerKeyDown}
        title={`${user.name} - ${user.role}`}
        className={cn(
          'group flex items-center gap-2 rounded-xl outline-none transition-all duration-200',
          'focus-visible:ring-2 focus-visible:ring-olive/30 focus-visible:ring-offset-2 focus-visible:ring-offset-warm-card',
          variant === 'header' && 'px-2.5 py-1.5',
          isSidebar && 'w-full items-start border border-transparent px-3 py-3 text-left hover:border-[#E5E7EB] hover:bg-hover-bg/70 hover:shadow-sm',
          isCollapsed && 'h-10 w-10 justify-center border border-transparent p-0 hover:border-[#E5E7EB] hover:bg-hover-bg',
          isOpen && cn('bg-hover-bg ring-1 ring-olive/20 shadow-sm', isSidebar && 'rounded-t-none border-[#E5E7EB]')
        )}
      >
        <span className="relative shrink-0">
          <Avatar initials={user.initials} size="sm" variant="filled" src={user.profileImageUrl} />
          {!isCollapsed && (
            <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-warm-card bg-status-success" />
          )}
        </span>

        {isSidebar && (
          <div className="min-w-0 flex-1 text-left">
            <div className="break-words text-[13.5px] font-bold leading-snug text-[#2F3437]">
              {user.name}
            </div>
            <div className="mt-1 flex items-center justify-between gap-2">
              <div className="min-w-0 truncate text-[11px] font-medium text-gray-400">{user.role}</div>
              <ChevronDown
                size={14}
                className={cn(
                  'shrink-0 text-gray-400 transition-transform duration-200 ease-out group-hover:text-olive',
                  isOpen && 'rotate-180 text-olive'
                )}
              />
            </div>
          </div>
        )}

        {!isCollapsed && !isSidebar && (
          <div className="min-w-0 flex-1 text-left">
            <div className="truncate text-[12.5px] font-semibold text-[#2F3437]">{user.name}</div>
            <div className="truncate text-[10.5px] text-gray-400">{user.role}</div>
          </div>
        )}

        {!isCollapsed && !isSidebar && (
          <ChevronDown
            size={14}
            className={cn(
              'shrink-0 text-gray-400 transition-transform duration-200 ease-out group-hover:text-olive',
              isOpen && 'rotate-180 text-olive'
            )}
          />
        )}
      </button>

      {isOpen && (
        <div
          ref={menuRef}
          role="menu"
          aria-label="Profile menu"
          onKeyDown={handleMenuKeyDown}
          className={cn(
            'absolute',
            panelPosition,
            panelWidth,
            'z-50 overflow-hidden border border-[#E5E7EB] bg-warm-card',
            'shadow-[0_18px_45px_rgba(47,52,55,0.16),0_4px_14px_rgba(47,52,55,0.08)]',
            'animate-profile-menu',
            isSidebar ? 'rounded-t-2xl rounded-b-none border-b-0' : 'rounded-2xl'
          )}
        >
          <div className="border-b border-[#E5E7EB] bg-gradient-to-b from-white to-warm-card px-4 py-3.5">
            <div className="flex items-center gap-3">
              <Avatar initials={user.initials} size="lg" variant="filled" src={user.profileImageUrl} />
              <div className="min-w-0">
                <div className="break-words text-[15px] font-semibold leading-snug text-[#2F3437]">{user.name}</div>
                <div className="text-[12px] font-medium text-gray-500">{user.role}</div>
                <div className="truncate text-[12px] text-gray-400">{user.email}</div>
              </div>
            </div>
          </div>

          <div className="space-y-0.5 px-2 py-2">
            <MenuItem icon={<User size={16} />} label="My Profile" onClick={() => handleAction(onViewProfile)} />
            <MenuItem icon={<Settings size={16} />} label="Settings" onClick={() => handleAction(onSettings)} />
          </div>

          <div className="mx-4 h-px bg-[#E5E7EB]" />

          <div className="px-2 py-2">
            <MenuItem icon={<LogOut size={16} />} label="Sign Out" variant="danger" onClick={() => handleAction(onSignOut)} />
          </div>
        </div>
      )}
    </div>
  );
}

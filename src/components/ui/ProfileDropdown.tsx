import { useState, useRef, useEffect } from 'react';
import { User, Settings, LogOut, ChevronDown, ChevronUp } from 'lucide-react';
import { Avatar } from '@/components/ui';
import { cn } from '@/utils/cn';

// ─── Types ───
interface ProfileUser {
  name: string;
  role: string;
  email: string;
  initials: string;
}

interface ProfileDropdownProps {
  user: ProfileUser;
  onViewProfile?: () => void;
  onAccountSettings?: () => void;
  onSignOut?: () => void;
}

// ─── Menu Item Component ───
interface MenuItemProps {
  icon: React.ReactNode;
  label: string;
  onClick?: () => void;
  variant?: 'default' | 'danger';
}

function MenuItem({ icon, label, onClick, variant = 'default' }: MenuItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-4 py-2.5 text-[13.5px] font-medium transition-all duration-150 rounded-lg mx-auto',
        variant === 'danger'
          ? 'text-status-error hover:bg-status-error/5'
          : 'text-[#2F3437] hover:bg-hover-bg'
      )}
    >
      <span className={cn(
        'shrink-0',
        variant === 'danger' ? 'text-status-error' : 'text-gray-400'
      )}>
        {icon}
      </span>
      {label}
    </button>
  );
}

// ─── Profile Dropdown Component ───
export function ProfileDropdown({
  user,
  onViewProfile,
  onAccountSettings,
  onSignOut,
}: ProfileDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Close dropdown after selecting an option
  const handleAction = (callback?: () => void) => {
    setIsOpen(false);
    callback?.();
  };

  return (
    <div ref={dropdownRef} className="relative">
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center gap-2 px-2.5 py-1.5 rounded-lg transition-all duration-150',
          isOpen
            ? 'bg-hover-bg ring-1 ring-olive/20'
            : 'hover:bg-hover-bg'
        )}
      >
        <Avatar initials={user.initials} size="sm" variant="filled" />
        <div className="text-left">
          <div className="text-[12.5px] font-semibold text-[#2F3437]">
            {user.name}
          </div>
          <div className="text-[10.5px] text-gray-400">{user.role}</div>
        </div>
        {isOpen ? (
          <ChevronUp size={14} className="text-olive" />
        ) : (
          <ChevronDown size={14} className="text-gray-400" />
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div
          className={cn(
            'absolute right-0 top-full mt-2 w-[280px]',
            'bg-warm-card border border-[#E5E7EB] rounded-2xl',
            'shadow-[0_8px_30px_rgba(47,52,55,0.08),0_2px_8px_rgba(47,52,55,0.04)]',
            'z-50 overflow-hidden',
            'animate-fade-up'
          )}
        >
          {/* User Info Header */}
          <div className="px-5 py-4 border-b border-[#E5E7EB]">
            <div className="flex items-center gap-3">
              <Avatar initials={user.initials} size="lg" variant="filled" />
              <div className="min-w-0">
                <div className="text-[15px] font-semibold text-[#2F3437] truncate">
                  {user.name}
                </div>
                <div className="text-[12px] text-gray-500 font-medium">
                  {user.role}
                </div>
                <div className="text-[12px] text-gray-400 truncate">
                  {user.email}
                </div>
              </div>
            </div>
          </div>

          {/* Menu Items */}
          <div className="px-2 py-2">
            <MenuItem
              icon={<User size={16} />}
              label="View My Profile"
              onClick={() => handleAction(onViewProfile)}
            />
            <MenuItem
              icon={<Settings size={16} />}
              label="Account Settings"
              onClick={() => handleAction(onAccountSettings)}
            />
          </div>

          {/* Divider */}
          <div className="h-px bg-[#E5E7EB] mx-4" />

          {/* Sign Out */}
          <div className="px-2 py-2">
            <MenuItem
              icon={<LogOut size={16} />}
              label="Sign Out"
              variant="danger"
              onClick={() => handleAction(onSignOut)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

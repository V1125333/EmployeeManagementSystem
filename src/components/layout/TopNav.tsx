import { useNavigate } from 'react-router-dom';
import { Search, Inbox, Bell, HelpCircle } from 'lucide-react';
import { ProfileDropdown } from '@/components/ui/ProfileDropdown';
import { useAuth } from '@/hooks/useAuth';

export function TopNav() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleViewProfile = () => {
    navigate('/profile');
  };

  const handleAccountSettings = () => {
    // TODO: navigate to account settings
    console.log('Navigate to account settings');
  };

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  // Fallback user data (should never show if ProtectedRoute works)
  const currentUser = user || {
    name: 'User',
    role: 'Employee',
    email: 'user@reknew.ai',
    initials: 'U',
    profileImageUrl: null,
  };

  return (
    <header className="h-14 flex items-center justify-between px-7 bg-warm-card border-b border-[#E5E7EB] sticky top-0 z-40">
      {/* Left — Search */}
      <div className="flex items-center">
        <div className="flex items-center gap-2 bg-warm-bg border border-[#E5E7EB] rounded-btn px-3.5 py-[7px] w-[340px]">
          <Search size={16} className="text-gray-400 shrink-0" />
          <input
            type="text"
            placeholder="Search employees, projects, skills..."
            className="bg-transparent border-none outline-none text-[13px] text-[#2F3437] placeholder:text-gray-400 w-full font-sans"
          />
        </div>
      </div>

      {/* Right — Icons + Profile */}
      <div className="flex items-center gap-1">
        {[
          { Icon: Inbox, badge: 3 },
          { Icon: Bell, badge: 7 },
          { Icon: HelpCircle, badge: 0 },
        ].map(({ Icon, badge }, i) => (
          <button
            key={i}
            className="relative w-9 h-9 rounded-lg flex items-center justify-center text-gray-400 hover:bg-hover-bg hover:text-gray-600 transition-all"
          >
            <Icon size={18} />
            {badge > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-status-error text-white text-[9px] font-bold flex items-center justify-center">
                {badge}
              </span>
            )}
          </button>
        ))}

        <div className="w-px h-6 bg-[#E5E7EB] mx-2" />

        {/* Profile Dropdown */}
        <ProfileDropdown
          user={currentUser}
          onViewProfile={handleViewProfile}
          onAccountSettings={handleAccountSettings}
          onSignOut={handleSignOut}
        />
      </div>
    </header>
  );
}

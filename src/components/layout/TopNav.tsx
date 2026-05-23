import { useEffect, useMemo, useRef, useState } from 'react';
import type { ElementType } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell, BookOpen, HelpCircle, Inbox, InboxIcon, Keyboard, LifeBuoy,
  Megaphone, Search, ShieldQuestion, UserCog, X,
} from 'lucide-react';
import { Badge, Button } from '@/components/ui';
import { ProfileDropdown } from '@/components/ui/ProfileDropdown';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface InboxItem {
  id: string;
  item_type: string;
  title: string;
  description?: string | null;
  employee_name?: string | null;
  status: string;
  priority: string;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  created_at?: string | null;
}

interface NotificationItem {
  id: string;
  title: string;
  message?: string | null;
  type: string;
  notification_type?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  is_read: boolean;
  link_url?: string | null;
  created_at?: string | null;
}

function normalizeRole(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return normalized === 'global_access' ? 'super_admin' : normalized;
}

function formatDateTime(value?: string | null) {
  if (!value) return 'Not recorded';
  return new Date(value).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function titleCase(value?: string | null) {
  return value ? value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) : 'Update';
}

function priorityVariant(priority?: string): 'olive' | 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (priority === 'critical') return 'error';
  if (priority === 'high') return 'warning';
  if (priority === 'low') return 'neutral';
  return 'olive';
}

function durationFromDescription(description?: string | null) {
  if (!description) return null;
  const match = description.match(/\(([^)]+)\)/);
  return match?.[1] || null;
}

export function TopNav() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [openPanel, setOpenPanel] = useState<'inbox' | 'notifications' | 'help' | null>(null);
  const [inboxItems, setInboxItems] = useState<InboxItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loadingInbox, setLoadingInbox] = useState(false);
  const [loadingNotifications, setLoadingNotifications] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-role': normalizeRole(user?.role),
    'x-user-email': user?.email || '',
    'x-user-name': user?.name || '',
  }), [user]);

  const loadInbox = async () => {
    if (!user) return;
    setLoadingInbox(true);
    try {
      const res = await fetch(`${API_BASE}/inbox`, { headers });
      const data = await res.json();
      setInboxItems(data.items || []);
    } catch {
      setInboxItems([]);
    } finally {
      setLoadingInbox(false);
    }
  };

  const loadNotifications = async () => {
    if (!user) return;
    setLoadingNotifications(true);
    try {
      const res = await fetch(`${API_BASE}/notifications`, { headers });
      const data = await res.json();
      setNotifications(data.notifications || []);
    } catch {
      setNotifications([]);
    } finally {
      setLoadingNotifications(false);
    }
  };

  useEffect(() => {
    loadInbox();
    loadNotifications();
  }, [headers]);

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setOpenPanel(null);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const markNotificationRead = async (notification: NotificationItem) => {
    if (!notification.is_read) {
      await fetch(`${API_BASE}/notifications/${notification.id}/read`, { method: 'PUT', headers }).catch(() => undefined);
      setNotifications((current) => current.map((item) => item.id === notification.id ? { ...item, is_read: true } : item));
    }
    if (notification.related_entity_type === 'announcement' || notification.link_url?.includes('/announcements/')) {
      navigate('/');
      setOpenPanel(null);
    }
  };

  const markAllRead = async () => {
    await fetch(`${API_BASE}/notifications/mark-all-read`, { method: 'PUT', headers }).catch(() => undefined);
    setNotifications((current) => current.map((item) => ({ ...item, is_read: true })));
  };

  const completeInboxItem = async (item: InboxItem) => {
    if (item.item_type === 'announcement_acknowledgment' && item.related_entity_id) {
      await fetch(`${API_BASE}/announcements/${item.related_entity_id}/acknowledge`, { method: 'POST', headers }).catch(() => undefined);
    } else if (!item.id.includes(':')) {
      await fetch(`${API_BASE}/inbox/${item.id}/complete`, { method: 'POST', headers }).catch(() => undefined);
    }
    loadInbox();
    loadNotifications();
  };

  const decideInboxItem = async (item: InboxItem, decision: 'approve' | 'reject') => {
    if (!item.related_entity_id) return;
    const entityPath = item.item_type === 'leave_request'
      ? 'leave-requests'
      : item.item_type === 'attendance_correction'
        ? 'attendance-corrections'
        : null;
    if (!entityPath) return;

    await fetch(`${API_BASE}/inbox/${entityPath}/${item.related_entity_id}/${decision}`, { method: 'POST', headers }).catch(() => undefined);
    loadInbox();
    loadNotifications();
  };

  const handleViewProfile = () => navigate('/profile');
  const handleAccountSettings = () => console.log('Navigate to account settings');
  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  const currentUser = user || {
    name: 'User',
    role: 'Employee',
    email: 'user@reknew.ai',
    initials: 'U',
    profileImageUrl: null,
  };
  const inboxCount = inboxItems.length;
  const notificationCount = notifications.filter((item) => !item.is_read).length;

  const IconButton = ({ type, Icon, badge }: { type: 'inbox' | 'notifications' | 'help'; Icon: ElementType; badge: number }) => (
    <button
      aria-label={type === 'inbox' ? 'Open action inbox' : type === 'notifications' ? 'Open notifications' : 'Open help menu'}
      onMouseDown={(event) => event.stopPropagation()}
      onClick={(event) => {
        event.stopPropagation();
        setOpenPanel((current) => current === type ? null : type);
      }}
      className={cn(
        'relative w-9 h-9 rounded-lg flex items-center justify-center text-gray-400 hover:bg-hover-bg hover:text-gray-600 transition-all',
        openPanel === type && 'bg-hover-bg text-olive'
      )}
    >
      <Icon size={18} />
      {badge > 0 && (
        <span className="absolute top-1 right-1 min-w-4 h-4 px-1 rounded-full bg-status-error text-white text-[9px] font-bold flex items-center justify-center">
          {badge > 9 ? '9+' : badge}
        </span>
      )}
    </button>
  );

  const EmptyState = ({
    Icon,
    title,
  }: {
    Icon: ElementType;
    title: string;
  }) => (
    <div className="px-4 py-5">
      <div className="flex min-h-[190px] flex-col items-center justify-center rounded-2xl border border-[#E5E7EB] bg-warm-bg/70 px-6 py-7 text-center shadow-sm">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-olive/10 text-olive">
          <Icon size={22} />
        </div>
        <div className="text-sm font-bold text-[#2F3437]">{title}</div>
      </div>
    </div>
  );

  const PanelHeader = ({ title, count }: { title: string; count: number }) => (
    <div className="flex items-center justify-between border-b border-[#E5E7EB] px-4 py-3">
      <div className="flex items-center gap-2">
        <div className="text-sm font-bold text-[#2F3437]">{title}</div>
        <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-olive/10 px-2 py-0.5 text-[11px] font-bold text-olive">
          {count}
        </span>
      </div>
      <button
        aria-label={`Close ${title}`}
        onClick={() => setOpenPanel(null)}
        className="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-hover-bg hover:text-[#2F3437]"
      >
        <X size={15} />
      </button>
    </div>
  );

  return (
    <header className="h-14 flex items-center justify-between px-7 bg-warm-card border-b border-[#E5E7EB] sticky top-0 z-40">
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

      <div className="flex items-center gap-3">
        <div ref={wrapperRef} className="flex items-center gap-2">
          <div className="relative">
            <IconButton type="inbox" Icon={Inbox} badge={inboxCount} />
            {openPanel === 'inbox' && (
              <div onMouseDown={(event) => event.stopPropagation()} className="absolute right-0 top-11 w-[390px] max-w-[calc(100vw-2rem)] rounded-2xl border border-[#E5E7EB] bg-warm-card shadow-card-lg z-50 overflow-hidden">
            <PanelHeader title="Inbox" count={inboxCount} />
            <div className="max-h-[70vh] overflow-y-auto p-2">
              {loadingInbox ? (
                <div className="py-8 text-center text-sm text-gray-400">Loading actions...</div>
              ) : inboxItems.length === 0 ? (
                <EmptyState
                  Icon={InboxIcon}
                  title="No pending actions"
                />
              ) : inboxItems.map((item) => (
                <div key={item.id} className="mb-2 rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-3 shadow-sm transition-colors hover:bg-hover-bg/60 last:mb-0">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-bold text-[#2F3437]">{item.title}</div>
                      <div className="mt-2 grid gap-1 text-[12px] text-gray-500">
                        <div><span className="font-semibold text-[#2F3437]">Employee:</span> {item.employee_name || titleCase(item.item_type)}</div>
                        <div><span className="font-semibold text-[#2F3437]">Date:</span> {formatDateTime(item.created_at)}</div>
                        {durationFromDescription(item.description) && (
                          <div><span className="font-semibold text-[#2F3437]">Duration:</span> {durationFromDescription(item.description)}</div>
                        )}
                        {!durationFromDescription(item.description) && item.description && (
                          <div className="line-clamp-2">{item.description}</div>
                        )}
                      </div>
                    </div>
                    <Badge variant={priorityVariant(item.priority)}>{titleCase(item.priority)}</Badge>
                  </div>
                  <div className="mt-3 flex justify-end gap-1.5">
                      <Button size="sm" variant="ghost" onClick={() => navigate('/')}>View</Button>
                      {item.item_type === 'announcement_acknowledgment' ? (
                        <Button size="sm" onClick={() => completeInboxItem(item)}>Mark as Read</Button>
                      ) : item.item_type === 'leave_request' || item.item_type === 'attendance_correction' ? (
                        <>
                          <Button size="sm" variant="soft" onClick={() => decideInboxItem(item, 'approve')}>Approve</Button>
                          <Button size="sm" variant="ghost" onClick={() => decideInboxItem(item, 'reject')}>Reject</Button>
                        </>
                      ) : (
                        <Button size="sm" variant="soft" onClick={() => completeInboxItem(item)}>Review</Button>
                      )}
                  </div>
                </div>
              ))}
            </div>
              </div>
            )}
          </div>

          <div className="relative">
            <IconButton type="notifications" Icon={Bell} badge={notificationCount} />
            {openPanel === 'notifications' && (
              <div onMouseDown={(event) => event.stopPropagation()} className="absolute right-0 top-11 w-[390px] max-w-[calc(100vw-2rem)] rounded-2xl border border-[#E5E7EB] bg-warm-card shadow-card-lg z-50 overflow-hidden">
            <PanelHeader title="Notifications" count={notificationCount} />
            {notificationCount > 0 && (
              <div className="border-b border-[#E5E7EB] px-4 py-2 text-right">
                <button onClick={markAllRead} className="text-[12px] font-semibold text-olive">Mark all as read</button>
              </div>
            )}
            <div className="max-h-[70vh] overflow-y-auto p-2">
              {loadingNotifications ? (
                <div className="py-8 text-center text-sm text-gray-400">Loading notifications...</div>
              ) : notifications.length === 0 ? (
                <EmptyState
                  Icon={Bell}
                  title="No new notifications"
                />
              ) : notifications.map((notification) => (
                <div key={notification.id} className="mb-2 rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-3 text-left shadow-sm transition-colors hover:bg-hover-bg/60 last:mb-0">
                  <div className="flex items-start gap-3">
                    <div className={cn('mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl', notification.is_read ? 'bg-gray-100 text-gray-400' : 'bg-olive/10 text-olive')}>
                      {notification.type === 'announcement' ? <Megaphone size={15} /> : <Bell size={15} />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <div className="text-[13px] font-bold text-[#2F3437] truncate">{notification.title}</div>
                        {!notification.is_read && <span className="h-2 w-2 rounded-full bg-olive shrink-0" />}
                      </div>
                      <div className="mt-1 text-[12px] text-gray-500 line-clamp-2">{notification.message || 'New update'}</div>
                      <div className="mt-1 text-[11px] text-gray-400">{formatDateTime(notification.created_at)}</div>
                    </div>
                  </div>
                  <div className="mt-3 flex justify-end gap-1.5">
                    <Button size="sm" variant="ghost" onClick={() => markNotificationRead(notification)}>View</Button>
                    {!notification.is_read && (
                      <Button size="sm" variant="soft" onClick={() => markNotificationRead(notification)}>Mark as Read</Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
              </div>
            )}
          </div>

          <div className="relative">
            <IconButton type="help" Icon={HelpCircle} badge={0} />
            {openPanel === 'help' && (
              <div onMouseDown={(event) => event.stopPropagation()} className="absolute right-0 top-11 w-[270px] max-w-[calc(100vw-2rem)] rounded-2xl border border-[#E5E7EB] bg-warm-card shadow-card-lg z-50 overflow-hidden p-2">
            {[
              { icon: LifeBuoy, label: 'Help Center' },
              { icon: BookOpen, label: 'Product Guide' },
              { icon: Keyboard, label: 'Keyboard Shortcuts' },
              { icon: ShieldQuestion, label: 'Report an Issue' },
              { icon: UserCog, label: 'Contact Admin' },
            ].map(({ icon: Icon, label }) => (
              <button key={label} onClick={() => setOpenPanel(null)} className="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[13px] font-semibold text-[#2F3437] hover:bg-hover-bg transition-colors">
                <Icon size={15} className="text-olive" />
                {label}
              </button>
            ))}
              </div>
            )}
          </div>
        </div>

        <div className="w-px h-6 bg-[#E5E7EB] mx-2" />
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

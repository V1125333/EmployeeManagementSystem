import { useEffect, useMemo, useRef, useState } from 'react';
import type { ElementType } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell, HelpCircle, Inbox, InboxIcon,
  Megaphone, Search, ShieldQuestion, UserCog, X,
} from 'lucide-react';
import { Badge, Button } from '@/components/ui';
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

interface SearchEmployeeResult {
  id: string;
  first_name: string;
  last_name: string;
  work_email: string;
  department?: string | null;
  designation?: string | null;
}

interface SearchDestination {
  label: string;
  description: string;
  path: string;
  keywords: string;
  roles: Array<'admin' | 'employee' | 'manager' | 'all'>;
}

const searchDestinations: SearchDestination[] = [
  { label: 'Dashboard', description: 'Workforce hub and company overview', path: '/dashboard', keywords: 'dashboard workforce hub kpi overview birthdays anniversary', roles: ['admin'] },
  { label: 'Employees', description: 'Search and manage employee records', path: '/employees', keywords: 'employees people directory department role manager skills', roles: ['admin'] },
  { label: 'Time Off & Attendance', description: 'Leave, attendance, corrections, timesheets, reports', path: '/time-off', keywords: 'time off attendance leave balances corrections timesheets reports policies', roles: ['admin'] },
  { label: 'Onboarding Center', description: 'Employee onboarding workflows', path: '/onboarding', keywords: 'onboarding setup new employee trainee', roles: ['admin'] },
  { label: 'Client Onboarding', description: 'Client onboarding workstreams', path: '/client-onboarding', keywords: 'client onboarding customer implementation', roles: ['admin'] },
  { label: 'Projects', description: 'Project registry and assignments', path: '/projects', keywords: 'projects assignments allocation client delivery', roles: ['all'] },
  { label: 'Team Allocation', description: 'Project and team allocations', path: '/team-allocation', keywords: 'team allocation project skills staffing resource', roles: ['admin'] },
  { label: 'Bench & Availability', description: 'Resource availability and bench capacity', path: '/bench', keywords: 'bench availability allocation utilization capacity resources', roles: ['admin'] },
  { label: 'Staffing Requests', description: 'Resource demand requests and candidate matching', path: '/staffing-requests', keywords: 'staffing requests resource demand candidates hiring manager headcount', roles: ['admin', 'manager'] },
  { label: 'Workforce Forecasting', description: 'Forecast employee availability and bench risk', path: '/forecasting', keywords: 'forecasting workforce bench risk future availability allocations', roles: ['admin', 'manager'] },
  { label: 'Assets & Access', description: 'Hardware, software, and access', path: '/assets', keywords: 'assets access laptop software license permissions', roles: ['admin'] },
  { label: 'Policies', description: 'Policy management', path: '/admin/policies', keywords: 'policies leave attendance rules configuration', roles: ['admin'] },
  { label: 'Certificates', description: 'Generate employee certificates', path: '/admin/certificates', keywords: 'certificates documents letters', roles: ['admin'] },
  { label: 'HR Documents', description: 'HR document templates and files', path: '/admin/hr-documents', keywords: 'hr documents files templates', roles: ['admin'] },
  { label: 'My Dashboard', description: 'Employee daily summary', path: '/employee', keywords: 'employee dashboard attendance leave timesheet', roles: ['employee'] },
  { label: 'Apply Leave', description: 'Create and track leave requests', path: '/employee/apply-leave', keywords: 'apply leave balance vacation sick earned casual', roles: ['employee'] },
  { label: 'Timesheets', description: 'Weekly project time entry', path: '/employee/timesheets', keywords: 'timesheet time project poc break overtime', roles: ['employee'] },
  { label: 'Check In / Out', description: 'Daily attendance punch', path: '/employee/check-in', keywords: 'check in checkout attendance clock', roles: ['employee'] },
  { label: 'Documents', description: 'Employee documents', path: '/employee/documents', keywords: 'documents files certificate', roles: ['employee'] },
];

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

function canReviewApprovals(role?: string) {
  const normalized = normalizeRole(role);
  return ['manager', 'super_admin', 'admin', 'hr_admin'].includes(normalized);
}

function isAdminRole(role?: string) {
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalizeRole(role));
}

export function TopNav() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [openPanel, setOpenPanel] = useState<'inbox' | 'notifications' | 'help' | null>(null);
  const [inboxItems, setInboxItems] = useState<InboxItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadNotificationCount, setUnreadNotificationCount] = useState(0);
  const [loadingInbox, setLoadingInbox] = useState(false);
  const [loadingNotifications, setLoadingNotifications] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [employeeResults, setEmployeeResults] = useState<SearchEmployeeResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);

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
      const [res, countRes] = await Promise.all([
        fetch(`${API_BASE}/notifications?unread_only=true&limit=6`, { headers }),
        fetch(`${API_BASE}/notifications/unread-count`, { headers }),
      ]);
      const data = await res.json();
      const countData = await countRes.json().catch(() => null);
      setNotifications(data.notifications || []);
      setUnreadNotificationCount(countData?.count ?? (data.notifications || []).length);
    } catch {
      setNotifications([]);
      setUnreadNotificationCount(0);
    } finally {
      setLoadingNotifications(false);
    }
  };

  useEffect(() => {
    loadInbox();
    loadNotifications();
  }, [headers]);

  useEffect(() => {
    const refreshActions = () => {
      loadInbox();
      loadNotifications();
    };
    window.addEventListener('reknew:actions-updated', refreshActions);
    return () => window.removeEventListener('reknew:actions-updated', refreshActions);
  }, [headers]);

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!wrapperRef.current?.contains(target)) {
        setOpenPanel(null);
      }
      if (!searchRef.current?.contains(target)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const visibleDestinations = useMemo(() => {
    const audience = isAdminRole(user?.role) ? 'admin' : normalizeRole(user?.role) === 'manager' ? 'manager' : 'employee';
    const term = searchQuery.trim().toLowerCase();
    return searchDestinations
      .filter((item) => item.roles.includes('all') || item.roles.includes(audience))
      .filter((item) => {
        if (!term) return true;
        return `${item.label} ${item.description} ${item.keywords}`.toLowerCase().includes(term);
      })
      .slice(0, 5);
  }, [headers, searchQuery, user?.role]);

  useEffect(() => {
    const term = searchQuery.trim();
    if (!isAdminRole(user?.role) || term.length < 2) {
      setEmployeeResults([]);
      setSearchLoading(false);
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearchLoading(true);
      try {
        const params = new URLSearchParams({ search: term, per_page: '5', page: '1' });
        const res = await fetch(`${API_BASE}/employees/?${params.toString()}`, { signal: controller.signal, headers });
        const data = await res.json();
        setEmployeeResults(data.employees || []);
      } catch (error) {
        if (!controller.signal.aborted) setEmployeeResults([]);
      } finally {
        if (!controller.signal.aborted) setSearchLoading(false);
      }
    }, 250);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [searchQuery, user?.role]);

  const markNotificationRead = async (notification: NotificationItem) => {
    if (!notification.is_read) {
      await fetch(`${API_BASE}/notifications/${notification.id}/read`, { method: 'PUT', headers }).catch(() => undefined);
      setNotifications((current) => current.filter((item) => item.id !== notification.id));
      setUnreadNotificationCount((current) => Math.max(0, current - 1));
    }
  };

  const notificationTargetPath = (notification: NotificationItem) => {
    const title = `${notification.title || ''} ${notification.message || ''}`.toLowerCase();
    const type = `${notification.type || ''} ${notification.notification_type || ''} ${notification.related_entity_type || ''}`.toLowerCase();

    if (type.includes('announcement') || notification.link_url?.includes('/announcements/')) {
      return '/';
    }

    if (type.includes('timesheet') || title.includes('timesheet')) {
      return canReviewApprovals(user?.role) && (title.includes('submitted') || title.includes('recalled'))
        ? '/employee/approvals'
        : '/employee/timesheets';
    }

    if (type.includes('leave') || title.includes('leave')) {
      return canReviewApprovals(user?.role) && (title.includes('request') || title.includes('submitted'))
        ? '/employee/approvals'
        : '/employee/apply-leave';
    }

    if (notification.link_url?.startsWith('/')) {
      return notification.link_url;
    }

    return '/notifications';
  };

  const viewNotification = async (notification: NotificationItem) => {
    await markNotificationRead(notification);
    navigate(notificationTargetPath(notification));
    setOpenPanel(null);
  };

  const inboxTargetPath = (item: InboxItem) => {
    if (item.item_type === 'leave_request' || item.related_entity_type === 'leave_request') return '/employee/approvals';
    if (item.item_type === 'attendance_correction' || item.related_entity_type === 'attendance_correction') return '/employee/approvals';
    if (item.item_type.includes('timesheet') || item.related_entity_type === 'timesheet') return '/employee/approvals';
    if (item.item_type === 'announcement_acknowledgment' || item.related_entity_type === 'announcement') return '/';
    if (item.item_type === 'profile_update') return '/profile';
    return '/notifications';
  };

  const viewInboxItem = (item: InboxItem) => {
    navigate(inboxTargetPath(item));
    setOpenPanel(null);
  };

  const markAllRead = async () => {
    await fetch(`${API_BASE}/notifications/mark-all-read`, { method: 'PUT', headers }).catch(() => undefined);
    setNotifications([]);
    setUnreadNotificationCount(0);
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

  const closeSearch = () => {
    setSearchOpen(false);
    setSearchQuery('');
  };

  const goToPath = (path: string) => {
    navigate(path);
    closeSearch();
  };

  const employeeName = (employee: SearchEmployeeResult) => `${employee.first_name} ${employee.last_name}`.trim();

  const goToEmployeeSearch = (employee?: SearchEmployeeResult) => {
    const term = employee ? (employeeName(employee) || employee.work_email) : searchQuery.trim();
    navigate(`/employees?search=${encodeURIComponent(term)}`);
    closeSearch();
  };

  const submitSearch = () => {
    const firstEmployee = employeeResults[0];
    const firstDestination = visibleDestinations[0];
    if (isAdminRole(user?.role) && firstEmployee) {
      goToEmployeeSearch(firstEmployee);
      return;
    }
    if (firstDestination) {
      goToPath(firstDestination.path);
      return;
    }
    if (isAdminRole(user?.role) && searchQuery.trim()) {
      goToEmployeeSearch();
    }
  };

  const inboxCount = inboxItems.length;
  const notificationCount = unreadNotificationCount;
  const notificationPreview = notifications.slice(0, 5);
  const hiddenNotificationCount = Math.max(0, notificationCount - notificationPreview.length);

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
      <div className="flex min-h-[190px] flex-col items-center justify-center rounded-2xl border border-[var(--color-border)] bg-warm-bg/70 px-6 py-7 text-center shadow-sm">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-olive/10 text-olive">
          <Icon size={22} />
        </div>
        <div className="text-sm font-bold text-[var(--color-brand-navy)]">{title}</div>
      </div>
    </div>
  );

  const PanelHeader = ({ title, count }: { title: string; count: number }) => (
    <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
      <div className="flex items-center gap-2">
        <div className="text-sm font-bold text-[var(--color-brand-navy)]">{title}</div>
        <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-olive/10 px-2 py-0.5 text-[11px] font-bold text-olive">
          {count}
        </span>
      </div>
      <button
        aria-label={`Close ${title}`}
        onClick={() => setOpenPanel(null)}
        className="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-hover-bg hover:text-[var(--color-brand-navy)]"
      >
        <X size={15} />
      </button>
    </div>
  );

  return (
    <header className="h-14 flex items-center justify-between px-7 bg-warm-card border-b border-[var(--color-border)] sticky top-0 z-40">
      <div ref={searchRef} className="relative flex items-center">
        <div className={cn('flex items-center gap-2 bg-warm-bg border rounded-btn px-3.5 py-[7px] w-[340px] transition-colors', searchOpen ? 'border-olive shadow-sm' : 'border-[var(--color-border)]')}>
          <Search size={16} className="text-gray-400 shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onFocus={() => setSearchOpen(true)}
            onChange={(event) => {
              setSearchQuery(event.target.value);
              setSearchOpen(true);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') submitSearch();
              if (event.key === 'Escape') setSearchOpen(false);
            }}
            placeholder="Search employees, projects, skills..."
            className="bg-transparent border-none outline-none text-[13px] text-[var(--color-brand-navy)] placeholder:text-gray-400 w-full font-sans"
          />
          {searchQuery && (
            <button aria-label="Clear search" onClick={closeSearch} className="text-gray-400 hover:text-gray-600">
              <X size={14} />
            </button>
          )}
        </div>
        {searchOpen && (
          <div className="absolute left-0 top-12 z-50 w-[460px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-[var(--color-border)] bg-warm-card shadow-card-lg">
            <div className="border-b border-[var(--color-border)] px-4 py-3">
              <div className="text-xs font-bold uppercase tracking-wide text-gray-400">Global Search</div>
              <div className="mt-1 text-[12px] text-gray-500">Search employees and jump to key workspace pages.</div>
            </div>
            <div className="max-h-[70vh] overflow-y-auto p-2">
              {isAdminRole(user?.role) && searchQuery.trim().length >= 2 && (
                <div className="mb-2">
                  <div className="px-2 pb-1 pt-1 text-[11px] font-bold uppercase tracking-wide text-gray-400">Employees</div>
                  {searchLoading ? (
                    <div className="rounded-xl px-3 py-3 text-sm text-gray-400">Searching employees...</div>
                  ) : employeeResults.length ? employeeResults.map((employee) => (
                    <button
                      key={employee.id}
                      onClick={() => goToEmployeeSearch(employee)}
                      className="mb-1 flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-hover-bg"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-[13px] font-bold text-[var(--color-brand-navy)]">{employeeName(employee)}</div>
                        <div className="truncate text-[12px] text-gray-500">{employee.work_email}</div>
                      </div>
                      <div className="shrink-0 text-right text-[11px] text-gray-400">
                        <div>{employee.department || 'No department'}</div>
                        <div>{employee.designation || 'No designation'}</div>
                      </div>
                    </button>
                  )) : (
                    <div className="rounded-xl px-3 py-3 text-sm text-gray-400">No matching employees.</div>
                  )}
                </div>
              )}

              <div>
                <div className="px-2 pb-1 pt-1 text-[11px] font-bold uppercase tracking-wide text-gray-400">Pages</div>
                {visibleDestinations.length ? visibleDestinations.map((item) => (
                  <button
                    key={item.path}
                    onClick={() => goToPath(item.path)}
                    className="mb-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-hover-bg"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-olive/10 text-olive">
                      <Search size={14} />
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-[13px] font-bold text-[var(--color-brand-navy)]">{item.label}</div>
                      <div className="truncate text-[12px] text-gray-500">{item.description}</div>
                    </div>
                  </button>
                )) : (
                  <div className="rounded-xl px-3 py-3 text-sm text-gray-400">No matching pages.</div>
                )}
              </div>
            </div>
            <div className="border-t border-[var(--color-border)] bg-warm-bg px-4 py-2 text-[11px] text-gray-400">
              Press Enter to open the best match.
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div ref={wrapperRef} className="flex items-center gap-2">
          <div className="relative">
            <IconButton type="inbox" Icon={Inbox} badge={inboxCount} />
            {openPanel === 'inbox' && (
              <div onMouseDown={(event) => event.stopPropagation()} className="absolute right-0 top-11 w-[390px] max-w-[calc(100vw-2rem)] rounded-2xl border border-[var(--color-border)] bg-warm-card shadow-card-lg z-50 overflow-hidden">
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
                <div key={item.id} className="mb-2 rounded-xl border border-[var(--color-border)] bg-white px-3.5 py-3 shadow-sm transition-colors hover:bg-hover-bg/60 last:mb-0">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-bold text-[var(--color-brand-navy)]">{item.title}</div>
                      <div className="mt-2 grid gap-1 text-[12px] text-gray-500">
                        <div><span className="font-semibold text-[var(--color-brand-navy)]">Employee:</span> {item.employee_name || titleCase(item.item_type)}</div>
                        <div><span className="font-semibold text-[var(--color-brand-navy)]">Date:</span> {formatDateTime(item.created_at)}</div>
                        {durationFromDescription(item.description) && (
                          <div><span className="font-semibold text-[var(--color-brand-navy)]">Duration:</span> {durationFromDescription(item.description)}</div>
                        )}
                        {!durationFromDescription(item.description) && item.description && (
                          <div className="line-clamp-2">{item.description}</div>
                        )}
                      </div>
                    </div>
                    <Badge variant={priorityVariant(item.priority)}>{titleCase(item.priority)}</Badge>
                  </div>
                  <div className="mt-3 flex justify-end gap-1.5">
                      <Button size="sm" variant="ghost" onClick={() => viewInboxItem(item)}>View</Button>
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
              <div onMouseDown={(event) => event.stopPropagation()} className="absolute right-0 top-11 w-[390px] max-w-[calc(100vw-2rem)] rounded-2xl border border-[var(--color-border)] bg-warm-card shadow-card-lg z-50 overflow-hidden">
            <PanelHeader title="Notifications" count={notificationCount} />
            {notificationCount > 0 && (
              <div className="border-b border-[var(--color-border)] px-4 py-2 text-right">
                <button onClick={markAllRead} className="text-[12px] font-semibold text-olive">Mark all as read</button>
              </div>
            )}
            <div className="max-h-[70vh] overflow-y-auto p-2">
              {loadingNotifications ? (
                <div className="py-8 text-center text-sm text-gray-400">Loading notifications...</div>
              ) : notificationCount === 0 ? (
                <EmptyState
                  Icon={Bell}
                  title="You are all caught up"
                />
              ) : (
                <>
                  {notificationPreview.map((notification) => (
                    <div key={notification.id} className="mb-2 rounded-xl border border-[var(--color-border)] bg-white px-3.5 py-3 text-left shadow-sm transition-colors hover:bg-hover-bg/60 last:mb-0">
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-olive/10 text-olive">
                          {notification.type === 'announcement' ? <Megaphone size={15} /> : <Bell size={15} />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <div className="truncate text-[13px] font-bold text-[var(--color-brand-navy)]">{notification.title}</div>
                            <span className="h-2 w-2 shrink-0 rounded-full bg-olive" />
                          </div>
                          <div className="mt-1 line-clamp-2 text-[12px] text-gray-500">{notification.message || 'New update'}</div>
                          <div className="mt-1 text-[11px] text-gray-400">{formatDateTime(notification.created_at)}</div>
                        </div>
                      </div>
                      <div className="mt-3 flex justify-end gap-1.5">
                        <Button size="sm" variant="ghost" onClick={() => viewNotification(notification)}>View</Button>
                        <Button size="sm" variant="soft" onClick={() => markNotificationRead(notification)}>Mark as Read</Button>
                      </div>
                    </div>
                  ))}
                  <div className="mt-2 flex items-center justify-between gap-3 rounded-xl bg-warm-bg px-3.5 py-2.5 text-xs text-gray-500">
                    <span>{hiddenNotificationCount > 0 ? `${hiddenNotificationCount} more unread notification${hiddenNotificationCount === 1 ? '' : 's'}` : 'Showing latest unread notifications'}</span>
                    <button
                      onClick={() => {
                        navigate('/notifications');
                        setOpenPanel(null);
                      }}
                      className="font-bold text-olive hover:underline"
                    >
                      View all
                    </button>
                  </div>
                </>
              )}
            </div>
              </div>
            )}
          </div>

          <div className="relative">
            <IconButton type="help" Icon={HelpCircle} badge={0} />
            {openPanel === 'help' && (
              <div onMouseDown={(event) => event.stopPropagation()} className="absolute right-0 top-11 w-[270px] max-w-[calc(100vw-2rem)] rounded-2xl border border-[var(--color-border)] bg-warm-card shadow-card-lg z-50 overflow-hidden p-2">
                {[
                  { icon: ShieldQuestion, label: 'Report an Issue', path: '/requests?new=application_issue' },
                  { icon: UserCog, label: 'Contact HR', path: '/requests?new=application_issue' },
                ].map(({ icon: Icon, label, path }) => (
                  <button
                    key={label}
                    onClick={() => {
                      navigate(path);
                      setOpenPanel(null);
                    }}
                    className="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[13px] font-semibold text-[var(--color-brand-navy)] hover:bg-hover-bg transition-colors"
                  >
                    <Icon size={15} className="text-olive" />
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </header>
  );
}

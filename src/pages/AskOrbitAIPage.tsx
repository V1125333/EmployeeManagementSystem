import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Bot, CalendarPlus, CheckCircle2, Clock3, Eraser, Send,
} from 'lucide-react';
import { OrbitAIGlyph } from '@/components/ai/OrbitAIGlyph';
import { Button } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';
import { AIChatResponseContent } from '@/components/ai/AIChatResponseContent';
import { AIAPIError, sendAIChat, type AIChatResponse } from '@/services/aiApi';

export type ChatMessage = {
  id: string;
  role: 'agent' | 'user';
  text: string;
  actions?: { label: string; path: string; icon?: React.ReactNode }[];
  result?: AIChatResponse['result'];
  correlationId?: string;
  status?: AIChatResponse['status'];
};

type LeaveBalanceItem = {
  name?: string;
  type?: string;
  code?: string;
  used?: number | string;
  pending?: number | string;
  available?: number | string;
  effective_available?: number | string;
  total?: number | string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const prompts = [
  'What is my casual leave balance?',
  'Show all my leave balances',
  'How many sick leave days do I have?',
];

function isAdminRole(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalized);
}

function authHeaders(user?: { id?: string; email?: string; role?: string }) {
  return {
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': user?.role || '',
  };
}

const leaveTypeAliases: Record<string, string[]> = {
  CL: ['casual', 'casual leave', 'cl'],
  SL: ['sick', 'sick leave', 'medical', 'sl'],
  EL: ['earned', 'earned leave', 'el'],
  PL: ['paternity', 'paternity leave', 'pl'],
  CO: ['compensatory', 'comp off', 'compensatory off', 'co'],
  LOP: ['loss of pay', 'lop', 'loss pay', 'unpaid'],
  BL: ['bereavement', 'bereavement leave', 'bl'],
  FL: ['floating', 'floating holiday', 'fl'],
  OH: ['optional', 'optional holiday', 'oh'],
};

const genericLeaveWords = new Set([
  'leave',
  'leaves',
  'holiday',
  'holidays',
  'balance',
  'available',
  'availability',
  'how',
  'many',
  'much',
  'do',
  'i',
  'have',
  'my',
  'current',
  'show',
  'what',
  'is',
  'the',
  'of',
  'days',
  'day',
]);

function hasTerm(text: string, term: string) {
  const normalizedTerm = term.toLowerCase().trim();
  if (!normalizedTerm) {
    return false;
  }
  return new RegExp(`(^|[^a-z0-9])${normalizedTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}([^a-z0-9]|$)`).test(text);
}

function mentionsLeaveType(text: string) {
  return Object.values(leaveTypeAliases).some((aliases) => aliases.some((alias) => hasTerm(text, alias)));
}

function isLeaveBalanceQuestion(text: string) {
  if (text.includes('balance') || text.includes('available') || text.includes('how many')) {
    return true;
  }

  const isFollowUp = text.includes('what about') || text.includes('how about') || text.includes('and ');
  const asksOwnership = text.includes('do i have') || text.includes('left') || text.includes('remaining');
  return mentionsLeaveType(text) && (isFollowUp || asksOwnership);
}

function formatLeaveValue(value: number | string | undefined) {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }

  if (typeof value === 'string' && Number.isNaN(Number(value))) {
    return value;
  }

  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return undefined;
  }

  return Number.isInteger(numericValue) ? String(numericValue) : `${numericValue.toFixed(1)}`;
}

function getLeaveName(item: LeaveBalanceItem) {
  return item.name || item.type || item.code || 'Leave';
}

function findRequestedLeaveType(message: string, balances: LeaveBalanceItem[]) {
  const text = message.toLowerCase();

  const byCode = balances.find((item) => item.code && hasTerm(text, item.code.toLowerCase()));
  if (byCode) {
    return byCode;
  }

  const byAlias = balances.find((item) => {
    const code = (item.code || '').toUpperCase();
    return code && leaveTypeAliases[code]?.some((alias) => hasTerm(text, alias));
  });
  if (byAlias) {
    return byAlias;
  }

  return balances.find((item) => {
    const leaveName = getLeaveName(item).toLowerCase();
    const searchableTokens = leaveName
      .split(/[^a-z0-9]+/)
      .filter((token) => token && !genericLeaveWords.has(token));
    return searchableTokens.some((token) => hasTerm(text, token));
  });
}

function formatLeaveLine(item: LeaveBalanceItem) {
  const leaveName = getLeaveName(item);
  const availableValue = formatLeaveValue(item.effective_available ?? item.available);
  if (!availableValue) {
    return null;
  }
  const code = item.code ? ` (${item.code})` : '';
  const pendingValue = formatLeaveValue(item.pending);
  const usedValue = formatLeaveValue(item.used);
  const totalValue = formatLeaveValue(item.total);
  const total = totalValue ? ` of ${totalValue} total` : '';
  const pending = Number(item.pending || 0) > 0 ? `, ${pendingValue} pending` : '';
  const used = usedValue ? `, ${usedValue} used` : '';
  return `${leaveName}${code}: ${availableValue} available${total}${pending}${used}`;
}

function formatSpecificLeaveBalanceReply(item: LeaveBalanceItem) {
  const leaveLine = formatLeaveLine(item);
  if (!leaveLine) {
    return `I found ${getLeaveName(item)}, but could not read its balance value from the API response.`;
  }
  return leaveLine;
}

function formatLeaveBalanceReply(
  data: { balances?: LeaveBalanceItem[]; requests?: { status?: string }[] },
  message: string,
) {
  const balances = data.balances || [];
  if (balances.length === 0) {
    return 'I could not find leave balance records for your profile.';
  }

  const requestedLeaveType = findRequestedLeaveType(message, balances);
  if (requestedLeaveType) {
    return formatSpecificLeaveBalanceReply(requestedLeaveType);
  }

  const visibleBalances = balances
    .map(formatLeaveLine)
    .filter((line): line is string => Boolean(line));

  if (visibleBalances.length === 0) {
    return 'I found your leave summary, but could not read the balance values from the API response.';
  }

  const pendingRequests = (data.requests || []).filter((request) => request.status === 'pending').length;
  return [
    'Here is your current leave balance:',
    '',
    ...visibleBalances.map((line) => `- ${line}`),
    '',
    pendingRequests > 0
      ? `You also have ${pendingRequests} pending leave request${pendingRequests === 1 ? '' : 's'}.`
      : 'You do not have pending leave requests right now.',
  ].join('\n');
}

async function getLeaveBalanceReply(
  message: string,
  user?: { id?: string; email?: string; role?: string },
): Promise<ChatMessage> {
  const admin = isAdminRole(user?.role);
  try {
    const response = await fetch(`${API_BASE}/leaves/me/summary`, {
      headers: authHeaders(user),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.message || 'Unable to fetch leave balance.');
    }

    return {
      id: crypto.randomUUID(),
      role: 'agent',
      text: formatLeaveBalanceReply(data, message),
      actions: [
        { label: admin ? 'Open Time Off' : 'Open Apply Leave', path: admin ? '/time-off' : '/employee/apply-leave', icon: <CalendarPlus size={15} /> },
      ],
    };
  } catch (error) {
    return {
      id: crypto.randomUUID(),
      role: 'agent',
      text: error instanceof Error
        ? `I could not fetch your leave balance right now. ${error.message}`
        : 'I could not fetch your leave balance right now.',
      actions: [
        { label: admin ? 'Open Time Off' : 'Open Apply Leave', path: admin ? '/time-off' : '/employee/apply-leave', icon: <CalendarPlus size={15} /> },
      ],
    };
  }
}

export async function getAgentReply(message: string, user?: { id?: string; email?: string; role?: string }): Promise<ChatMessage> {
  const text = message.toLowerCase().trim();
  const admin = isAdminRole(user?.role);
  const leavePath = admin ? '/time-off' : '/employee/apply-leave';
  const timesheetPath = admin ? '/time-off' : '/employee/timesheets';
  const requestsPath = admin ? '/staffing-requests' : '/employee/requests';

  if (/^(hi|hello|hey|good morning|good afternoon|good evening)[!. ]*$/.test(text)) {
    const firstName = user && 'name' in user
      ? String((user as { name?: string }).name || '').split(' ')[0]
      : '';
    return {
      id: crypto.randomUUID(),
      role: 'agent',
      text: `Hello${firstName ? `, ${firstName}` : ''}! How can I help you today? You can ask me about leave, timesheets, attendance, requests, projects, or your documents.`,
    };
  }

  if (isLeaveBalanceQuestion(text)) {
    return getLeaveBalanceReply(message, user);
  }

  if (text.includes('leave') && (text.includes('apply') || text.includes('request'))) {
    return {
      id: crypto.randomUUID(),
      role: 'agent',
      text: 'I can help you start a leave request. I will open Apply Leave, where you can confirm the leave type, dates, reason, and submit it to your reporting manager.',
      actions: [
        { label: admin ? 'Open Time Off' : 'Open Apply Leave', path: leavePath, icon: <CalendarPlus size={15} /> },
      ],
    };
  }

  if (text.includes('timesheet') || text.includes('time sheet')) {
    return {
      id: crypto.randomUUID(),
      role: 'agent',
      text: 'I can help with timesheets. Open the Timesheets page, review your work blocks, save hours, and submit the week for manager approval.',
      actions: [
        { label: admin ? 'Open Time Off' : 'Open Timesheets', path: timesheetPath, icon: <Clock3 size={15} /> },
      ],
    };
  }

  if (text.includes('payslip') || text.includes('document') || text.includes('certificate')) {
    return {
      id: crypto.randomUUID(),
      role: 'agent',
      text: 'I can take you to Documents, where your latest payslips, personal files, policies, and certificates are grouped into folders.',
      actions: [
        { label: 'Open Documents', path: admin ? '/hr-documents' : '/employee/documents', icon: <CheckCircle2 size={15} /> },
      ],
    };
  }

  if (text.includes('needs me today') || text.includes('what needs me')) {
    return {
      id: crypto.randomUUID(),
      role: 'agent',
      text: 'Your dashboard briefing collects the items that need attention today, including timesheet deadlines, pending requests, manager approvals, training, and document actions.',
      actions: [
        { label: 'Open Dashboard', path: admin ? '/' : '/employee', icon: <CheckCircle2 size={15} /> },
      ],
    };
  }

  if (text.includes('pending') || text.includes('request') || text.includes('status')) {
    return {
      id: crypto.randomUUID(),
      role: 'agent',
      text: 'I can show your requests page, where pending, approved, rejected, and cancelled requests are tracked with their current owner and status.',
      actions: [
        { label: admin ? 'Open Staffing Requests' : 'Open Requests', path: requestsPath, icon: <CheckCircle2 size={15} /> },
      ],
    };
  }

  return {
    id: crypto.randomUUID(),
    role: 'agent',
    text: 'I can help with HR actions like applying leave, checking balances, reviewing timesheets, finding requests, and opening the right Reknew Orbit page. Try asking: “Apply sick leave today” or “Help me submit my timesheet.”',
  };
}

export function AskOrbitAIPage({
  embedded = false,
  contextualPrompts = [],
}: {
  embedded?: boolean;
  contextualPrompts?: string[];
} = {}) {
  const navigate = useNavigate();
  const { user, accessToken } = useAuth();
  const [searchParams] = useSearchParams();
  const initialPromptRef = useRef(searchParams.get('prompt') || '');
  const [input, setInput] = useState(() => searchParams.get('prompt') || '');
  const [sending, setSending] = useState(false);
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'agent',
      text: 'Hi, I am Ask Orbit AI. In this first secure version, I can check your own leave balance.',
    },
  ]);

  const displayName = useMemo(() => user?.name?.split(' ')[0] || 'there', [user?.name]);
  const hasOnlyWelcome = messages.length === 1 && messages[0]?.id === 'welcome';
  const visiblePrompts = useMemo(
    () => [...new Set([...contextualPrompts, ...prompts])].slice(0, embedded ? 4 : 6),
    [contextualPrompts, embedded],
  );

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      text: trimmed,
    };
    setMessages((current) => [...current, userMessage]);
    setInput('');
    setSending(true);
    try {
      const response = await sendAIChat(trimmed, accessToken, conversationId);
      setConversationId(response.conversation_id);
      setMessages((current) => [...current, {
        id: crypto.randomUUID(),
        role: 'agent',
        text: response.message.content,
        result: response.result,
        correlationId: response.correlation_id,
        status: response.status,
      }]);
    } catch (error) {
      const apiError = error instanceof AIAPIError ? error : null;
      setMessages((current) => [...current, {
        id: crypto.randomUUID(),
        role: 'agent',
        text: apiError?.message || 'Orbit AI could not answer right now.',
        correlationId: apiError?.correlationId,
      }]);
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    if (!initialPromptRef.current) return;
    initialPromptRef.current = '';
    void sendMessage();
  }, []);

  const clearChat = () => {
    setMessages([
      {
        id: 'welcome',
        role: 'agent',
        text: 'Chat cleared. What would you like Ask Orbit AI to help with next?',
      },
    ]);
    setConversationId(undefined);
  };

  return (
    <div className={cn(
      'flex min-h-0 flex-col overflow-hidden',
      embedded
        ? 'h-full pb-[72px]'
        : '-mx-[var(--layout-main-padding-x)] -my-[var(--layout-main-padding-y)] h-[calc(100vh-3.5rem)]',
    )}>
      <section className="flex min-h-0 flex-1 flex-col overflow-hidden bg-white">
        <div className="border-b border-[var(--color-border)] px-5 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-[#199a8e] to-[#12433f] shadow-[0_4px_12px_rgba(18,67,63,.22)]">
                <OrbitAIGlyph className="orbit-ai-glyph" />
              </div>
              <div>
                <div className="text-sm font-bold text-[var(--color-brand-navy)]">Ask Orbit AI</div>
                <div className="text-xs text-gray-500">Hi {displayName}, ask a question or launch an HR action.</div>
              </div>
            </div>
            <div>
              <Button variant="ghost" icon={<Eraser size={15} />} onClick={clearChat}>
                Clear
              </Button>
            </div>
          </div>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto bg-[var(--color-brand-canvas)] px-5 py-5">
          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                'flex',
                message.role === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              <div
                className={cn(
                    'max-w-[840px] whitespace-pre-line rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm',
                  message.role === 'user'
                    ? 'bg-[var(--color-brand-navy)] text-white'
                    : 'border border-[var(--color-border)] bg-white text-[var(--color-brand-navy)]'
                )}
              >
                {message.role === 'agent' && (
                  <div className="mb-1 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-accent">
                    <Bot size={13} />
                    Ask Orbit AI
                  </div>
                )}
                <AIChatResponseContent
                  text={message.text}
                  status={message.status}
                  result={message.result}
                  correlationId={message.correlationId}
                />
                {message.actions && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {message.actions.map((action) => (
                      <Button
                        key={action.path}
                        size="sm"
                        variant="soft"
                        icon={action.icon}
                        onClick={() => navigate(action.path)}
                      >
                        {action.label}
                      </Button>
            ))}
          {sending && (
            <div className="flex justify-start">
              <div className="rounded-2xl border border-[var(--color-border)] bg-white px-4 py-3 text-sm font-medium text-gray-500 shadow-sm">
                <AIChatResponseContent loading />
              </div>
            </div>
          )}
        </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-[var(--color-border)] bg-white p-4">
          {hasOnlyWelcome && (
            <div className="mb-3 flex flex-wrap gap-2">
              {visiblePrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setInput(prompt)}
                  className="rounded-full border border-[var(--color-border)] bg-[var(--color-bg-hover)] px-3 py-1.5 text-xs font-semibold text-[var(--color-brand-navy)] transition hover:border-accent-mid hover:bg-accent-light"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
          <div className="flex gap-3">
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask Orbit AI to check your leave balance..."
              className="min-h-12 flex-1 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-hover)] px-4 text-sm font-medium text-[var(--color-brand-navy)] outline-none transition focus:border-accent-mid focus:ring-2 focus:ring-accent-light"
            />
            <Button icon={<Send size={16} />} onClick={sendMessage} disabled={sending}>
              {sending ? 'Sending' : 'Send'}
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

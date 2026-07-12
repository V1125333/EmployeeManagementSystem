import type React from 'react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bot, CalendarPlus, CheckCircle2, Clock3, Eraser, Send,
} from 'lucide-react';
import { Button } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

type ChatMessage = {
  id: string;
  role: 'agent' | 'user';
  text: string;
  actions?: { label: string; path: string; icon?: React.ReactNode }[];
};

const prompts = [
  'Apply casual leave for tomorrow',
  'What is my leave balance?',
  'Help me submit this week timesheet',
  'Show pending requests',
];

function isAdminRole(role?: string) {
  const normalized = (role || '').toLowerCase().replace(/\s+/g, '_');
  return ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(normalized);
}

function getAgentReply(message: string, userRole?: string): ChatMessage {
  const text = message.toLowerCase();
  const admin = isAdminRole(userRole);
  const leavePath = admin ? '/time-off' : '/employee/apply-leave';
  const timesheetPath = admin ? '/time-off' : '/employee/timesheets';
  const requestsPath = admin ? '/staffing-requests' : '/employee/requests';

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

  if (text.includes('balance') || text.includes('available')) {
    return {
      id: crypto.randomUUID(),
      role: 'agent',
      text: 'Your leave balance is available on the Apply Leave page. I can take you there so you can review casual, sick, earned, and other leave balances before applying.',
      actions: [
        { label: admin ? 'Open Time Off' : 'View Leave Balance', path: leavePath, icon: <CalendarPlus size={15} /> },
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

export function AskOrbitAIPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'agent',
      text: 'Hi, I am Ask Orbit AI. Ask me about leave, timesheets, requests, attendance, projects, or HR policies. I can answer and guide you to the right action.',
    },
  ]);

  const displayName = useMemo(() => user?.name?.split(' ')[0] || 'there', [user?.name]);
  const hasOnlyWelcome = messages.length === 1 && messages[0]?.id === 'welcome';

  const sendMessage = () => {
    const trimmed = input.trim();
    if (!trimmed) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      text: trimmed,
    };
    setMessages((current) => [...current, userMessage, getAgentReply(trimmed, user?.role)]);
    setInput('');
  };

  const clearChat = () => {
    setMessages([
      {
        id: 'welcome',
        role: 'agent',
        text: 'Chat cleared. What would you like Ask Orbit AI to help with next?',
      },
    ]);
  };

  return (
    <div className="-mx-[var(--layout-main-padding-x)] -my-[var(--layout-main-padding-y)] flex h-[calc(100vh-3.5rem)] min-h-0 flex-col overflow-hidden">
      <section className="flex min-h-0 flex-1 flex-col overflow-hidden bg-white">
        <div className="border-b border-[#E7E9EE] px-5 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#252B3A] text-accent">
                <Bot size={21} />
              </div>
              <div>
                <div className="text-sm font-bold text-[#252B3A]">Ask Orbit AI</div>
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

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto bg-[#FAF8F4] px-5 py-5">
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
                  'max-w-[840px] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm',
                  message.role === 'user'
                    ? 'bg-[#252B3A] text-white'
                    : 'border border-[#E7E9EE] bg-white text-[#252B3A]'
                )}
              >
                {message.role === 'agent' && (
                  <div className="mb-1 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-accent">
                    <Bot size={13} />
                    Ask Orbit AI
                  </div>
                )}
                <div>{message.text}</div>
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
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-[#E7E9EE] bg-white p-4">
          {hasOnlyWelcome && (
            <div className="mb-3 flex flex-wrap gap-2">
              {prompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setInput(prompt)}
                  className="rounded-full border border-[#E7E9EE] bg-[#FBFAF7] px-3 py-1.5 text-xs font-semibold text-[#252B3A] transition hover:border-accent-mid hover:bg-accent-light"
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
              placeholder="Ask Orbit AI to apply leave, check balance, submit timesheet..."
              className="min-h-12 flex-1 rounded-2xl border border-[#E7E9EE] bg-[#FBFAF7] px-4 text-sm font-medium text-[#252B3A] outline-none transition focus:border-accent-mid focus:ring-2 focus:ring-accent-light"
            />
            <Button icon={<Send size={16} />} onClick={sendMessage}>
              Send
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

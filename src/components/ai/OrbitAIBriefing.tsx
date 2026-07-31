import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Archive,
  Check,
  CornerDownLeft,
  History,
  Maximize2,
  Minimize2,
  Plus,
  RotateCcw,
  Trash2,
  X,
} from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth, type AuthUser } from '@/hooks/useAuth';
import type { ChatMessage } from '@/pages/AskOrbitAIPage';
import { AIChatResponseContent } from '@/components/ai/AIChatResponseContent';
import {
  AIAPIError,
  archiveAIConversation,
  closeAIConversation,
  deleteAIConversation,
  getAIConversation,
  listAIConversations,
  restoreAIConversation,
  sendAIChat,
  startAIConversation,
  type AIConversationDetail,
  type AIConversationSummary,
  type AIConversationWorkflow,
} from '@/services/aiApi';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
type Action = { label: string; href?: string; intent?: string };
type Item = {
  id: string; severity: 'overdue' | 'due_soon' | 'waiting' | 'advisory';
  title: string; urgencyLabel: string; heroValue?: string | null; heroUnit?: string | null;
  weekBars: Array<{ day: string; pct: number; deficient: boolean }>; reasoning: string;
  primaryAction?: Action | null; secondaryAction?: Action | null; dismissLabel: string;
};
type Completion = { confirmation: string; next: string; viewLabel: string; viewHref: string; undoToken: string };
type Upcoming = { title: string; displayDate: string } | null;
type StoredConversation = {
  conversationId?: string;
};
type PanelView = 'briefing' | 'conversation' | 'history';

const authHeaders = (user: AuthUser | null) => ({
  'Content-Type': 'application/json',
  ...(user?.id ? { 'X-User-Id': user.id } : {}),
  ...(user?.email ? { 'X-User-Email': user.email } : {}),
});

function routeContext(path: string) {
  if (path.includes('timesheet')) return 'On Timesheets';
  if (path.includes('document')) return 'On Documents';
  if (path.includes('leave')) return 'On Apply Leave';
  if (path.includes('request')) return 'On Requests';
  if (path.includes('project') || path.includes('allocation')) return 'On My Allocations';
  return path.includes('dashboard') || path === '/employee' ? 'On My Dashboard' : 'In Orbit';
}

function formatConversationTime(value: string | null) {
  if (!value) return 'No messages yet';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? 'Unknown'
    : parsed.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
}

export function OrbitAIBriefing({
  maximized,
  onToggleMaximize,
}: {
  maximized: boolean;
  onToggleMaximize: () => void;
}) {
  const { user, accessToken } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [upcoming, setUpcoming] = useState<Upcoming>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');
  const dismissalKey = `orbit.ai.dismissed.${user?.id || user?.email || 'anonymous'}`;
  const [dismissed, setDismissed] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(`orbit.ai.dismissed.${user?.id || user?.email || 'anonymous'}`);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const [completions, setCompletions] = useState<Record<string, Completion>>({});
  const [question, setQuestion] = useState('');
  const [conversation, setConversation] = useState<ChatMessage[]>([]);
  const [answerLoading, setAnswerLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string>();
  const [conversationTitle, setConversationTitle] = useState('Orbit AI conversation');
  const [conversationWorkflow, setConversationWorkflow] = useState<AIConversationWorkflow | null>(null);
  const [conversationNotice, setConversationNotice] = useState('');
  const [panelView, setPanelView] = useState<PanelView>('briefing');
  const [history, setHistory] = useState<AIConversationSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [conversationPendingDelete, setConversationPendingDelete] = useState<AIConversationSummary | null>(null);
  const [deleteInProgress, setDeleteInProgress] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const conversationStorageKey = `orbit.ai.conversation.${user?.id || user?.email || 'anonymous'}`;
  const [hydratedConversationKey, setHydratedConversationKey] = useState<string>();
  const messageScrollRef = useRef<HTMLDivElement>(null);
  const deleteDialogRef = useRef<HTMLElement>(null);
  const deleteCancelRef = useRef<HTMLButtonElement>(null);
  const deleteInProgressRef = useRef(false);
  const nearMessageBottomRef = useRef(true);
  const previousConversationLengthRef = useRef(0);
  const [newContentWaiting, setNewContentWaiting] = useState(false);
  const visible = useMemo(() => items.filter((item) => !dismissed.includes(item.id)).slice(0, 2), [items, dismissed]);
  const outstanding = useMemo(() => visible.filter((item) => !completions[item.id]), [visible, completions]);
  const more = Math.max(0, total - visible.length - dismissed.length);

  const applyConversationDetail = useCallback((detail: AIConversationDetail) => {
    setConversationId(detail.conversation.id);
    setConversationTitle(detail.conversation.title);
    setConversationWorkflow(detail.workflow);
    setConversationNotice(detail.notice);
    setConversation(detail.messages.map((message) => ({
      id: message.id,
      role: message.role === 'assistant' ? 'agent' : 'user',
      text: message.content,
      correlationId: message.correlation_id || undefined,
      status: message.response_status || undefined,
    })));
    setPanelView('conversation');
  }, []);

  const scrollToLatest = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const container = messageScrollRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior });
    nearMessageBottomRef.current = true;
    setNewContentWaiting(false);
  }, []);

  const handleMessageScroll = () => {
    const container = messageScrollRef.current;
    if (!container) return;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    nearMessageBottomRef.current = distanceFromBottom <= 72;
    if (nearMessageBottomRef.current) setNewContentWaiting(false);
  };

  useEffect(() => {
    if (!conversationPendingDelete) return;

    const previouslyFocused = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    deleteCancelRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        if (!deleteInProgressRef.current) {
          setConversationPendingDelete(null);
          setDeleteError('');
        }
        return;
      }
      if (event.key !== 'Tab') return;
      event.stopPropagation();

      const focusable = Array.from(
        deleteDialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) || [],
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [conversationPendingDelete]);

  useEffect(() => {
    let active = true;
    try {
      const stored = sessionStorage.getItem(conversationStorageKey);
      if (!stored) {
        setConversation([]);
        setConversationId(undefined);
        setPanelView('briefing');
        setHydratedConversationKey(conversationStorageKey);
        return;
      }
      const parsed = JSON.parse(stored) as Partial<StoredConversation>;
      const storedId = typeof parsed.conversationId === 'string' ? parsed.conversationId : undefined;
      if (!storedId) {
        sessionStorage.removeItem(conversationStorageKey);
        setHydratedConversationKey(conversationStorageKey);
        return;
      }
      setConversationId(storedId);
      void getAIConversation(storedId, accessToken).then((detail) => {
        if (!active) return;
        applyConversationDetail(detail);
      }).catch(() => {
        if (!active) return;
        setConversation([]);
        setConversationId(undefined);
        setPanelView('briefing');
        sessionStorage.removeItem(conversationStorageKey);
      }).finally(() => {
        if (active) setHydratedConversationKey(conversationStorageKey);
      });
    } catch {
      setConversation([]);
      setConversationId(undefined);
      setPanelView('briefing');
      sessionStorage.removeItem(conversationStorageKey);
      setHydratedConversationKey(conversationStorageKey);
    }
    return () => { active = false; };
  }, [accessToken, applyConversationDetail, conversationStorageKey]);

  useEffect(() => {
    if (hydratedConversationKey !== conversationStorageKey) return;
    try {
      if (!conversationId) {
        sessionStorage.removeItem(conversationStorageKey);
        return;
      }
      const stored: StoredConversation = { conversationId };
      sessionStorage.setItem(conversationStorageKey, JSON.stringify(stored));
    } catch {
      // Session storage can be unavailable in hardened browser contexts.
    }
  }, [conversationId, conversationStorageKey, hydratedConversationKey]);

  useEffect(() => {
    const previousLength = previousConversationLengthRef.current;
    previousConversationLengthRef.current = conversation.length;
    if (conversation.length === 0) {
      nearMessageBottomRef.current = true;
      setNewContentWaiting(false);
      return;
    }
    if (conversation.length <= previousLength) return;
    if (nearMessageBottomRef.current) {
      window.requestAnimationFrame(() => scrollToLatest('smooth'));
    } else {
      setNewContentWaiting(true);
    }
  }, [conversation.length, scrollToLatest]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE}/me/action-items`, { headers: authHeaders(user) }).then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Could not load your briefing.');
        return data;
      }),
      fetch(`${API_BASE}/me/upcoming`, { headers: authHeaders(user) }).then((response) => response.ok ? response.json() : { item: null }),
    ]).then(([actions, horizon]) => {
      if (!active) return;
      setItems(actions.items || []);
      setTotal(actions.total || 0);
      setUpcoming(horizon.item || null);
      setError('');
    }).catch((requestError) => active && setError(requestError instanceof Error ? requestError.message : 'Could not load your briefing.'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [user?.id, user?.email]);

  useEffect(() => {
    const completedIds = Object.keys(completions);
    if (!completedIds.length) return;
    const timers = completedIds.map((id) => window.setTimeout(() => {
      setDismissed((current) => current.includes(id) ? current : [...current, id]);
    }, 10_000));
    return () => timers.forEach(window.clearTimeout);
  }, [completions]);

  useEffect(() => {
    try {
      localStorage.setItem(dismissalKey, JSON.stringify(dismissed.slice(-100)));
    } catch {
      // Local storage may be unavailable in hardened browser contexts.
    }
  }, [dismissalKey, dismissed]);

  const execute = async (item: Item) => {
    setBusyId(item.id);
    try {
      const response = await fetch(`${API_BASE}/me/action-items/${encodeURIComponent(item.id)}/execute`, {
        method: 'POST', headers: authHeaders(user),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Orbit could not complete that action.');
      setCompletions((current) => ({ ...current, [item.id]: data }));
      setError('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Orbit could not complete that action.');
    } finally { setBusyId(''); }
  };

  const undo = async (item: Item) => {
    const result = completions[item.id];
    if (!result) return;
    setBusyId(item.id);
    try {
      const response = await fetch(`${API_BASE}/me/action-items/${encodeURIComponent(item.id)}/undo`, {
        method: 'POST', headers: authHeaders(user), body: JSON.stringify({ undoToken: result.undoToken }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'This action could not be undone.');
      setCompletions((current) => { const next = { ...current }; delete next[item.id]; return next; });
      setError('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'This action could not be undone.');
    } finally { setBusyId(''); }
  };

  const act = (item: Item, action?: Action | null) => {
    if (action?.href) navigate(action.href);
    else if (action?.intent === 'execute') void execute(item);
  };

  const startNewConversation = async () => {
    if (answerLoading) return;
    setAnswerLoading(true);
    try {
      if (conversationId) {
        await closeAIConversation(conversationId, accessToken);
      }
      const created = await startAIConversation(accessToken);
      setConversationId(created.id);
      setConversationTitle(created.title);
      setConversation([]);
      setConversationWorkflow(null);
      setConversationNotice('');
      setPanelView('conversation');
      setHistoryError('');
    } catch (requestError) {
      setHistoryError(requestError instanceof AIAPIError
        ? requestError.message
        : 'Could not start a new conversation.');
    } finally {
      setAnswerLoading(false);
    }
  };

  const showHistory = async () => {
    setPanelView('history');
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const response = await listAIConversations(accessToken);
      setHistory(response.conversations);
    } catch (requestError) {
      setHistoryError(requestError instanceof AIAPIError
        ? requestError.message
        : 'Conversation history is unavailable.');
    } finally {
      setHistoryLoading(false);
    }
  };

  const reopenConversation = async (summary: AIConversationSummary) => {
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const detail = await restoreAIConversation(summary.id, accessToken);
      applyConversationDetail(detail);
    } catch (requestError) {
      setHistoryError(requestError instanceof AIAPIError
        ? requestError.message
        : 'Could not reopen that conversation.');
    } finally {
      setHistoryLoading(false);
    }
  };

  const backToBriefing = async () => {
    const activeId = conversationId;
    setPanelView('briefing');
    setConversation([]);
    setConversationId(undefined);
    setConversationWorkflow(null);
    setConversationNotice('');
    setQuestion('');
    sessionStorage.removeItem(conversationStorageKey);
    if (!activeId) return;
    try {
      await closeAIConversation(activeId, accessToken);
    } catch {
      // The transcript is already durable; returning to briefing must remain usable.
    }
  };

  const archiveCurrentConversation = async () => {
    if (!conversationId) return;
    try {
      await archiveAIConversation(conversationId, accessToken);
      await backToBriefing();
    } catch (requestError) {
      setError(requestError instanceof AIAPIError
        ? requestError.message
        : 'Could not archive that conversation.');
    }
  };

  const requestConversationDelete = (summary: AIConversationSummary) => {
    setDeleteError('');
    setConversationPendingDelete(summary);
  };

  const cancelConversationDelete = () => {
    if (deleteInProgress) return;
    setDeleteError('');
    setConversationPendingDelete(null);
  };

  const removeConversation = async () => {
    if (!conversationPendingDelete || deleteInProgress) return;
    const summary = conversationPendingDelete;
    deleteInProgressRef.current = true;
    setDeleteInProgress(true);
    setDeleteError('');
    try {
      await deleteAIConversation(summary.id, accessToken);
      setHistory((current) => current.filter((item) => item.id !== summary.id));
      if (conversationId === summary.id) {
        setConversationId(undefined);
        setConversation([]);
        sessionStorage.removeItem(conversationStorageKey);
      }
      setConversationPendingDelete(null);
    } catch (requestError) {
      setDeleteError(requestError instanceof AIAPIError
        ? requestError.message
        : 'Could not delete that conversation.');
    } finally {
      deleteInProgressRef.current = false;
      setDeleteInProgress(false);
    }
  };

  const archiveHistoryConversation = async (summary: AIConversationSummary) => {
    try {
      const archived = await archiveAIConversation(summary.id, accessToken);
      setHistory((current) => current.map((item) => (
        item.id === summary.id ? { ...item, ...archived } : item
      )));
      if (conversationId === summary.id) {
        setConversationId(undefined);
        setConversation([]);
        sessionStorage.removeItem(conversationStorageKey);
      }
    } catch (requestError) {
      setHistoryError(requestError instanceof AIAPIError
        ? requestError.message
        : 'Could not archive that conversation.');
    }
  };

  const submitPrompt = async (value: string) => {
    const prompt = value.trim();
    if (!prompt || answerLoading) return;
    const continueConversationId = panelView === 'conversation'
      ? conversationId
      : undefined;
    setQuestion('');
    setPanelView('conversation');
    setConversation((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', text: prompt },
    ]);
    setAnswerLoading(true);
    try {
      let activeConversationId = continueConversationId;
      if (!activeConversationId) {
        const created = await startAIConversation(accessToken);
        activeConversationId = created.id;
        setConversationId(created.id);
        setConversationTitle(created.title);
      }
      const response = await sendAIChat(prompt, accessToken, activeConversationId);
      setConversationId(response.conversation_id);
      setConversation((current) => [...current, {
        id: crypto.randomUUID(),
        role: 'agent',
        text: response.message.content,
        result: response.result,
        correlationId: response.correlation_id,
        status: response.status,
      }]);
      setConversationNotice('');
      setConversationWorkflow(
        response.result?.type === 'leave_request_draft'
          ? {
              kind: 'leave_request_draft',
              status: response.result.draft.status,
              display_status: 'active',
              message: 'This draft is current for this conversation.',
              refreshed_at: new Date().toISOString(),
            }
          : conversationWorkflow,
      );
    } catch (requestError) {
      const apiError = requestError instanceof AIAPIError ? requestError : null;
      setConversation((current) => [...current, {
          id: crypto.randomUUID(),
          role: 'agent',
          text: apiError?.message || 'I could not answer that just now. Please try again.',
          correlationId: apiError?.correlationId,
        }]);
    } finally {
      setAnswerLoading(false);
    }
  };
  const ask = () => void submitPrompt(question);
  const handleDraftAction = (prompt: string, submit = true) => {
    if (submit) void submitPrompt(prompt);
    else setQuestion(prompt);
  };
  const empty = !loading && !error && visible.length === 0;

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden font-['Instrument_Sans',sans-serif] text-[#221f1a]">
      <header
        data-testid="orbit-ai-header"
        className="shrink-0 border-b border-[#e9e1d3] bg-[#fbf8f2]/95 px-5 pb-3 pt-4 backdrop-blur-sm sm:px-7 sm:pb-4 sm:pt-5"
      >
        <div className={`mx-auto w-full ${maximized ? 'max-w-[820px]' : ''}`}>
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <span className={`h-[7px] w-[7px] shrink-0 rounded-full ${empty ? 'bg-[#c4bcaa]' : 'orbit-ai-breathe bg-[#1c7d73]'}`} />
              <span className="truncate text-[10.5px] font-bold tracking-[1.1px] text-[#1c7d73]">
                {panelView === 'history' ? 'HISTORY' : panelView === 'conversation' ? 'CONVERSATION' : empty ? 'NOTHING LEFT' : 'ORBIT AI'}
              </span>
            </div>
            <div className="flex shrink-0 items-center gap-1.5 sm:gap-3">
              <span className="hidden max-w-[150px] truncate text-[11px] text-[#6f6757] min-[380px]:inline">
                {routeContext(location.pathname)}
              </span>
              <button
                type="button"
                onClick={() => void showHistory()}
                title="Conversation history"
                aria-label="Open conversation history"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#6b6353] transition-colors hover:bg-[#eee7dc] hover:text-[#221f1a] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/40"
              >
                <History size={16} />
              </button>
              <button
                type="button"
                onClick={() => void startNewConversation()}
                title="New conversation"
                aria-label="Start new conversation"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#6b6353] transition-colors hover:bg-[#eee7dc] hover:text-[#221f1a] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/40"
              >
                <Plus size={16} />
              </button>
              <button
                type="button"
                onClick={onToggleMaximize}
                title={maximized ? 'Restore compact view' : 'Maximize Orbit AI'}
                aria-label={maximized ? 'Restore compact Orbit AI view' : 'Maximize Orbit AI'}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#6b6353] transition-colors hover:bg-[#eee7dc] hover:text-[#221f1a] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/40"
              >
                {maximized ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              </button>
            </div>
          </div>
          {panelView !== 'briefing' && (
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="truncate text-[11px] text-[#8a8270]">
                {panelView === 'history' ? 'Your saved conversations' : conversationTitle}
              </span>
              <div className="flex shrink-0 items-center gap-1">
                {panelView === 'conversation' && conversationId && (
                  <button
                    type="button"
                    onClick={() => void archiveCurrentConversation()}
                    title="Archive conversation"
                    aria-label="Archive conversation"
                    className="flex h-7 w-7 items-center justify-center rounded-md text-[#6b6353] hover:bg-[#eee7dc] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/40"
                  >
                    <Archive size={13} />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void backToBriefing()}
                  className="shrink-0 rounded-md px-1.5 py-1 text-[11.5px] font-semibold text-[#6b6353] hover:bg-[#eee7dc] hover:text-[#221f1a] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/40"
                >
                  Back to briefing
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

      <div className="relative min-h-0 flex-1">
        <main
          ref={messageScrollRef}
          data-testid="orbit-ai-scroll-region"
          onScroll={handleMessageScroll}
          className="orbit-ai-message-scroll h-full min-h-0 overflow-x-hidden overflow-y-auto overscroll-contain px-5 sm:px-7"
        >
          <div className={`mx-auto w-full ${maximized ? 'max-w-[820px]' : ''}`}>
            {panelView === 'history' ? (
              <div className="space-y-3 py-5 sm:py-6" data-testid="orbit-ai-history">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-[16px] font-semibold text-[#221f1a]">Conversation history</h2>
                    <p className="mt-1 text-[11.5px] text-[#736b5c]">
                      Reopened conversations refresh current workflow state.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void startNewConversation()}
                    className="shrink-0 rounded-xl bg-[#1c7d73] px-3 py-2 text-[11px] font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/40"
                  >
                    New conversation
                  </button>
                </div>
                {historyError && (
                  <div role="alert" className="rounded-xl border border-[#e7c8bf] bg-[#fff5f1] p-3 text-[12px] text-[#9a3f2b]">
                    {historyError}
                  </div>
                )}
                {historyLoading ? (
                  <div className="space-y-2" aria-label="Loading conversation history">
                    {[0, 1, 2].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-[#eee7dc]" />)}
                  </div>
                ) : history.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-[#d9d1c2] px-4 py-8 text-center text-[12px] text-[#736b5c]">
                    No saved conversations yet.
                  </div>
                ) : history.map((summary) => (
                  <article key={summary.id} className="rounded-2xl border border-[#e9e1d3] bg-white/75 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <button
                        type="button"
                        onClick={() => void reopenConversation(summary)}
                        className="min-w-0 flex-1 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1c7d73]/40"
                        aria-label={`Reopen ${summary.title}`}
                      >
                        <span className="block truncate text-[13px] font-semibold text-[#221f1a]">{summary.title}</span>
                        <span className="mt-1 block text-[10.5px] uppercase tracking-[.7px] text-[#8a8270]">
                          {summary.domain} · {summary.status}
                          {summary.workflow_status ? ` · ${summary.workflow_status}` : ''}
                        </span>
                        <span className="mt-2 block text-[11px] text-[#736b5c]">
                          Created {formatConversationTime(summary.created_at)} · Updated {formatConversationTime(summary.updated_at)}
                        </span>
                      </button>
                      <div className="flex shrink-0 items-center gap-1">
                        {summary.status === 'archived' && (
                          <button
                            type="button"
                            onClick={() => void reopenConversation(summary)}
                            title="Restore conversation"
                            aria-label={`Restore ${summary.title}`}
                            className="flex h-8 w-8 items-center justify-center rounded-full text-[#6b6353] hover:bg-[#eee7dc] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/40"
                          >
                            <RotateCcw size={14} />
                          </button>
                        )}
                        {summary.status !== 'archived' && (
                          <button
                            type="button"
                            onClick={() => void archiveHistoryConversation(summary)}
                            title="Archive conversation"
                            aria-label={`Archive ${summary.title}`}
                            className="flex h-8 w-8 items-center justify-center rounded-full text-[#6b6353] hover:bg-[#eee7dc] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/40"
                          >
                            <Archive size={14} />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => requestConversationDelete(summary)}
                          title="Delete conversation"
                          aria-label={`Delete ${summary.title}`}
                          className="flex h-8 w-8 items-center justify-center rounded-full text-[#9a4a38] hover:bg-[#f7e8e3] focus:outline-none focus:ring-2 focus:ring-[#9a4a38]/35"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : panelView === 'conversation' ? (
              <div className="space-y-4 py-5 sm:py-6">
              {conversationNotice && conversation.length > 0 && (
                <div className="rounded-xl border border-[#d8d0c1] bg-[#f4efe5] px-3 py-2 text-[10.5px] leading-5 text-[#6b6353]">
                  {conversationNotice}
                </div>
              )}
              {conversationWorkflow && (
                <div className={`rounded-xl border px-3 py-2 text-[11px] leading-5 ${
                  conversationWorkflow.display_status === 'expired'
                    ? 'border-[#e7c8bf] bg-[#fff5f1] text-[#9a3f2b]'
                    : conversationWorkflow.display_status === 'completed'
                      ? 'border-[#bdd9c0] bg-[#eef7ef] text-[#3f7d3f]'
                      : 'border-[#d8d0c1] bg-[#fbf8f2] text-[#6b6353]'
                }`}>
                  <span className="font-semibold capitalize">{conversationWorkflow.display_status}</span>
                  {' · '}{conversationWorkflow.message}
                </div>
              )}
              {conversation.map((message, index) => (
                <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={message.role === 'user'
                    ? 'max-w-[85%] rounded-[16px_16px_4px_16px] bg-[#221f1a] px-4 py-3 text-[13px] leading-[1.6] text-white'
                    : 'max-w-[92%] rounded-[4px_16px_16px_16px] border border-[#e9e1d3] bg-white/70 px-4 py-3 text-[13px] leading-[1.7] text-[#736b5c]'}
                    role={message.role === 'agent' && index === conversation.length - 1 ? 'status' : undefined}
                    aria-live={message.role === 'agent' && index === conversation.length - 1 ? 'polite' : undefined}
                  >
                    {message.role === 'agent' && <div className="mb-1.5 text-[9.5px] font-bold tracking-[1px] text-[#1c7d73]">ORBIT AI</div>}
                    <AIChatResponseContent
                      text={message.text}
                      status={message.status}
                      result={message.result}
                      correlationId={message.correlationId}
                      onAction={handleDraftAction}
                    />
                    {message.actions && message.actions.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-4">
                        {message.actions.map((action) => (
                          <button key={action.path} type="button" onClick={() => navigate(action.path)} className="text-[12px] font-semibold text-[#1c7d73]">
                            {action.label} →
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {answerLoading && (
                <div className="flex justify-start">
                  <div className="rounded-[4px_16px_16px_16px] border border-[#e9e1d3] bg-white/70 px-4 py-3">
                    <AIChatResponseContent loading />
                  </div>
                </div>
              )}
              {!answerLoading && conversation.length === 0 && (
                <div className="rounded-2xl border border-dashed border-[#d9d1c2] px-4 py-8 text-center">
                  <p className="text-[13px] font-semibold text-[#221f1a]">Start a new conversation</p>
                  <p className="mt-1 text-[11.5px] text-[#736b5c]">Ask about your leave balance, status, eligibility, or draft.</p>
                </div>
              )}
            </div>
        ) : loading ? (
          <div className="py-7"><div className="h-7 w-4/5 animate-pulse rounded bg-[#e9e1d3]" /><div className="mt-3 h-4 w-3/5 animate-pulse rounded bg-[#eee7dc]" /></div>
        ) : error ? (
          <div className="py-7"><h2 className="font-['Instrument_Serif',Georgia,serif] text-[25px] leading-[1.26]">I couldn't finish your briefing.</h2><p className="mt-2 text-[12.5px] leading-6 text-[#736b5c]">{error}</p></div>
        ) : empty ? (
          <div className="pb-7 pt-5">
            <h2 className="font-['Instrument_Serif',Georgia,serif] text-[26px] italic leading-[1.26] tracking-[-.4px] text-[#4a4438]">
              {Object.keys(completions).length ? 'That was the last one.' : new Date().getDay() >= 5 ? "You're clear. Enjoy the weekend." : "You're clear. Nothing needs you today."}
            </h2>
            <p className="mt-3 text-[12.5px] leading-6 text-[#736b5c]">{upcoming ? `Next thing on your plate is ${upcoming.title} — ${upcoming.displayDate}.` : 'There is nothing dated on your immediate horizon.'}</p>
          </div>
        ) : (
          <>
            <h2 className="pb-6 pt-5 font-['Instrument_Serif',Georgia,serif] text-[26px] leading-[1.26] tracking-[-.4px]">
              {outstanding.length === 0
                ? 'Your part is done.'
                : outstanding.length === 1
                  ? 'One thing still needs your attention.'
                  : `${outstanding.length} things stand between you and being done.`}
            </h2>
            {visible.map((item, index) => {
              const done = completions[item.id];
              return (
                <section key={item.id} className="border-t border-[#e9e1d3] py-5">
                  {done ? (
                    <>
                      <div className="flex items-center gap-2"><span className="flex h-[18px] w-[18px] items-center justify-center rounded-full bg-[#1c7d73] text-white"><Check size={12} /></span><span className="text-[10.5px] font-bold tracking-[1px] text-[#1c7d73]">DONE</span></div>
                      <h3 className="mt-3 font-['Instrument_Serif',Georgia,serif] text-[22px] leading-tight">{done.confirmation}</h3>
                      <p className="mt-2 text-[12.5px] leading-5 text-[#736b5c]">{done.next}</p>
                      <div className="mt-4 flex gap-6 text-[12.5px] font-semibold"><button onClick={() => navigate(done.viewHref)} className="text-[#1c7d73]">{done.viewLabel}</button><button disabled={busyId === item.id} onClick={() => void undo(item)} className="text-[#6b6353] disabled:opacity-50">Undo</button></div>
                    </>
                  ) : (
                    <>
                      <div className="flex items-start justify-between gap-4">
                        <h3 className="text-[15px] font-semibold">{item.title}</h3>
                        <div className="flex shrink-0 items-center gap-2">
                          <span className={`text-[10.5px] font-bold uppercase ${item.severity === 'waiting' ? 'text-[#7d6210]' : item.severity === 'advisory' ? 'text-[#6f6757]' : 'text-[#a8442c]'}`}>{item.urgencyLabel}</span>
                          <button
                            type="button"
                            onClick={() => setDismissed((current) => current.includes(item.id) ? current : [...current, item.id])}
                            title="Dismiss this item"
                            aria-label={`Dismiss ${item.title}`}
                            className="flex h-6 w-6 items-center justify-center rounded-full text-[#8a8270] transition-colors hover:bg-[#eee7dc] hover:text-[#221f1a] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/30"
                          >
                            <X size={13} />
                          </button>
                        </div>
                      </div>
                      {index === 0 && item.heroValue && <>
                        <div className="mt-3 flex items-end gap-1.5"><span className="font-['Instrument_Serif',Georgia,serif] text-[40px] leading-none">{item.heroValue}</span><span className="pb-1 text-[12px] text-[#736b5c]">{item.heroUnit}</span></div>
                        <div className="mt-4 grid grid-cols-5 gap-1">{item.weekBars.map((bar, barIndex) => <div key={`${bar.day}-${barIndex}`} className="text-center"><div className="relative h-[38px] overflow-hidden rounded bg-[#e3dccd]"><span className={`absolute inset-x-0 bottom-0 ${bar.deficient ? 'bg-[#1c7d73]' : 'bg-[#8a8270]'}`} style={{ height: `${Math.max(8, bar.pct)}%` }} /></div><span className="mt-1.5 block text-[9.5px] text-[#6f6757]">{bar.day}</span></div>)}</div>
                      </>}
                      <p className={`${index === 0 ? 'mt-4' : 'mt-2'} text-[12.5px] leading-[1.6] text-[#736b5c]`}>{item.reasoning}</p>
                      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3 text-[12.5px] font-semibold">
                        {item.primaryAction && (index === 0
                          ? <button disabled={busyId === item.id} onClick={() => act(item, item.primaryAction)} className="rounded-[13px] bg-[#221f1a] px-5 py-3 text-white disabled:opacity-50">{busyId === item.id ? 'Working…' : item.primaryAction.label}</button>
                          : <button disabled={busyId === item.id} onClick={() => act(item, item.primaryAction)} className="text-[#1c7d73] disabled:opacity-50">{busyId === item.id ? 'Working…' : item.primaryAction.label}</button>)}
                        {item.secondaryAction && <button disabled={busyId === item.id} onClick={() => act(item, item.secondaryAction)} className="text-[#1c7d73] disabled:opacity-50">{item.secondaryAction.label}</button>}
                        {index > 0 && <button onClick={() => setDismissed((current) => [...current, item.id])} className="text-[#6b6353]">{item.dismissLabel}</button>}
                      </div>
                    </>
                  )}
                </section>
              );
            })}
            {more > 0 && <button onClick={() => navigate('/employee/requests')} className="mb-5 text-[12px] font-semibold text-[#1c7d73]">{more} more →</button>}
          </>
        )}
          </div>
        </main>
        {newContentWaiting && (
          <button
            type="button"
            onClick={() => scrollToLatest('smooth')}
            aria-label="Jump to latest message"
            className="absolute bottom-3 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-full border border-[#d9d1c2] bg-[#221f1a] px-3 py-2 text-[11px] font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-[#343027] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/50"
          >
            Jump to latest
          </button>
        )}
      </div>
      <footer
        data-testid="orbit-ai-composer"
        className="shrink-0 border-t border-[#e9e1d3] bg-[#f4efe5] pb-[env(safe-area-inset-bottom)]"
      >
        <div className={`mx-auto flex min-h-[66px] w-full items-center gap-3 px-5 sm:px-7 ${maximized ? 'max-w-[820px]' : ''}`}>
          <input
            disabled={answerLoading}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && void ask()}
            placeholder="Or ask me something"
            aria-label="Ask Orbit AI a question"
            className="min-w-0 flex-1 border-0 bg-transparent text-[13px] outline-none placeholder:text-[#736b5c] focus-visible:ring-0 disabled:opacity-60"
          />
          <button
            type="button"
            disabled={answerLoading}
            onClick={() => void ask()}
            title="Send question"
            aria-label="Send question"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#6f6757] hover:bg-[#e7dfd1] hover:text-[#221f1a] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/40 disabled:opacity-50"
          >
            <CornerDownLeft size={15} />
          </button>
        </div>
      </footer>
      {conversationPendingDelete && (
        <div
          className="fixed inset-0 z-[1100] flex items-end justify-center bg-[#17140f]/45 p-3 backdrop-blur-[2px] sm:items-center sm:p-6"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) cancelConversationDelete();
          }}
        >
          <section
            ref={deleteDialogRef}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-conversation-title"
            aria-describedby="delete-conversation-description"
            className="w-full max-w-[420px] overflow-hidden rounded-[22px] border border-[#e9e1d3] bg-[#fbf8f2] shadow-[0_28px_80px_rgba(23,20,15,.28)]"
          >
            <div className="px-5 pb-5 pt-5 sm:px-6 sm:pb-6 sm:pt-6">
              <div className="flex items-start gap-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#f7e8e3] text-[#9a4a38]">
                  <Trash2 size={19} strokeWidth={1.8} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-bold uppercase tracking-[1.2px] text-[#9a4a38]">
                    Permanent action
                  </p>
                  <h2
                    id="delete-conversation-title"
                    className="mt-1 font-['Instrument_Serif',Georgia,serif] text-[24px] leading-tight tracking-[-.2px] text-[#221f1a]"
                  >
                    Delete conversation?
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={cancelConversationDelete}
                  disabled={deleteInProgress}
                  aria-label="Close delete confirmation"
                  className="-mr-1 -mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#8a8270] transition hover:bg-[#eee7dc] hover:text-[#221f1a] focus:outline-none focus:ring-2 focus:ring-[#9a4a38]/35 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <X size={17} aria-hidden="true" />
                </button>
              </div>

              <p id="delete-conversation-description" className="mt-4 text-[13px] leading-6 text-[#6f6757]">
                You’re about to permanently delete
                {' '}
                <span className="font-semibold text-[#221f1a]">“{conversationPendingDelete.title}”</span>.
                Its messages and activity history can’t be recovered.
              </p>

              {deleteError && (
                <div role="alert" className="mt-4 rounded-xl border border-[#e7c8bf] bg-[#fff5f1] px-3.5 py-3 text-[12px] leading-5 text-[#9a3f2b]">
                  {deleteError}
                </div>
              )}
            </div>

            <div className="flex flex-col-reverse gap-2 border-t border-[#e9e1d3] bg-[#f4efe5]/75 px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
              <button
                ref={deleteCancelRef}
                type="button"
                onClick={cancelConversationDelete}
                disabled={deleteInProgress}
                className="h-11 rounded-xl border border-[#d9d1c2] bg-white/70 px-5 text-[13px] font-semibold text-[#4a4438] transition hover:border-[#c9bfaf] hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/35 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Keep conversation
              </button>
              <button
                type="button"
                onClick={() => void removeConversation()}
                disabled={deleteInProgress}
                className="flex h-11 items-center justify-center gap-2 rounded-xl bg-[#9a4a38] px-5 text-[13px] font-semibold text-white shadow-[0_5px_14px_rgba(154,74,56,.2)] transition hover:bg-[#843d2e] focus:outline-none focus:ring-2 focus:ring-[#9a4a38]/35 focus:ring-offset-2 focus:ring-offset-[#f4efe5] disabled:cursor-wait disabled:opacity-65"
              >
                <Trash2 size={15} aria-hidden="true" />
                {deleteInProgress ? 'Deleting…' : 'Delete permanently'}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

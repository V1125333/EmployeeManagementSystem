import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { OrbitAIBriefing } from './OrbitAIBriefing';

const mocks = vi.hoisted(() => ({
  sendAIChat: vi.fn(),
  startAIConversation: vi.fn(),
  listAIConversations: vi.fn(),
  getAIConversation: vi.fn(),
  closeAIConversation: vi.fn(),
  archiveAIConversation: vi.fn(),
  restoreAIConversation: vi.fn(),
  deleteAIConversation: vi.fn(),
}));

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'orbit-user-1',
      email: 'employee@reknew.ai',
      role: 'employee',
    },
    accessToken: 'signed-token',
  }),
}));

vi.mock('@/services/aiApi', () => ({
  AIAPIError: class AIAPIError extends Error {
    correlationId?: string;
  },
  sendAIChat: mocks.sendAIChat,
  startAIConversation: mocks.startAIConversation,
  listAIConversations: mocks.listAIConversations,
  getAIConversation: mocks.getAIConversation,
  closeAIConversation: mocks.closeAIConversation,
  archiveAIConversation: mocks.archiveAIConversation,
  restoreAIConversation: mocks.restoreAIConversation,
  deleteAIConversation: mocks.deleteAIConversation,
}));

const storageKey = 'orbit.ai.conversation.orbit-user-1';

function messages(count = 24) {
  return Array.from({ length: count }, (_, index) => ({
    id: `message-${index}`,
    role: index % 2 ? 'agent' : 'user',
    text: `Conversation message ${index + 1}`,
  }));
}

function storeConversation(count = 24) {
  sessionStorage.setItem(storageKey, JSON.stringify({
    conversationId: 'conversation-1',
  }));
  mocks.getAIConversation.mockResolvedValue(conversationDetail(count));
}

function conversationDetail(count = 24) {
  return {
    conversation: {
      id: 'conversation-1',
      title: 'Leave Balance',
      domain: 'leave',
      capability: 'leave_balance',
      status: 'active',
      created_at: '2026-07-25T10:00:00',
      updated_at: '2026-07-25T10:05:00',
      last_message_at: '2026-07-25T10:05:00',
      message_count: count,
      workflow_status: null,
    },
    messages: messages(count).map((message, index) => ({
      id: message.id,
      role: message.role === 'agent' ? 'assistant' : 'user',
      content: message.text,
      response_status: message.role === 'agent' ? 'completed' : null,
      result_type: null,
      correlation_id: index % 2 ? `correlation-${index}` : null,
      created_at: `2026-07-25T10:${String(index).padStart(2, '0')}:00`,
      historical: true,
    })),
    workflow: null,
    facts_require_refresh: true,
    notice: 'Historical messages are restored for context.',
  };
}

function renderBriefing(maximized = false, onToggleMaximize = vi.fn()) {
  return render(
    <MemoryRouter initialEntries={['/employee/dashboard']}>
      <OrbitAIBriefing
        maximized={maximized}
        onToggleMaximize={onToggleMaximize}
      />
    </MemoryRouter>,
  );
}

function ResizableBriefing() {
  const [maximized, setMaximized] = useState(false);
  return (
    <OrbitAIBriefing
      maximized={maximized}
      onToggleMaximize={() => setMaximized((value) => !value)}
    />
  );
}

function setScrollGeometry(
  element: HTMLElement,
  { scrollHeight, clientHeight, scrollTop }: {
    scrollHeight: number;
    clientHeight: number;
    scrollTop: number;
  },
) {
  Object.defineProperties(element, {
    scrollHeight: { configurable: true, value: scrollHeight },
    clientHeight: { configurable: true, value: clientHeight },
    scrollTop: { configurable: true, writable: true, value: scrollTop },
  });
}

describe('OrbitAIBriefing panel layout and scrolling', () => {
  const scrollTo = vi.fn();

  beforeEach(() => {
    sessionStorage.clear();
    Object.values(mocks).forEach((mock) => mock.mockReset());
    mocks.startAIConversation.mockResolvedValue({
      id: 'new-conversation',
      title: 'New Orbit AI conversation',
      domain: 'leave',
      capability: null,
      status: 'active',
      created_at: '2026-07-25T10:00:00',
      updated_at: '2026-07-25T10:00:00',
      last_message_at: null,
      message_count: 0,
      workflow_status: null,
    });
    mocks.closeAIConversation.mockResolvedValue({ status: 'closed' });
    mocks.archiveAIConversation.mockResolvedValue({ status: 'archived' });
    mocks.deleteAIConversation.mockResolvedValue({ deleted: true });
    mocks.listAIConversations.mockResolvedValue({ conversations: [] });
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
      ok: true,
      json: async () => String(input).includes('/upcoming')
        ? { item: null }
        : { items: [], total: 0 },
    })));
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      value: scrollTo,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    scrollTo.mockReset();
  });

  it('keeps the header, controls, and composer outside the long-message scroll region', async () => {
    storeConversation(30);
    renderBriefing();

    await screen.findByText('Conversation message 30');
    const header = screen.getByTestId('orbit-ai-header');
    const scroller = screen.getByTestId('orbit-ai-scroll-region');
    const composer = screen.getByTestId('orbit-ai-composer');

    expect(scroller).toHaveClass('overflow-y-auto', 'min-h-0');
    expect(scroller).toHaveClass('overflow-x-hidden');
    expect(scroller.contains(header)).toBe(false);
    expect(scroller.contains(composer)).toBe(false);
    expect(screen.getByRole('button', { name: 'Maximize Orbit AI' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Back to briefing' })).toBeVisible();
    expect(screen.getByRole('textbox', { name: 'Ask Orbit AI a question' })).toBeVisible();
  });

  it('restores a backend conversation and Back to briefing preserves it in history', async () => {
    storeConversation(4);
    renderBriefing();

    await screen.findByText('Conversation message 4');
    fireEvent.click(screen.getByRole('button', { name: 'Back to briefing' }));

    await waitFor(() => {
      expect(screen.queryByText('Conversation message 4')).not.toBeInTheDocument();
      expect(sessionStorage.getItem(storageKey)).toBeNull();
      expect(mocks.closeAIConversation).toHaveBeenCalledWith('conversation-1', 'signed-token');
    });
  });

  it('maximizing and restoring leaves the conversation intact', async () => {
    storeConversation(6);
    render(
      <MemoryRouter initialEntries={['/employee/dashboard']}>
        <ResizableBriefing />
      </MemoryRouter>,
    );

    await screen.findByText('Conversation message 6');
    fireEvent.click(screen.getByRole('button', { name: 'Maximize Orbit AI' }));
    expect(screen.getByRole('button', { name: 'Restore compact Orbit AI view' })).toBeVisible();
    expect(screen.getByText('Conversation message 6')).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'Restore compact Orbit AI view' }));
    expect(screen.getByRole('button', { name: 'Maximize Orbit AI' })).toBeVisible();
    expect(screen.getByText('Conversation message 6')).toBeVisible();
  });

  it('auto-scrolls a new message when the reader is near the bottom', async () => {
    storeConversation(8);
    mocks.sendAIChat.mockImplementation(() => new Promise(() => {}));
    renderBriefing();

    await screen.findByText('Conversation message 8');
    const scroller = screen.getByTestId('orbit-ai-scroll-region');
    setScrollGeometry(scroller, {
      scrollHeight: 1000,
      clientHeight: 300,
      scrollTop: 650,
    });
    fireEvent.scroll(scroller);
    scrollTo.mockClear();

    fireEvent.change(screen.getByRole('textbox', { name: 'Ask Orbit AI a question' }), {
      target: { value: 'A new question' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }));

    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Jump to latest message' })).not.toBeInTheDocument();
  });

  it('does not force-scroll when reading older messages and offers Jump to latest', async () => {
    storeConversation(8);
    mocks.sendAIChat.mockImplementation(() => new Promise(() => {}));
    renderBriefing();

    await screen.findByText('Conversation message 8');
    const scroller = screen.getByTestId('orbit-ai-scroll-region');
    setScrollGeometry(scroller, {
      scrollHeight: 1000,
      clientHeight: 300,
      scrollTop: 120,
    });
    fireEvent.scroll(scroller);
    scrollTo.mockClear();

    fireEvent.change(screen.getByRole('textbox', { name: 'Ask Orbit AI a question' }), {
      target: { value: 'Do not move my scroll' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }));

    const jump = await screen.findByRole('button', { name: 'Jump to latest message' });
    expect(scrollTo).not.toHaveBeenCalled();
    fireEvent.click(jump);
    expect(scrollTo).toHaveBeenCalledWith({ top: 1000, behavior: 'smooth' });
    expect(screen.queryByRole('button', { name: 'Jump to latest message' })).not.toBeInTheDocument();
  });

  it('opens history and restores the selected conversation', async () => {
    const summary = conversationDetail(4).conversation;
    mocks.listAIConversations.mockResolvedValue({ conversations: [summary] });
    mocks.restoreAIConversation.mockResolvedValue(conversationDetail(4));
    renderBriefing();

    fireEvent.click(screen.getByRole('button', { name: 'Open conversation history' }));
    expect(await screen.findByText('Conversation history')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Reopen Leave Balance' }));

    expect(await screen.findByText('Conversation message 4')).toBeVisible();
    expect(mocks.restoreAIConversation).toHaveBeenCalledWith('conversation-1', 'signed-token');
  });

  it('starts a new conversation without clearing saved history', async () => {
    renderBriefing();
    fireEvent.click(screen.getByRole('button', { name: 'Start new conversation' }));

    expect(await screen.findByText('Start a new conversation')).toBeVisible();
    expect(mocks.startAIConversation).toHaveBeenCalledWith('signed-token');
    expect(JSON.parse(sessionStorage.getItem(storageKey) || '{}')).toEqual({
      conversationId: 'new-conversation',
    });
  });

  it('keeps messages when maximizing after a backend restore', async () => {
    storeConversation(3);
    render(
      <MemoryRouter initialEntries={['/employee/dashboard']}>
        <ResizableBriefing />
      </MemoryRouter>,
    );

    await screen.findByText('Conversation message 3');
    fireEvent.click(screen.getByRole('button', { name: 'Maximize Orbit AI' }));
    expect(screen.getByText('Conversation message 3')).toBeVisible();
  });

  it('requires confirmation before deleting a conversation', async () => {
    const summary = conversationDetail(1).conversation;
    mocks.listAIConversations.mockResolvedValue({ conversations: [summary] });
    renderBriefing();

    fireEvent.click(screen.getByRole('button', { name: 'Open conversation history' }));
    await screen.findByText('Leave Balance');
    fireEvent.click(screen.getByRole('button', { name: 'Delete Leave Balance' }));

    expect(screen.getByRole('alertdialog', { name: 'Delete conversation?' })).toBeVisible();
    expect(screen.getByText(/messages and activity history can’t be recovered/i)).toBeVisible();
    expect(mocks.deleteAIConversation).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }));

    await waitFor(() => expect(mocks.deleteAIConversation).toHaveBeenCalledWith(
      'conversation-1',
      'signed-token',
    ));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(screen.queryByText('Leave Balance')).not.toBeInTheDocument();
  });

  it('keeps the conversation when the delete dialog is dismissed', async () => {
    const summary = conversationDetail(1).conversation;
    mocks.listAIConversations.mockResolvedValue({ conversations: [summary] });
    renderBriefing();

    fireEvent.click(screen.getByRole('button', { name: 'Open conversation history' }));
    await screen.findByText('Leave Balance');
    fireEvent.click(screen.getByRole('button', { name: 'Delete Leave Balance' }));
    fireEvent.click(screen.getByRole('button', { name: 'Keep conversation' }));

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(screen.getByText('Leave Balance')).toBeVisible();
    expect(mocks.deleteAIConversation).not.toHaveBeenCalled();
  });
});

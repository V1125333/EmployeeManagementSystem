import { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, CornerDownLeft, X } from 'lucide-react';
import { OrbitAIGlyph } from '@/components/ai/OrbitAIGlyph';
import { AIChatResponseContent } from '@/components/ai/AIChatResponseContent';
import { Button } from '@/components/ui';
import { ApiError } from '@/services/apiClient';
import { sendOrbitMessage } from '@/services/orbitApi';
import { cn } from '@/utils/cn';

type OrbitMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
};

const WELCOME_MESSAGE = 'Hi! I\'m Orbit AI. How can I help you today?';
const FALLBACK_ERROR = 'I\'m having trouble connecting right now. Please try again.';

export function OrbitFloatingAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<OrbitMessage[]>([
    { id: 'orbit-welcome', role: 'assistant', content: WELCOME_MESSAGE },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const messageViewportRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading]);

  useEffect(() => {
    if (!isOpen) return;
    textareaRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    const viewport = messageViewportRef.current;
    if (!viewport) return;
    viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' });
  }, [messages, isLoading, isOpen]);

  const submitMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    setError('');
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', content: trimmed },
    ]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await sendOrbitMessage(trimmed, conversationId);
      setConversationId(response.conversation_id);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.message || FALLBACK_ERROR,
        },
      ]);
    } catch (reason) {
      const friendlyMessage = reason instanceof ApiError && reason.message
        ? FALLBACK_ERROR
        : FALLBACK_ERROR;
      setError(friendlyMessage);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: friendlyMessage },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="pointer-events-none fixed bottom-6 right-6 z-[80] flex flex-col items-end gap-3">
      {isOpen && (
        <section
          aria-label="Orbit AI assistant"
          className="pointer-events-auto flex h-[560px] w-[400px] max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-[26px] border border-[#e9e1d3] bg-[#fbf8f2] shadow-[0_28px_80px_rgba(23,20,15,.22)]"
        >
          <header className="border-b border-[#e9e1d3] bg-[#fbf8f2]/95 px-5 pb-4 pt-4 backdrop-blur-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-[#1c7d73] to-[#12433f] shadow-[0_8px_22px_rgba(18,67,63,.18)]">
                  <OrbitAIGlyph className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <div className="truncate text-[10.5px] font-bold uppercase tracking-[1.1px] text-[#1c7d73]">
                    Orbit AI
                  </div>
                  <h2 className="truncate text-[15px] font-semibold text-[#221f1a]">Your ReKnew Assistant</h2>
                </div>
              </div>
              <button
                type="button"
                aria-label="Close Orbit AI"
                onClick={() => setIsOpen(false)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#8a8270] transition hover:bg-[#eee7dc] hover:text-[#221f1a] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/35"
              >
                <X size={17} />
              </button>
            </div>
          </header>

          <div
            ref={messageViewportRef}
            className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto bg-[#f6f1e7] px-4 py-4"
          >
            {messages.map((message) => (
              <div
                key={message.id}
                className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}
              >
                <div
                  className={cn(
                    'max-w-[88%] rounded-[18px] px-4 py-3 text-[13px] leading-[1.65] shadow-sm',
                    message.role === 'user'
                      ? 'rounded-br-[6px] bg-[#221f1a] text-white'
                      : 'rounded-bl-[6px] border border-[#e9e1d3] bg-white/90 text-[#4a4438]'
                  )}
                >
                  {message.role === 'assistant' && (
                    <div className="mb-1.5 flex items-center gap-2 text-[9.5px] font-bold uppercase tracking-[1px] text-[#1c7d73]">
                      <Bot size={12} />
                      Orbit AI
                    </div>
                  )}
                  <AIChatResponseContent text={message.content} />
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="rounded-[18px] rounded-bl-[6px] border border-[#e9e1d3] bg-white/90 px-4 py-3 text-[13px] text-[#6f6757] shadow-sm">
                  <div className="mb-1 text-[9.5px] font-bold uppercase tracking-[1px] text-[#1c7d73]">Orbit AI</div>
                  <span role="status">Orbit is thinking...</span>
                </div>
              </div>
            )}
          </div>

          <footer className="border-t border-[#e9e1d3] bg-[#f4efe5] px-4 pb-4 pt-3">
            {error && (
              <div className="mb-3 rounded-xl border border-[#e7c8bf] bg-[#fff5f1] px-3 py-2 text-[12px] text-[#9a3f2b]">
                {error}
              </div>
            )}
            <div className="flex items-end gap-3">
              <textarea
                ref={textareaRef}
                value={input}
                disabled={isLoading}
                rows={2}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void submitMessage();
                  }
                }}
                placeholder="Ask Orbit..."
                aria-label="Ask Orbit AI"
                className="min-h-[52px] flex-1 resize-none rounded-2xl border border-[#d9d1c2] bg-white px-4 py-3 text-[13px] text-[#221f1a] outline-none transition placeholder:text-[#8a8270] focus:border-[#1c7d73] focus:ring-2 focus:ring-[#1c7d73]/15 disabled:opacity-70"
              />
              <Button
                type="button"
                onClick={() => void submitMessage()}
                disabled={!canSend}
                className="h-11 w-11 shrink-0 justify-center rounded-full px-0"
                icon={<CornerDownLeft size={15} />}
                aria-label="Send Orbit AI message"
                title="Send"
              />
            </div>
          </footer>
        </section>
      )}

      <div className="pointer-events-auto flex items-center gap-2">
        {isOpen && (
          <span className="rounded-full border border-[#e9e1d3] bg-[#fbf8f2] px-3 py-1.5 text-[11px] font-semibold text-[#6b6353] shadow-sm">
            Orbit AI
          </span>
        )}
        <button
          type="button"
          aria-label={isOpen ? 'Hide Orbit AI assistant' : 'Open Orbit AI assistant'}
          title="Orbit AI"
          onClick={() => setIsOpen((current) => !current)}
          className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-[#1c7d73] to-[#12433f] text-white shadow-[0_18px_45px_rgba(18,67,63,.28)] transition hover:-translate-y-0.5 hover:shadow-[0_22px_55px_rgba(18,67,63,.32)] focus:outline-none focus:ring-2 focus:ring-[#1c7d73]/35"
        >
          <OrbitAIGlyph className="h-6 w-6" />
        </button>
      </div>
    </div>
  );
}

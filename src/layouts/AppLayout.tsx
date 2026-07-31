import { useEffect, useRef, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { X } from 'lucide-react';
import { OrbitAIGlyph } from '@/components/ai/OrbitAIGlyph';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopNav } from '@/components/layout/TopNav';
import { OrbitAIBriefing } from '@/components/ai/OrbitAIBriefing';
import { cn } from '@/utils/cn';
import { useTheme } from '@/hooks/useTheme';

export function AppLayout() {
  const { sidebarCollapsed, compactMode } = useTheme();
  const launcherRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const [assistantMaximized, setAssistantMaximized] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const closeAssistant = () => {
    setAssistantOpen(false);
    setAssistantMaximized(false);
    window.setTimeout(() => launcherRef.current?.focus(), 0);
  };

  useEffect(() => {
    if (assistantOpen) {
      window.setTimeout(() => dialogRef.current?.querySelector<HTMLElement>('input, button')?.focus(), 0);
    }
  }, [assistantOpen]);

  useEffect(() => {
    if (!assistantOpen) return;
    const previousOverflow = document.body.style.overflow;
    const previousPaddingRight = document.body.style.paddingRight;
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
    document.body.style.overflow = 'hidden';
    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    }
    return () => {
      document.body.style.overflow = previousOverflow;
      document.body.style.paddingRight = previousPaddingRight;
    };
  }, [assistantOpen]);

  useEffect(() => {
    const handleKeyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && assistantOpen) {
        event.preventDefault();
        closeAssistant();
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        assistantOpen ? closeAssistant() : setAssistantOpen(true);
        return;
      }
      if (event.key === 'Tab' && assistantOpen && dialogRef.current) {
        const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        ));
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
      }
    };
    window.addEventListener('keydown', handleKeyboard);
    return () => window.removeEventListener('keydown', handleKeyboard);
  }, [assistantOpen]);

  return (
    <div className="min-h-screen bg-warm-bg font-sans" data-compact={compactMode}>
      <div
        className={cn(
          'min-h-screen transition-[filter,opacity] duration-200',
          assistantOpen && 'saturate-[.72] opacity-50',
        )}
      >
        <Sidebar />
        <div className={cn('min-h-screen transition-all duration-250', sidebarCollapsed ? 'ml-16' : 'ml-60')}>
          <TopNav />
          <main className="px-[var(--layout-main-padding-x)] pb-[86px] pt-[var(--layout-main-padding-y)]">
            <Outlet />
          </main>
        </div>
      </div>

      <button
        type="button"
        aria-label="Close Orbit AI"
        onClick={closeAssistant}
        className={cn(
          'orbit-ai-scrim fixed inset-0 z-[32] cursor-default border-0',
          assistantOpen ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0',
        )}
      />
      <aside
        ref={dialogRef}
        role="dialog"
        aria-label="Orbit AI"
        aria-modal="true"
        aria-hidden={!assistantOpen}
        tabIndex={-1}
        className={cn(
          'orbit-ai-surface fixed z-[35] origin-bottom-right overflow-hidden overscroll-contain rounded-[26px] border border-white/90 bg-[#fbf8f2] shadow-[0_2px_4px_rgba(60,50,35,.08),0_34px_64px_-16px_rgba(40,33,24,.42)]',
          assistantMaximized
            ? 'bottom-[88px] right-[22px] top-[22px] min-w-[560px] w-[min(50vw,900px)] max-md:left-[14px] max-md:right-[14px] max-md:top-[14px] max-md:min-w-0 max-md:w-auto'
            : 'bottom-[88px] right-[22px] h-[min(680px,calc(100dvh-110px))] w-[min(408px,calc(100vw-28px))] max-sm:right-[14px]',
          assistantOpen ? 'pointer-events-auto translate-y-0 scale-100 opacity-100' : 'pointer-events-none translate-y-3 scale-[.98] opacity-0',
        )}
      >
        {assistantOpen && (
          <OrbitAIBriefing
            maximized={assistantMaximized}
            onToggleMaximize={() => setAssistantMaximized((current) => !current)}
          />
        )}
      </aside>

      <button
        ref={launcherRef}
        type="button"
        onClick={() => assistantOpen ? closeAssistant() : setAssistantOpen(true)}
        title={assistantOpen ? 'Close Orbit AI' : 'Ask Orbit AI'}
        aria-label={assistantOpen ? 'Close Orbit AI' : 'Ask Orbit AI'}
        aria-expanded={assistantOpen}
        className={cn(
          'fixed bottom-[22px] right-[22px] z-[40] flex h-[50px] w-[50px] cursor-pointer items-center justify-center rounded-full border-0 shadow-[0_6px_18px_rgba(18,67,63,.3)] transition-all duration-150 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(18,67,63,.42)] focus:outline-none focus:ring-4 focus:ring-[#199a8e]/20 active:scale-95',
          assistantOpen ? 'bg-[#221f1a]' : 'bg-gradient-to-br from-[#199a8e] to-[#12433f]',
        )}
      >
        {assistantOpen ? <X size={21} strokeWidth={1.9} className="text-[#eafffb]" /> : <OrbitAIGlyph className="orbit-ai-glyph" />}
      </button>
    </div>
  );
}

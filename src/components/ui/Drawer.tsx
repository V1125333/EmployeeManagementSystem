import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/utils/cn';

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = 'w-[580px]',
}: DrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  // ESC key to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    if (open) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex justify-end">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/20 backdrop-blur-[2px] animate-[fadeIn_0.2s_ease]"
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        className={cn(
          width,
          'relative h-full bg-warm-card border-l border-[#E5E7EB] shadow-[-8px_0_30px_rgba(47,52,55,0.08)]',
          'flex flex-col',
          'animate-[slideInRight_0.3s_cubic-bezier(0.16,1,0.3,1)]'
        )}
      >
        {/* Header */}
        <div className="px-7 pt-7 pb-5 border-b border-[#E5E7EB] shrink-0">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-bold text-[#2F3437] tracking-tight">
                {title}
              </h2>
              {subtitle && (
                <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
              )}
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:bg-hover-bg hover:text-gray-600 transition-all"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content — scrollable */}
        <div className="flex-1 overflow-y-auto px-7 py-6">
          {children}
        </div>

        {/* Footer */}
        {footer && (
<div className="px-7 py-3 border-t border-[#E5E7EB] shrink-0 bg-warm-card">            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

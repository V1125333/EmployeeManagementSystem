import { useEffect, useState, createContext, useContext, useCallback, type ReactNode } from 'react';
import { CheckCircle, X, ChevronRight } from 'lucide-react';
import { cn } from '@/utils/cn';

// ─── Types ───
interface Toast {
  id: string;
  message: string;
  action?: { label: string; onClick: () => void };
  duration?: number;
}

interface ToastContextType {
  showToast: (toast: Omit<Toast, 'id'>) => void;
}

// ─── Context ───
const ToastContext = createContext<ToastContextType | null>(null);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
}

// ─── Toast Item ───
function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(() => onDismiss(toast.id), 300);
    }, toast.duration || 5000);
    return () => clearTimeout(timer);
  }, [toast, onDismiss]);

  const handleDismiss = () => {
    setExiting(true);
    setTimeout(() => onDismiss(toast.id), 300);
  };

  return (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-3.5 rounded-xl',
        'bg-warm-card border border-[#E5E7EB] shadow-card-md',
        'min-w-[340px] max-w-[420px]',
        'transition-all duration-300',
        exiting
          ? 'opacity-0 translate-x-4'
          : 'opacity-100 translate-x-0 animate-[slideInRight_0.3s_ease]'
      )}
    >
      <CheckCircle size={18} className="text-status-success shrink-0" />
      <span className="text-[13.5px] font-medium text-[#2F3437] flex-1">
        {toast.message}
      </span>
      {toast.action && (
        <button
          onClick={toast.action.onClick}
          className="flex items-center gap-1 text-[13px] font-semibold text-olive hover:text-olive-dark transition-colors shrink-0"
        >
          {toast.action.label}
          <ChevronRight size={14} />
        </button>
      )}
      <button
        onClick={handleDismiss}
        className="text-gray-400 hover:text-gray-600 transition-colors shrink-0 ml-1"
      >
        <X size={14} />
      </button>
    </div>
  );
}

// ─── Provider ───
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Date.now().toString();
    setToasts((prev) => [...prev, { ...toast, id }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}

      {/* Toast container — bottom right */}
      {toasts.length > 0 && (
        <div className="fixed bottom-6 right-6 z-[200] flex flex-col gap-2">
          {toasts.map((toast) => (
            <ToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}

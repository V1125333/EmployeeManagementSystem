import React from 'react';
import { cn } from '@/utils/cn';

// ═══════════════════════════════════════
// CARD
// ═══════════════════════════════════════
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Card({ children, className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'bg-warm-card border border-[var(--color-border)] rounded-card shadow-card',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  icon,
  action,
  badge,
  badgeColor = 'neutral',
}: {
  title: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  badge?: string;
  badgeColor?: BadgeVariant;
}) {
  return (
    <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
      <div className="flex items-center gap-2">
        {icon && (
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-light text-[var(--color-nav-active-bar)]">
            {icon}
          </span>
        )}
        <span className="text-sm font-semibold text-[var(--color-text-primary)] tracking-tight">
          {title}
        </span>
      </div>
      {action || (badge ? <Badge variant={badgeColor}>{badge}</Badge> : null)}
    </div>
  );
}

// ═══════════════════════════════════════
// AVATAR
// ═══════════════════════════════════════
interface AvatarProps {
  initials: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'filled' | 'soft';
  src?: string | null;
}

const avatarSizes = {
  sm: 'w-8 h-8 text-[11px]',
  md: 'w-9 h-9 text-xs',
  lg: 'w-12 h-12 text-sm',
};

export function Avatar({ initials, size = 'md', variant = 'soft', src }: AvatarProps) {
  return (
    <div
      className={cn(
        'rounded-full flex items-center justify-center font-semibold shrink-0 overflow-hidden',
        avatarSizes[size],
        variant === 'filled'
          ? 'bg-[var(--color-text-primary)] text-warm-card'
          : 'bg-accent-light text-accent'
      )}
    >
      {src ? (
        <img src={src} alt="" className="w-full h-full object-cover" />
      ) : (
        initials
      )}
    </div>
  );
}

// ═══════════════════════════════════════
// BADGE
// ═══════════════════════════════════════
type BadgeVariant = 'olive' | 'success' | 'warning' | 'error' | 'info' | 'sage' | 'neutral';

const badgeStyles: Record<BadgeVariant, string> = {
  olive: 'bg-accent-light text-[var(--color-nav-active-text)]',
  success: 'bg-[var(--color-status-success-bg)] text-[var(--color-status-success)]',
  warning: 'bg-[var(--color-status-warning-bg)] text-[var(--color-status-warning)]',
  error: 'bg-[var(--color-status-error-bg)] text-[var(--color-status-error)]',
  info: 'bg-[var(--color-status-info-bg)] text-[var(--color-status-info)]',
  sage: 'bg-[var(--color-status-info-bg)] text-[var(--color-status-info)]',
  neutral: 'bg-sage/10 text-[var(--color-text-muted)]',
};

export function Badge({
  children,
  variant = 'olive',
}: {
  children: React.ReactNode;
  variant?: BadgeVariant;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-3 py-1 rounded-full text-[11px] font-semibold',
        badgeStyles[variant]
      )}
    >
      {children}
    </span>
  );
}

// ═══════════════════════════════════════
// BUTTONS
// ═══════════════════════════════════════
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'soft';
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center gap-1.5 font-semibold rounded-btn transition-all duration-150 cursor-pointer',
        size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-[13px]',
        variant === 'primary' &&
          'bg-[var(--color-text-primary)] text-warm-card shadow-sm hover:opacity-90 active:scale-[0.98]',
        variant === 'ghost' &&
          'bg-transparent text-[var(--color-text-primary)] border border-[var(--color-border)] hover:bg-hover-bg hover:text-[var(--color-nav-active-text)] active:scale-[0.98]',
        variant === 'soft' &&
          'bg-accent-light text-[var(--color-nav-active-text)] hover:bg-accent-mid active:scale-[0.98]',
        className
      )}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}

// ═══════════════════════════════════════
// STATUS DOT
// ═══════════════════════════════════════
export function StatusDot({ color }: { color: string }) {
  return (
    <span
      className="w-2 h-2 rounded-full shrink-0 opacity-60"
      style={{ backgroundColor: color }}
    />
  );
}

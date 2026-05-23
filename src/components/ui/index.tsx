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
        'bg-warm-card border border-[#E5E7EB] rounded-card shadow-card',
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
}: {
  title: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-5 py-4 border-b border-[#E5E7EB]">
      <div className="flex items-center gap-2">
        {icon && <span className="text-olive">{icon}</span>}
        <span className="text-sm font-semibold text-[#2F3437] tracking-tight">
          {title}
        </span>
      </div>
      {action}
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
          ? 'bg-olive text-white'
          : 'bg-hover-bg text-olive'
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
  olive: 'bg-olive/10 text-olive',
  success: 'bg-status-success/10 text-status-success',
  warning: 'bg-status-warning/10 text-status-warning',
  error: 'bg-status-error/10 text-status-error',
  info: 'bg-status-info/10 text-status-info',
  sage: 'bg-sage/10 text-sage',
  neutral: 'bg-gray-100 text-gray-500',
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
        'inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold',
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
          'bg-olive text-white shadow-sm hover:bg-olive-dark active:scale-[0.98]',
        variant === 'ghost' &&
          'bg-transparent text-olive border border-[#E5E7EB] hover:bg-hover-bg active:scale-[0.98]',
        variant === 'soft' &&
          'bg-hover-bg text-olive hover:bg-olive-mid active:scale-[0.98]',
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

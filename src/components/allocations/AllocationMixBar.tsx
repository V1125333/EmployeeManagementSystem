import { cn } from '@/utils/cn';

interface AllocationMixBarProps {
  allocated: number;
  className?: string;
  compact?: boolean;
  showLabels?: boolean;
}

function clampPercent(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

export function AllocationMixBar({ allocated, className, compact = false, showLabels = false }: AllocationMixBarProps) {
  const allocatedPercent = Math.max(0, Math.round(Number(allocated) || 0));
  const visibleAllocated = clampPercent(allocatedPercent);
  const availablePercent = Math.max(0, 100 - allocatedPercent);
  const isOverallocated = allocatedPercent > 100;
  const isTight = allocatedPercent >= 80 && !isOverallocated;
  const allocatedColor = isOverallocated
    ? 'bg-status-error'
    : isTight
      ? 'bg-accent'
      : 'bg-[var(--color-brand-navy)]';

  return (
    <div className={cn('space-y-2', className)}>
      {showLabels && (
        <div className="flex items-center justify-between gap-3 text-xs font-bold">
          <span className="text-[var(--color-brand-navy)]">{allocatedPercent}% allocated</span>
          <span className={isOverallocated ? 'text-status-error' : 'text-status-success'}>
            {isOverallocated ? `${allocatedPercent - 100}% over` : `${availablePercent}% available`}
          </span>
        </div>
      )}
      <div
        className={cn('flex overflow-hidden rounded-full bg-hover-bg', compact ? 'h-2' : 'h-2.5')}
        title={isOverallocated ? `${allocatedPercent}% allocated, ${allocatedPercent - 100}% overallocated` : `${allocatedPercent}% allocated, ${availablePercent}% available`}
      >
        <div
          className={cn('transition-all', allocatedColor)}
          style={{ width: `${visibleAllocated}%` }}
          aria-label={`${allocatedPercent}% allocated`}
        />
        {!isOverallocated && (
          <div
            className="bg-status-success/70 transition-all"
            style={{ width: `${clampPercent(availablePercent)}%` }}
            aria-label={`${availablePercent}% available`}
          />
        )}
      </div>
    </div>
  );
}

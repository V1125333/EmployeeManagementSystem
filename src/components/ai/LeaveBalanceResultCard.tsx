import type { LeaveBalanceItem } from '@/services/aiApi';

function value(value: number | 'On request') {
  return typeof value === 'number' ? `${value} days` : value;
}

function sourceLabel(source: LeaveBalanceItem['source']) {
  if (source === 'stored_balance') return 'Recorded balance · stored_balance';
  if (source === 'policy_default') return 'Policy entitlement · policy_default';
  return 'Available on request · on_request';
}

export function LeaveBalanceResultCard({
  title,
  asOf,
  balances,
}: {
  title: string;
  asOf: string;
  balances: LeaveBalanceItem[];
}) {
  return (
    <section className="mt-3 overflow-hidden rounded-xl border border-[#d9d1c2] bg-[#fffdf8]" aria-label={title}>
      <div className="flex items-center justify-between border-b border-[#eee7dc] px-3 py-2">
        <h4 className="text-xs font-bold text-[#221f1a]">{title}</h4>
        <span className="text-[9px] text-[#8a8270]">
          As of {new Date(asOf).toLocaleDateString()}
        </span>
      </div>
      <div className="divide-y divide-[#eee7dc]">
        {balances.map((balance) => (
          <div key={balance.code} className="px-3 py-2.5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-semibold text-[#221f1a]">{balance.leave_type}</div>
                <div className="mt-0.5 text-[9px] text-[#8a8270]">{sourceLabel(balance.source)}</div>
              </div>
              <strong className="text-sm text-[#1c7d73]">{value(balance.available)}</strong>
            </div>
            <div className="mt-2 grid grid-cols-3 gap-2 text-[9.5px] text-[#736b5c]">
              <span>Total <b className="text-[#221f1a]">{balance.total}</b></span>
              <span>Used <b className="text-[#221f1a]">{balance.used}</b></span>
              <span>Pending <b className="text-[#221f1a]">{balance.pending}</b></span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

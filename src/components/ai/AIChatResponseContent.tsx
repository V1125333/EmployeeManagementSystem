import type { AIChatResponse } from '@/services/aiApi';
import { LeaveBalanceResultCard } from './LeaveBalanceResultCard';
import { LeaveAgentResultCards } from './LeaveAgentResultCards';

export function AIChatResponseContent({
  text,
  status,
  result,
  correlationId,
  loading = false,
  onAction,
}: {
  text?: string;
  status?: AIChatResponse['status'];
  result?: AIChatResponse['result'];
  correlationId?: string;
  loading?: boolean;
  onAction?: (prompt: string, submit?: boolean) => void;
}) {
  if (loading) {
    return <span role="status">Orbit AI is checking…</span>;
  }
  return (
    <>
      {status === 'unsupported' && (
        <span className="mb-2 inline-flex rounded-full bg-[#eee7dc] px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-[#736b5c]">
          Not available yet
        </span>
      )}
      <p className="whitespace-pre-line">{text}</p>
      {result?.type === 'leave_balance' && (
        <LeaveBalanceResultCard
          title={result.title}
          asOf={result.as_of}
          balances={result.balances}
        />
      )}
      {result && result.type !== 'leave_balance' && (
        <LeaveAgentResultCards result={result} correlationId={correlationId} onAction={onAction} />
      )}
      {correlationId && !result && (
        <div className="mt-2 text-[9px] text-[#9a927f]">Reference: {correlationId}</div>
      )}
    </>
  );
}

import type { AIResult, LeaveBalanceItem, LeaveRequestItem } from '@/services/aiApi';
import { LeaveEligibilityResultCard } from './LeaveEligibilityResultCard';
import { LeaveRequestDraftCard } from './LeaveRequestDraftCard';

const date = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString(
  undefined,
  { month: 'short', day: 'numeric', year: 'numeric' },
);

const available = (item: LeaveBalanceItem) => (
  typeof item.available === 'number' ? `${item.available} days` : item.available
);

function StatusPill({ status }: { status: string }) {
  const tone = status === 'approved'
    ? 'bg-[#e5f3e5] text-[#3f7d3f]'
    : status === 'rejected' || status === 'cancelled'
      ? 'bg-[#fcecec] text-[#b84444]'
      : 'bg-[#fbeee1] text-[#a86423]';
  return (
    <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${tone}`}>
      {status}
    </span>
  );
}

function RequestRow({ request }: { request: LeaveRequestItem }) {
  return (
    <div className="border-t border-[#eee7dc] px-3 py-2.5 first:border-t-0">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold text-[#221f1a]">{request.leave_type}</div>
          <div className="mt-0.5 text-[9.5px] text-[#8a8270]">
            {date(request.start_date)}
            {request.end_date !== request.start_date ? ` – ${date(request.end_date)}` : ''}
            {' · '}{request.total_days} day{request.total_days === 1 ? '' : 's'}
          </div>
        </div>
        <StatusPill status={request.status} />
      </div>
      {request.status === 'pending' && (
        <div className="mt-1.5 text-[9.5px] text-[#736b5c]">
          {request.approver ? `With ${request.approver}` : 'Approver unavailable'}
          {request.pending_duration_days !== null ? ` · ${request.pending_duration_days} day(s) pending` : ''}
        </div>
      )}
    </div>
  );
}

export function LeaveAgentResultCards({
  result,
  correlationId,
  onAction,
}: {
  result: Exclude<AIResult, { type: 'leave_balance' }>;
  correlationId?: string;
  onAction?: (prompt: string, submit?: boolean) => void;
}) {
  if (result.type === 'leave_request_draft') {
    return <LeaveRequestDraftCard draft={result.draft} onAction={onAction} />;
  }
  if (result.type === 'leave_intake_cancelled') {
    return (
      <section className="mt-3 rounded-xl border border-[#d9d1c2] bg-[#fffdf8] p-3" aria-label={result.title}>
        <div className="text-xs font-bold text-[#221f1a]">{result.title}</div>
        <p className="mt-1.5 text-[10px] leading-4 text-[#736b5c]">{result.message}</p>
      </section>
    );
  }
  if (result.type === 'leave_intake_question' || result.type === 'leave_intake_summary') {
    const fields = result.intake.collected_fields;
    const dates = fields.start_date
      ? `${date(fields.start_date)}${fields.end_date && fields.end_date !== fields.start_date ? ` – ${date(fields.end_date)}` : ''}`
      : null;
    return (
      <section className="mt-3 rounded-xl border border-[#d97a34] bg-[#fffaf5] p-3" aria-label={result.title} aria-live="polite">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-bold text-[#221f1a]">{result.title}</span>
          <span className="rounded-full bg-[#fbeee1] px-2 py-0.5 text-[8px] font-bold uppercase text-[#a86423]">
            Intake
          </span>
        </div>
        {'prompt' in result && (
          <p className="mt-1.5 text-[10px] leading-4 text-[#554e42]">{result.prompt}</p>
        )}
        <div className="mt-2 flex flex-wrap gap-1.5 text-[8.5px]">
          {dates && <span className="rounded-full bg-white px-2 py-1 text-[#554e42]">{dates}</span>}
          {fields.leave_type && <span className="rounded-full bg-white px-2 py-1 text-[#554e42]">{fields.leave_type}</span>}
          {fields.reason && <span className="rounded-full bg-white px-2 py-1 text-[#554e42]">Reason: {fields.reason}</span>}
          {fields.reason_skipped && <span className="rounded-full bg-white px-2 py-1 text-[#8a8270]">No reason</span>}
        </div>
        {result.intake.missing_required_fields.length > 0 && (
          <div className="mt-2 text-[9px] text-[#a86423]">
            Still needed: {result.intake.missing_required_fields.map((field) => field.replace(/_/g, ' ')).join(', ')}
          </div>
        )}
        <div className="mt-2 text-[8px] text-[#9a927f]">
          Expires {new Date(result.intake.expires_at).toLocaleTimeString()}
        </div>
      </section>
    );
  }
  if (result.type === 'leave_eligibility') {
    return <LeaveEligibilityResultCard eligibility={result.eligibility} correlationId={correlationId} />;
  }
  if (result.type === 'leave_eligibility_clarification') {
    return (
      <section className="mt-3 rounded-xl border border-[#d9d1c2] bg-[#fffdf8] p-3" aria-label={result.title} aria-live="polite">
        <div className="text-xs font-bold text-[#221f1a]">{result.title}</div>
        <p className="mt-1.5 text-[10px] leading-4 text-[#736b5c]">{result.prompt}</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {result.missing_fields.map((field) => (
            <span key={field} className="rounded-full bg-[#fbeee1] px-2 py-1 text-[8.5px] font-bold text-[#a86423]">
              {field === 'leave_type' ? 'Leave type' : 'Date range'}
            </span>
          ))}
        </div>
      </section>
    );
  }
  if (result.type === 'leave_balance_comparison') {
    const summary = result.comparison === 'highest'
      ? result.highest && `${result.highest.leave_type}: ${available(result.highest)}`
      : `${result.meets_threshold ? 'Yes' : 'No'} · ${result.threshold} day threshold`;
    return (
      <section className="mt-3 rounded-xl border border-[#d9d1c2] bg-[#fffdf8] p-3" aria-label={result.title}>
        <div className="text-xs font-bold text-[#221f1a]">{result.title}</div>
        <div className="mt-2 text-sm font-semibold text-[#1c7d73]">{summary}</div>
        <div className="mt-2 space-y-1 text-[9.5px] text-[#736b5c]">
          {result.balances.map((item) => (
            <div key={item.code} className="flex justify-between">
              <span>{item.leave_type}</span><b className="text-[#221f1a]">{available(item)}</b>
            </div>
          ))}
        </div>
      </section>
    );
  }
  if (result.type === 'leave_request_list') {
    return (
      <section className="mt-3 overflow-hidden rounded-xl border border-[#d9d1c2] bg-[#fffdf8]" aria-label={result.title}>
        <div className="flex justify-between px-3 py-2 text-xs font-bold text-[#221f1a]">
          <span>{result.title}</span><span>{result.total_matches}</span>
        </div>
        {result.requests.length
          ? result.requests.map((request) => <RequestRow key={request.request_id} request={request} />)
          : <div className="border-t border-[#eee7dc] px-3 py-4 text-[10px] text-[#8a8270]">No matching requests.</div>}
      </section>
    );
  }
  if (result.type === 'leave_request_status') {
    return (
      <section className="mt-3 overflow-hidden rounded-xl border border-[#d9d1c2] bg-[#fffdf8]" aria-label={result.title}>
        <div className="px-3 py-2 text-xs font-bold text-[#221f1a]">{result.title}</div>
        <RequestRow request={result.request} />
        {result.request.decided_at && (
          <div className="border-t border-[#eee7dc] px-3 py-2 text-[9.5px] text-[#736b5c]">
            Decided {new Date(result.request.decided_at).toLocaleDateString()}
            {result.request.decided_by ? ` by ${result.request.decided_by}` : ''}
          </div>
        )}
      </section>
    );
  }
  if (result.type === 'rejection_explanation') {
    return (
      <section className="mt-3 rounded-xl border border-[#e5cfc8] bg-[#fffaf7] p-3" aria-label={result.title}>
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-bold text-[#221f1a]">{result.title}</span>
          <StatusPill status={result.request.status} />
        </div>
        <p className="mt-2 text-[10px] leading-4 text-[#736b5c]">{result.explanation}</p>
        {!result.reason_recorded && (
          <span className="mt-2 inline-block text-[9px] font-semibold text-[#a86423]">No reason recorded</span>
        )}
      </section>
    );
  }
  return (
    <section className="mt-3 overflow-hidden rounded-xl border border-[#d97a34] bg-[#fffaf5]" aria-label={result.title}>
      <div className="px-3 py-2 text-xs font-bold text-[#221f1a]">{result.title}</div>
      {result.candidates.map((request) => <RequestRow key={request.request_id} request={request} />)}
    </section>
  );
}

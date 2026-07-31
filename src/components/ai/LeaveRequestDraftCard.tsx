import type { LeaveRequestDraft } from '@/services/aiApi';

const formatDate = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString(
  undefined,
  { month: 'short', day: 'numeric', year: 'numeric' },
);

const statusLabel = (status: LeaveRequestDraft['status']) => status
  .replace(/_/g, ' ')
  .replace(/\b\w/g, (letter: string) => letter.toUpperCase());

export function LeaveRequestDraftCard({
  draft,
  onAction,
}: {
  draft: LeaveRequestDraft;
  onAction?: (prompt: string, submit?: boolean) => void;
}) {
  const ready = draft.status === 'ready_for_review' || draft.status === 'ready_for_confirmation';
  const unavailable = draft.status === 'discarded' || draft.status === 'expired';
  const balance = typeof draft.available_leave_balance === 'number'
    ? `${draft.available_leave_balance} days`
    : draft.available_leave_balance;
  return (
    <section className="mt-3 overflow-hidden rounded-xl border border-[#d97a34] bg-[#fffaf5]" aria-label="Leave request draft">
      <div className="flex items-center justify-between border-b border-[#eee1d2] px-3 py-2.5">
        <div>
          <div className="text-xs font-bold text-[#221f1a]">{draft.leave_type}</div>
          <div className="mt-0.5 text-[9px] text-[#8a8270]">
            AI draft · not submitted · v{draft.version}
          </div>
        </div>
        <span className={`rounded-full px-2 py-1 text-[8px] font-bold uppercase ${
          ready ? 'bg-[#e5f3e5] text-[#3f7d3f]' : 'bg-[#fbeee1] text-[#a86423]'
        }`}>
          {statusLabel(draft.status)}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 px-3 py-3 text-[9.5px]">
        <div><dt className="text-[#9a927f]">Dates</dt><dd className="font-semibold text-[#221f1a]">{formatDate(draft.start_date)}{draft.end_date !== draft.start_date ? ` – ${formatDate(draft.end_date)}` : ''}</dd></div>
        <div><dt className="text-[#9a927f]">Working days</dt><dd className="font-semibold text-[#221f1a]">{draft.working_day_count} of {draft.calendar_day_count}</dd></div>
        <div><dt className="text-[#9a927f]">Balance</dt><dd className="font-semibold text-[#221f1a]">{balance} · needs {draft.required_leave_units}</dd></div>
        <div>
          <dt className="text-[#9a927f]">Approver</dt>
          <dd className={`font-semibold ${draft.approver ? 'text-[#221f1a]' : 'text-[#b84444]'}`}>
            {draft.approver || 'Needs configuration'}
          </dd>
        </div>
        <div className="col-span-2"><dt className="text-[#9a927f]">Reason</dt><dd className="font-semibold text-[#221f1a]">{draft.reason || 'Not added'}</dd></div>
      </dl>
      {(draft.blocking_reasons.length > 0 || draft.warnings.length > 0) && (
        <div className="border-t border-[#eee1d2] px-3 py-2.5 text-[9.5px] leading-4">
          {draft.blocking_reasons.map((issue) => <div key={issue.code} className="text-[#b84444]">{issue.message}</div>)}
          {draft.warnings.map((issue) => <div key={issue.code} className="text-[#a86423]">{issue.message}</div>)}
        </div>
      )}
      {!unavailable && onAction && (
        <div className="flex flex-wrap gap-2 border-t border-[#eee1d2] px-3 py-3">
          <button type="button" onClick={() => onAction('Change it to ', false)} className="rounded-lg border border-[#ded5c6] bg-white px-2.5 py-1.5 text-[9px] font-semibold text-[#554e42]">Edit type</button>
          <button type="button" onClick={() => onAction('Change it to ', false)} className="rounded-lg border border-[#ded5c6] bg-white px-2.5 py-1.5 text-[9px] font-semibold text-[#554e42]">Edit dates</button>
          <button type="button" onClick={() => onAction(draft.reason ? 'Change the reason to ' : 'Add the reason ', false)} className="rounded-lg border border-[#ded5c6] bg-white px-2.5 py-1.5 text-[9px] font-semibold text-[#554e42]">{draft.reason ? 'Edit reason' : 'Add reason'}</button>
          {draft.reason && <button type="button" onClick={() => onAction('Remove the reason')} className="rounded-lg border border-[#ded5c6] bg-white px-2.5 py-1.5 text-[9px] font-semibold text-[#554e42]">Remove reason</button>}
          <button type="button" onClick={() => onAction('Discard this draft')} className="rounded-lg px-2.5 py-1.5 text-[9px] font-semibold text-[#b84444]">Discard</button>
          {ready && draft.status !== 'ready_for_confirmation' && (
            <button type="button" onClick={() => onAction('Continue with the draft')} className="ml-auto rounded-lg bg-[#d97a34] px-3 py-1.5 text-[9px] font-bold text-white">Continue</button>
          )}
        </div>
      )}
      <div className="border-t border-[#eee1d2] px-3 py-2 text-[8px] text-[#9a927f]">
        Expires {new Date(draft.expires_at).toLocaleString()} · {draft.balance_source.replace(/_/g, ' ')} · Ref {draft.correlation_id}
      </div>
    </section>
  );
}

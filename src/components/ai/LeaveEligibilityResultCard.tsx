import type { LeaveEligibility } from '@/services/aiApi';

const formatDate = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString(
  undefined,
  { month: 'short', day: 'numeric', year: 'numeric' },
);

const formatNumber = (value: number) => Number.isInteger(value) ? `${value}` : value.toFixed(1);

export function LeaveEligibilityResultCard({
  eligibility,
  correlationId,
}: {
  eligibility: LeaveEligibility;
  correlationId?: string;
}) {
  const eligible = eligibility.eligibility_status === 'eligible';
  const warning = eligibility.eligibility_status === 'eligible_with_warnings';
  const tone = eligible
    ? 'border-[#b9d8bd] bg-[#f7fcf7]'
    : warning
      ? 'border-[#ead49d] bg-[#fffbf1]'
      : eligibility.eligibility_status === 'not_eligible'
        ? 'border-[#e9c1b9] bg-[#fff8f6]'
        : 'border-[#d9d1c2] bg-[#fffdf8]';
  const title = eligible
    ? 'Eligible'
    : warning
      ? 'Eligible with warnings'
      : eligibility.eligibility_status === 'not_eligible'
        ? 'Not eligible'
        : 'More information needed';
  const statusColor = eligible
    ? 'text-[#3f7d3f]'
    : warning
      ? 'text-[#a86423]'
      : 'text-[#b84444]';

  return (
    <section className={`mt-3 rounded-xl border p-3 ${tone}`} aria-label="Leave eligibility result">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className={`text-xs font-bold ${statusColor}`}>{title}</div>
          <div className="mt-0.5 text-[10px] font-semibold text-[#221f1a]">
            {eligibility.leave_type}
          </div>
        </div>
        <span className="rounded-full bg-white px-2 py-1 text-[8.5px] font-bold uppercase text-[#736b5c]">
          {eligibility.balance_source.replace('_', ' ')}
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-[9.5px]">
        <div><dt className="text-[#8a8270]">Dates</dt><dd className="font-semibold text-[#221f1a]">
          {formatDate(eligibility.start_date)}{eligibility.end_date !== eligibility.start_date ? ` – ${formatDate(eligibility.end_date)}` : ''}
        </dd></div>
        <div><dt className="text-[#8a8270]">Working days</dt><dd className="font-semibold text-[#221f1a]">{formatNumber(eligibility.working_day_count)} of {eligibility.calendar_day_count}</dd></div>
        <div><dt className="text-[#8a8270]">Required</dt><dd className="font-semibold text-[#221f1a]">{formatNumber(eligibility.required_leave_units)} days</dd></div>
        <div><dt className="text-[#8a8270]">Available</dt><dd className="font-semibold text-[#221f1a]">
          {typeof eligibility.available_leave_balance === 'number' ? `${formatNumber(eligibility.available_leave_balance)} days` : eligibility.available_leave_balance}
        </dd></div>
      </dl>

      {(eligibility.weekend_dates_excluded.length > 0 || eligibility.company_holidays_excluded.length > 0) && (
        <div className="mt-3 border-t border-[#eee7dc] pt-2 text-[9.5px] text-[#736b5c]">
          {eligibility.weekend_dates_excluded.length > 0 && (
            <p>{eligibility.weekend_dates_excluded.length} weekend/non-working day(s) excluded.</p>
          )}
          {eligibility.company_holidays_excluded.map((holiday) => (
            <p key={holiday.date}>{holiday.label || 'Company holiday'} · {formatDate(holiday.date)}</p>
          ))}
        </div>
      )}

      {eligibility.existing_overlaps.length > 0 && (
        <div className="mt-2 rounded-lg bg-[#fbeee1] px-2.5 py-2 text-[9.5px] text-[#7f552c]">
          {eligibility.existing_overlaps.length} pending/approved request(s) overlap this period.
        </div>
      )}
      {eligibility.blocking_reasons.length > 0 && (
        <ul className="mt-2 space-y-1" aria-label="Blocking reasons">
          {eligibility.blocking_reasons.map((reason) => (
            <li key={reason.code} className="text-[9.5px] text-[#a43f36]">• {reason.message}</li>
          ))}
        </ul>
      )}
      {eligibility.warnings.length > 0 && (
        <ul className="mt-2 space-y-1" aria-label="Eligibility warnings">
          {eligibility.warnings.map((item) => (
            <li key={item.code} className="text-[9.5px] text-[#986918]">• {item.message}</li>
          ))}
        </ul>
      )}
      {eligibility.current_approver && (
        <div className="mt-2 text-[9px] text-[#8a8270]">Current approver: {eligibility.current_approver}</div>
      )}
      {correlationId && (
        <div className="mt-2 text-[8px] text-[#a99e8a]">Reference: {correlationId}</div>
      )}
    </section>
  );
}

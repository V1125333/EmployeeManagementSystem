import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, BarChart3, Check, CheckCircle2, ChevronLeft, ChevronRight,
  Copy, Minus, Plus, RefreshCw, UserRound, X,
} from 'lucide-react';

import { Badge, Button, Card } from '@/components/ui';
import { authenticatedFetch } from '@/services/apiClient';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const JSON_HEADERS = { 'Content-Type': 'application/json' };
const PROJECT_COLORS = [
  'var(--color-brand-orange)',
  'var(--color-brand-navy)',
  'var(--color-status-success)',
  'var(--color-status-warning)',
  'var(--color-status-info)',
];

interface TimesheetOption {
  id: string | null;
  allocation_id?: string | null;
  name: string;
  code: string;
  group?: string;
  allocation_percentage?: number | null;
  allocation_role?: string | null;
  allocation_start_date?: string | null;
  allocation_end_date?: string | null;
  disabled?: boolean;
}

interface TimesheetEntry {
  id: string;
  work_date: string;
  entry_code: string;
  project_id: string | null;
  project_name: string;
  hours: number;
  status: string;
}

interface LeaveDay {
  date: string;
  status: string;
  leave_type: string;
  hours: number;
}

interface TimesheetWeek {
  week_start: string;
  week_end: string;
  status: string;
  total_hours: number;
  working_hours: number;
  leave_hours: number;
  overtime_hours: number;
  weekly_limit_hours: number;
  submitted_to?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  reviewer_notes?: string | null;
  warnings: string[];
  entries: TimesheetEntry[];
  leave_days: LeaveDay[];
  non_working_days?: string[];
}

interface WorkItem {
  key: string;
  projectId: string | null;
  name: string;
  code: string;
  allocation: number | null;
  allocationRole?: string | null;
  activeFrom?: string | null;
  activeTo?: string | null;
  kind: 'project' | 'training' | 'bench' | 'internal';
  hours: Record<string, number>;
}

type AddType = 'project' | 'leave' | 'training' | 'bench';

function addDays(date: Date, days: number) {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

function dateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function startOfWeek(date = new Date()) {
  const copy = new Date(date);
  const day = copy.getDay();
  copy.setDate(copy.getDate() - ((day + 6) % 7));
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function weekLabel(startValue: string) {
  const start = new Date(`${startValue}T00:00:00`);
  const end = addDays(start, 6);
  return `${start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
}

function displayHours(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '');
}

function sumHours(values: number[]) {
  return Math.round(values.reduce((sum, value) => sum + value, 0) * 100) / 100;
}

function clampHours(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.round(Math.min(16, Math.max(0, value)) * 100) / 100;
}

function isWeekend(day: string) {
  const weekday = new Date(`${day}T00:00:00`).getDay();
  return weekday === 0 || weekday === 6;
}

function distributeWeeklyHours(
  total: number,
  item: WorkItem,
  days: string[],
  unavailableDays: Set<string>,
  leaveByDay: Map<string, LeaveDay>,
) {
  const eligible = days.filter((day) => !isWeekend(day) && !unavailableDays.has(day)
    && (!item.activeFrom || day >= item.activeFrom)
    && (!item.activeTo || day <= item.activeTo)
    && (leaveByDay.get(day)?.hours || 0) < 8);
  const result = Object.fromEntries(days.map((day) => [day, 0]));
  if (!eligible.length) return result;
  const capacities = eligible.map((day) => Math.max(0, 8 - (leaveByDay.get(day)?.hours || 0)));
  const totalCapacity = capacities.reduce((sum, capacity) => sum + capacity, 0);
  const requested = Math.max(0, Math.min(80, total));
  let distributed = 0;
  eligible.forEach((day, index) => {
    const raw = requested <= totalCapacity
      ? requested * capacities[index] / Math.max(1, totalCapacity)
      : capacities[index] + (requested - totalCapacity) / eligible.length;
    const value = index === eligible.length - 1 ? requested - distributed : Math.round(raw * 100) / 100;
    result[day] = Math.max(0, Math.min(16, Math.round(value * 100) / 100));
    distributed += result[day];
  });
  return result;
}

function endTimeForHours(hours: number) {
  const minutes = Math.min(23 * 60 + 59, Math.round(hours * 60));
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

function isDateActive(option: TimesheetOption, day: string) {
  return (!option.allocation_start_date || day >= option.allocation_start_date)
    && (!option.allocation_end_date || day <= option.allocation_end_date);
}

function optionKey(option: TimesheetOption) {
  return option.allocation_id || option.id || option.code;
}

function makeAllocationDefaults(options: TimesheetOption[], week: TimesheetWeek, days: string[]): WorkItem[] {
  const unavailable = new Set([...days.filter(isWeekend), ...(week.non_working_days || [])]);
  const leaveHours = new Map(week.leave_days.map((leave) => [leave.date, leave.hours]));
  const allocations = options.filter((option) => option.id && option.allocation_percentage && !option.disabled);
  const rows: WorkItem[] = allocations.map((option) => ({
    key: optionKey(option),
    projectId: option.id,
    name: option.name,
    code: 'PRJ',
    allocation: option.allocation_percentage || 0,
    allocationRole: option.allocation_role,
    activeFrom: option.allocation_start_date,
    activeTo: option.allocation_end_date,
    kind: 'project',
    hours: Object.fromEntries(days.map((day) => {
      const available = unavailable.has(day) ? 0 : Math.max(0, 8 - (leaveHours.get(day) || 0));
      return [day, isDateActive(option, day) ? clampHours(available * (option.allocation_percentage || 0) / 100) : 0];
    })),
  }));

  const benchHours = Object.fromEntries(days.map((day) => {
    if (unavailable.has(day)) return [day, 0];
    const available = Math.max(0, 8 - (leaveHours.get(day) || 0));
    const allocated = rows.reduce((sum, row) => sum + (row.hours[day] || 0), 0);
    return [day, clampHours(Math.max(0, available - allocated))];
  }));
  if (!rows.length || Object.values(benchHours).some((hours) => hours > 0)) {
    rows.push({ key: 'BENCH', projectId: null, name: 'Bench / Internal', code: 'POC', allocation: rows.length ? null : 100, kind: 'bench', hours: benchHours });
  }
  return rows;
}

function rowsFromWeek(options: TimesheetOption[], week: TimesheetWeek, days: string[]) {
  if (!week.entries.length) return makeAllocationDefaults(options, week, days);
  const groups = new Map<string, WorkItem>();
  week.entries.forEach((entry) => {
    const allocation = entry.project_id
      ? options.find((option) => option.id === entry.project_id && isDateActive(option, entry.work_date))
      : options.find((option) => option.code === entry.entry_code);
    const key = allocation ? optionKey(allocation) : entry.project_id || entry.entry_code;
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        projectId: entry.project_id,
        name: entry.project_name,
        code: entry.entry_code,
        allocation: allocation?.allocation_percentage ?? null,
        allocationRole: allocation?.allocation_role,
        activeFrom: allocation?.allocation_start_date,
        activeTo: allocation?.allocation_end_date,
        kind: entry.project_id ? 'project' : entry.entry_code === 'TRN' ? 'training' : entry.entry_code === 'POC' ? 'bench' : 'internal',
        hours: Object.fromEntries(days.map((day) => [day, 0])),
      });
    }
    groups.get(key)!.hours[entry.work_date] = clampHours((groups.get(key)!.hours[entry.work_date] || 0) + Number(entry.hours));
  });
  return Array.from(groups.values());
}

function StatusTimeline({ status }: { status: string }) {
  const normalized = status === 'not_started' || status === 'rejected' ? 'draft' : status;
  const stages = ['draft', 'submitted', 'in_progress', 'approved'];
  const current = Math.max(0, stages.indexOf(normalized));
  return (
    <div className="grid grid-cols-4 gap-0" aria-label={`Timesheet status: ${normalized.replace('_', ' ')}`}>
      {stages.map((stage, index) => (
        <div key={stage} className="relative flex flex-col items-center text-center">
          {index > 0 && <span className={cn('absolute right-1/2 top-3 h-0.5 w-full', index <= current ? 'bg-accent' : 'bg-[var(--color-border)]')} />}
          <span className={cn('relative z-10 flex h-6 w-6 items-center justify-center rounded-full border text-[10px] font-bold', index < current ? 'border-accent bg-accent text-white' : index === current ? 'border-accent bg-accent-light text-accent' : 'border-[var(--color-border)] bg-warm-card text-gray-400')}>
            {index < current ? <Check size={12} /> : index + 1}
          </span>
          <span className={cn('mt-2 text-[10px] font-semibold sm:text-xs', index === current ? 'text-[var(--color-brand-navy)]' : 'text-gray-400')}>{stage.replace('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())}</span>
        </div>
      ))}
    </div>
  );
}

function HourControl({ value, disabled, label, onChange }: { value: number; disabled: boolean; label: string; onChange: (value: number) => void }) {
  return (
    <div className={cn('flex h-10 items-center overflow-hidden rounded-btn border bg-warm-card', disabled ? 'border-[var(--color-border)] bg-warm-bg opacity-55' : 'border-[var(--color-border)] focus-within:border-accent')}>
      <button type="button" disabled={disabled || value <= 0} onClick={() => onChange(Math.max(0, Math.round((value - 1) * 100) / 100))} className="flex h-full w-9 shrink-0 items-center justify-center text-gray-400 hover:bg-hover-bg hover:text-accent disabled:opacity-30" aria-label={`Decrease ${label}`}><Minus size={13} /></button>
      <input aria-label={label} type="number" min="0" max="80" step="0.5" disabled={disabled} value={value} onChange={(event) => onChange(Math.max(0, Math.min(80, Number(event.target.value) || 0)))} className="h-full min-w-0 flex-1 bg-transparent text-center text-base font-bold text-[var(--color-brand-navy)] outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none" />
      <span className="text-xs font-semibold text-gray-400">h</span>
      <button type="button" disabled={disabled || value >= 80} onClick={() => onChange(Math.min(80, Math.round((value + 1) * 100) / 100))} className="flex h-full w-9 shrink-0 items-center justify-center text-gray-400 hover:bg-hover-bg hover:text-accent disabled:opacity-30" aria-label={`Increase ${label}`}><Plus size={13} /></button>
    </div>
  );
}

export function HourCentricTimesheetsPage() {
  const initialWeek = dateKey(startOfWeek());
  const [weekStart, setWeekStart] = useState(initialWeek);
  const [options, setOptions] = useState<TimesheetOption[]>([]);
  const [week, setWeek] = useState<TimesheetWeek | null>(null);
  const [items, setItems] = useState<WorkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<'draft' | 'submit' | 'copy' | 'recall' | null>(null);
  const [message, setMessage] = useState<{ tone: 'success' | 'error' | 'warning'; text: string } | null>(null);
  const [manualReview, setManualReview] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [addType, setAddType] = useState<AddType>('project');
  const [addProjectId, setAddProjectId] = useState('');

  const weekDays = useMemo(() => {
    const start = new Date(`${weekStart}T00:00:00`);
    return Array.from({ length: 7 }, (_, index) => addDays(start, index));
  }, [weekStart]);
  const dayKeys = useMemo(() => weekDays.map(dateKey), [weekDays]);
  const weekDayKeys = dayKeys.slice(0, 5);

  const loadWeek = useCallback(async () => {
    setLoading(true);
    setMessage(null);
    try {
      const [optionsResponse, weekResponse] = await Promise.all([
        authenticatedFetch(`${API_BASE}/timesheets/me/options?week_start=${weekStart}`),
        authenticatedFetch(`${API_BASE}/timesheets/me/week?week_start=${weekStart}`),
      ]);
      const optionsData = await optionsResponse.json().catch(() => null);
      const weekData = await weekResponse.json().catch(() => null);
      if (!optionsResponse.ok) throw new Error(optionsData?.detail || 'Could not load allocation options.');
      if (!weekResponse.ok) throw new Error(weekData?.detail || 'Could not load this timesheet.');
      const nextOptions = (optionsData.projects || []) as TimesheetOption[];
      const nextWeek = weekData as TimesheetWeek;
      setOptions(nextOptions);
      setWeek(nextWeek);
      setItems(rowsFromWeek(nextOptions, nextWeek, dayKeys));
      setAddProjectId(nextOptions.find((option) => option.id && !option.disabled)?.id || '');
      setManualReview(false);
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'Could not load this timesheet.' });
    } finally {
      setLoading(false);
    }
  }, [dayKeys, weekStart]);

  useEffect(() => { void loadWeek(); }, [loadWeek]);

  const unavailableDays = useMemo(() => new Set([...dayKeys.filter(isWeekend), ...(week?.non_working_days || [])]), [dayKeys, week?.non_working_days]);
  const leaveByDay = useMemo(() => new Map((week?.leave_days || []).map((leave) => [leave.date, leave])), [week?.leave_days]);
  const locked = week?.status === 'submitted' || week?.status === 'approved' || week?.status === 'in_progress';
  const defaults = useMemo(() => week ? makeAllocationDefaults(options, week, dayKeys) : [], [dayKeys, options, week]);

  const setWeeklyHours = (key: string, value: number) => {
    setItems((current) => current.map((item) => item.key === key ? {
      ...item,
      hours: distributeWeeklyHours(value, item, dayKeys, unavailableDays, leaveByDay),
    } : item));
    setMessage(null);
  };
  const workHours = sumHours(items.map((item) => sumHours(Object.values(item.hours))));
  const leaveHours = (week?.leave_days || []).reduce((sum, leave) => sum + leave.hours, 0);
  const leaveLabel = Array.from(new Set((week?.leave_days || []).map((leave) => leave.leave_type))).join(' / ') || 'Leave / PTO';
  const leaveStatus = (week?.leave_days || []).some((leave) => leave.status === 'pending') ? 'pending leave' : 'approved leave';
  const accountedHours = workHours + leaveHours;
  const targetHours = week?.weekly_limit_hours || 40;
  const leavePercent = Math.min(100, targetHours ? leaveHours / targetHours * 100 : 0);
  const overtime = Math.max(0, accountedHours - targetHours);
  const remaining = Math.max(0, targetHours - accountedHours);
  const matchesDefaults = useMemo(() => {
    const values = (rows: WorkItem[]) => rows.flatMap((row) => weekDayKeys.map((day) => `${row.key}:${day}:${row.hours[day] || 0}`)).sort().join('|');
    return values(items) === values(defaults);
  }, [defaults, items, weekDayKeys]);
  const quickSubmitChecked = matchesDefaults && !manualReview;
  const status = !week?.status || week.status === 'not_started' ? 'draft' : week.status;
  const statusVariant = status === 'approved' ? 'success' : status === 'rejected' ? 'error' : status === 'draft' ? 'neutral' : 'warning';

  const useAllocation = () => {
    setItems(defaults.map((item) => ({ ...item, hours: { ...item.hours } })));
    setManualReview(false);
    setMessage({ tone: 'success', text: 'Allocation defaults restored. Review the totals and submit when ready.' });
  };
  const addItem = () => {
    if (addType === 'leave') {
      setMessage(week?.leave_days.length
        ? { tone: 'success', text: 'Approved leave is already included automatically in the weekly totals.' }
        : { tone: 'warning', text: 'No approved or pending leave exists this week. Submit a leave request from Apply Leave first.' });
      setAddOpen(false);
      return;
    }
    let next: WorkItem | null = null;
    if (addType === 'project') {
      const option = options.find((candidate) => candidate.id === addProjectId);
      if (option) next = { key: `extra-${option.id}-${Date.now()}`, projectId: option.id, name: option.name, code: 'PRJ', allocation: option.allocation_percentage ?? null, kind: 'project', hours: Object.fromEntries(dayKeys.map((day) => [day, 0])) };
    } else if (addType === 'training') {
      next = { key: `training-${Date.now()}`, projectId: null, name: 'Training', code: 'TRN', allocation: null, kind: 'training', hours: Object.fromEntries(dayKeys.map((day) => [day, 0])) };
    } else {
      next = { key: `bench-${Date.now()}`, projectId: null, name: 'Bench / Internal', code: 'POC', allocation: null, kind: 'bench', hours: Object.fromEntries(dayKeys.map((day) => [day, 0])) };
    }
    if (!next) return;
    setItems((current) => [...current, next!]);
    setAddOpen(false);
  };

  const payload = () => ({
    week_start: weekStart,
    time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
    entries: items.flatMap((item) => dayKeys.flatMap((day) => {
      const hours = item.hours[day] || 0;
      if (!hours || unavailableDays.has(day) || leaveByDay.get(day)?.hours === 8) return [];
      return [{ work_date: day, entry_code: item.code, project_id: item.projectId, project_name: item.name, start_time: '00:00', end_time: endTimeForHours(hours), notes: null }];
    })),
  });

  const save = async (mode: 'draft' | 'submit') => {
    setSaving(mode);
    setMessage(null);
    try {
      const response = await authenticatedFetch(`${API_BASE}/timesheets/me/week${mode === 'submit' ? '/submit' : ''}`, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(payload()) });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || `Could not ${mode === 'submit' ? 'submit' : 'save'} the timesheet.`);
      const nextWeek = data as TimesheetWeek;
      setWeek(nextWeek);
      setItems(rowsFromWeek(options, nextWeek, dayKeys));
      setMessage({ tone: 'success', text: mode === 'submit' ? 'Timesheet submitted for approval.' : 'Timesheet draft saved.' });
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'Could not save the timesheet.' });
    } finally {
      setSaving(null);
    }
  };

  const copyPrevious = async () => {
    setSaving('copy');
    setMessage(null);
    try {
      const source = dateKey(addDays(new Date(`${weekStart}T00:00:00`), -7));
      const response = await authenticatedFetch(`${API_BASE}/timesheets/me/week/copy`, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ source_week_start: source, target_week_start: weekStart, time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' }) });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || 'Could not copy the previous week.');
      setWeek(data);
      setItems(rowsFromWeek(options, data, dayKeys));
      setMessage({ tone: 'success', text: 'Previous week copied. Review exceptions, then submit.' });
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'Could not copy the previous week.' });
    } finally { setSaving(null); }
  };

  const recall = async () => {
    setSaving('recall');
    setMessage(null);
    try {
      const params = new URLSearchParams({ week_start: weekStart, time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' });
      const response = await authenticatedFetch(`${API_BASE}/timesheets/me/week/recall?${params}`, { method: 'POST' });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || 'Could not recall the timesheet.');
      setWeek(data);
      setItems(rowsFromWeek(options, data, dayKeys));
      setMessage({ tone: 'success', text: 'Submission recalled. You can amend and resubmit it.' });
    } catch (error) {
      setMessage({ tone: 'error', text: error instanceof Error ? error.message : 'Could not recall the timesheet.' });
    } finally { setSaving(null); }
  };

  const allocationCount = options.filter((option) => option.id && option.allocation_percentage).length;
  const reconciliation = overtime > 0 ? `${displayHours(overtime)}h over target` : remaining > 0 ? `${displayHours(remaining)}h short` : 'target reached';

  return (
    <div className="animate-fade-up text-[var(--color-brand-navy)]">
      <header className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight">Timesheet</h1><p className="mt-1 text-sm text-gray-500">Your allocated week is ready. Adjust only what changed.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex h-10 items-center overflow-hidden rounded-btn border border-[var(--color-border)] bg-warm-card">
            <button type="button" disabled={!!saving} onClick={() => setWeekStart(dateKey(addDays(new Date(`${weekStart}T00:00:00`), -7)))} className="h-full px-3 text-gray-500 hover:bg-hover-bg" aria-label="Previous week"><ChevronLeft size={15} /></button>
            <label className="flex h-full items-center border-x border-[var(--color-border)] px-3"><input type="date" value={weekStart} onChange={(event) => setWeekStart(dateKey(startOfWeek(new Date(`${event.target.value}T00:00:00`))))} className="w-0 opacity-0" aria-label="Select week" /><span className="whitespace-nowrap text-sm font-bold">{weekLabel(weekStart)}</span></label>
            <button type="button" disabled={!!saving} onClick={() => setWeekStart(dateKey(addDays(new Date(`${weekStart}T00:00:00`), 7)))} className="h-full px-3 text-gray-500 hover:bg-hover-bg" aria-label="Next week"><ChevronRight size={15} /></button>
          </div>
          <Button variant="ghost" icon={<Copy size={14} />} disabled={!!saving || locked} onClick={copyPrevious}>{saving === 'copy' ? 'Copying…' : 'Copy Previous Week'}</Button>
          <Badge variant={statusVariant}>{status.replace('_', ' ')}</Badge>
        </div>
      </header>

      {message && <div className={cn('mb-5 rounded-xl border px-4 py-3 text-sm', message.tone === 'success' ? 'border-status-success/20 bg-[var(--color-status-success-bg)] text-status-success' : message.tone === 'error' ? 'border-status-error/20 bg-[var(--color-status-error-bg)] text-status-error' : 'border-status-warning/20 bg-[var(--color-status-warning-bg)] text-status-warning')}>{message.text}</div>}

      <Card className="mb-4 overflow-hidden">
        <div className="grid items-center lg:grid-cols-[minmax(300px,.9fr)_minmax(360px,1.2fr)_auto]">
          <label className={cn('flex min-h-[76px] items-center gap-3 px-4 py-3 sm:px-5', locked ? 'cursor-not-allowed opacity-60' : 'cursor-pointer')}>
            <input type="checkbox" checked={quickSubmitChecked} disabled={locked || !matchesDefaults} onChange={(event) => setManualReview(!event.target.checked)} className="h-5 w-5 shrink-0 rounded accent-[var(--color-accent)]" />
            <span className="min-w-0"><span className="block text-sm font-bold">Submit default timesheet</span><span className="mt-0.5 block text-xs text-gray-500">{matchesDefaults ? 'Allocation hours are ready to submit.' : 'Manual changes detected — review before submitting.'}</span></span>
          </label>
          <div className="flex min-h-[76px] items-center gap-3 border-t border-[var(--color-border)] px-4 py-3 sm:px-5 lg:border-l lg:border-t-0">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-light text-accent"><UserRound size={16} /></span>
            <div className="min-w-0"><div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500"><span>Approver</span><strong className="text-[var(--color-brand-navy)]">{week?.submitted_to || 'Not assigned'}</strong></div><div className="mt-1 text-sm font-semibold text-gray-500">{allocationCount ? `${allocationCount} allocation${allocationCount === 1 ? '' : 's'} configured` : 'No project allocations'}</div></div>
          </div>
          <div className="flex min-h-[60px] items-center justify-end border-t border-[var(--color-border)] px-4 py-3 sm:px-5 lg:min-h-[76px] lg:border-l lg:border-t-0">
            <Button size="sm" variant="soft" icon={<RefreshCw size={14} />} disabled={locked || loading} onClick={useAllocation}>Use My Allocation</Button>
          </div>
        </div>
      </Card>

      <div className="mb-5 grid items-stretch gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
      <Card className="h-full overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-[var(--color-border)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div><h2 className="text-base font-bold">Work items</h2><p className="mt-1 text-xs text-gray-500">Allocation hours are pre-filled. Adjust each weekly total directly or use ± 1h.</p></div>
          {!locked && <Button size="sm" icon={<Plus size={14} />} onClick={() => setAddOpen((open) => !open)}>Add Task</Button>}
        </div>
        {addOpen && <div className="grid gap-3 border-b border-[var(--color-border)] bg-warm-bg p-4 sm:grid-cols-[180px_minmax(0,1fr)_auto]">
          <select value={addType} onChange={(event) => setAddType(event.target.value as AddType)} className="h-10 rounded-btn border border-[var(--color-border)] bg-warm-card px-3 text-sm font-semibold outline-none focus:border-accent"><option value="project">Project / Task</option><option value="leave">Leave / PTO</option><option value="training">Training</option><option value="bench">Bench / Internal</option></select>
          {addType === 'project' ? <select value={addProjectId} onChange={(event) => setAddProjectId(event.target.value)} className="h-10 rounded-btn border border-[var(--color-border)] bg-warm-card px-3 text-sm outline-none focus:border-accent">{options.filter((option) => option.id && !option.disabled).map((option) => <option key={`${optionKey(option)}-add`} value={option.id || ''}>{option.name}{option.allocation_percentage ? ` · ${option.allocation_percentage}% allocation` : ''}</option>)}</select> : <div className="flex h-10 items-center rounded-btn border border-[var(--color-border)] bg-warm-card px-3 text-sm text-gray-500">{addType === 'leave' ? 'Approved leave is synchronized automatically' : addType === 'training' ? 'Training / learning activity' : 'Bench, internal, or unallocated work'}</div>}
          <div className="flex gap-2"><Button size="sm" onClick={addItem}>Add row</Button><button type="button" onClick={() => setAddOpen(false)} className="flex h-9 w-9 items-center justify-center rounded-btn text-gray-400 hover:bg-warm-card" aria-label="Cancel add task"><X size={15} /></button></div>
        </div>}

        <div className="space-y-3 p-4 sm:p-5">
          {loading ? <div className="py-10 text-center text-sm text-gray-500">Preparing your allocated work items…</div> : items.map((item, itemIndex) => {
            const weeklyHours = sumHours(Object.values(item.hours));
            const fillPercent = Math.min(100, targetHours ? weeklyHours / targetHours * 100 : 0);
            const itemColor = PROJECT_COLORS[itemIndex % PROJECT_COLORS.length];
            return <div key={item.key} className="grid items-center gap-3 sm:grid-cols-[minmax(0,760px)_170px_36px]">
              <div className="relative min-h-[52px] overflow-hidden rounded-xl border border-[var(--color-border)] bg-warm-bg">
                <span className="absolute inset-y-0 left-0 transition-[width] duration-200" style={{ width: `${fillPercent}%`, background: `color-mix(in srgb, ${itemColor} 18%, var(--color-brand-surface))`, borderLeft: `5px solid ${itemColor}` }} />
                <div className="relative flex min-h-[52px] items-center justify-between gap-3 px-4 py-2.5">
                  <div className="min-w-0 truncate text-sm font-bold">{item.name}{item.allocation !== null && <span className="font-semibold text-accent"> — {item.allocation}%</span>}{item.activeFrom && item.activeTo && <span className="ml-2 text-[10px] font-normal text-gray-500">Active {item.activeFrom.slice(5)}–{item.activeTo.slice(5)}</span>}</div>
                  <span className="shrink-0 text-xs font-semibold text-gray-500">{Math.round(fillPercent)}% of target</span>
                </div>
              </div>
              <HourControl value={weeklyHours} disabled={Boolean(locked)} label={`${item.name} weekly hours`} onChange={(value) => setWeeklyHours(item.key, value)} />
              <button type="button" disabled={locked} onClick={() => setItems((current) => current.filter((row) => row.key !== item.key))} className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 hover:bg-[var(--color-status-error-bg)] hover:text-status-error disabled:opacity-30" aria-label={`Remove ${item.name}`}><X size={15} /></button>
            </div>;
          })}
          {!!week?.leave_days.length && <div className="grid items-center gap-3 sm:grid-cols-[minmax(0,760px)_170px_36px]">
            <div className="relative min-h-[52px] overflow-hidden rounded-xl border border-[var(--color-border)] bg-warm-bg">
              <span className="absolute inset-y-0 left-0 border-l-[5px] border-status-info bg-[var(--color-status-info-bg)] transition-[width] duration-200" style={{ width: `${leavePercent}%` }} />
              <div className="relative flex min-h-[52px] items-center justify-between gap-3 px-4 py-2.5">
                <div className="min-w-0 truncate text-sm font-bold">{leaveLabel}<span className="font-semibold text-status-info"> — {displayHours(leavePercent)}%</span><span className="ml-2"><Badge variant={leaveStatus === 'pending leave' ? 'warning' : 'info'}>{leaveStatus}</Badge></span></div>
                <span className="shrink-0 text-xs font-semibold text-gray-500">{displayHours(leavePercent)}% of target</span>
              </div>
            </div>
            <div className="flex h-10 items-center justify-center rounded-btn border border-[var(--color-border)] bg-[var(--color-status-info-bg)] text-base font-bold text-status-info" aria-label={`${leaveLabel} weekly hours`}>{displayHours(leaveHours)}<span className="ml-1 text-xs">h</span></div>
            <div />
          </div>}
          {!loading && <div className="flex flex-col gap-2 border-t border-[var(--color-border)] pt-4 sm:flex-row sm:items-center sm:justify-between"><div className="text-xs text-gray-500">Weekly hours are distributed across eligible working dates automatically.</div><div className="text-sm font-bold">Total <span className="ml-2 text-lg text-accent">{displayHours(accountedHours)}h</span></div></div>}
        </div>
      </Card>

      <Card className="h-full p-4 sm:p-5">
        <h2 className="mb-4 text-base font-bold">Weekly totals</h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
          {[
            { label: 'Hours logged', value: accountedHours, detail: leaveHours ? `includes ${displayHours(leaveHours)}h leave` : 'live total', variant: 'neutral' },
            { label: 'Overtime', value: overtime, detail: overtime ? 'non-blocking flag' : 'within target', variant: overtime ? 'warning' : 'success' },
            { label: 'Target hours', value: targetHours, detail: unavailableDays.size > 2 ? 'holidays excluded' : 'this week', variant: 'neutral' },
            { label: 'Remaining', value: remaining, detail: remaining ? 'to target' : overtime ? 'target exceeded' : 'target reached', variant: remaining ? 'warning' : 'success' },
          ].map((metric) => <div key={metric.label} className="rounded-xl border border-[var(--color-border)] bg-warm-bg px-4 py-3.5"><div className="flex items-center justify-between"><span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{metric.label}</span>{metric.variant !== 'neutral' && <span className={cn('h-2 w-2 rounded-full', metric.variant === 'warning' ? 'bg-status-warning' : 'bg-status-success')} />}</div><div className="mt-1.5 flex items-baseline gap-2"><strong className="text-2xl tracking-tight">{displayHours(metric.value)}h</strong><span className="text-[11px] text-gray-500">{metric.detail}</span></div></div>)}
        </div>
      </Card>
      </div>

      <div className="mb-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <Card className="p-5 sm:p-6"><div className="mb-5 flex items-center gap-2 text-base font-bold"><BarChart3 size={17} className="text-accent" /> Weekly distribution</div><div className="flex h-5 overflow-hidden rounded-full bg-warm-bg">{items.map((item, index) => { const hours = sumHours(Object.values(item.hours)); return <span key={item.key} style={{ width: `${accountedHours ? hours / accountedHours * 100 : 0}%`, background: PROJECT_COLORS[index % PROJECT_COLORS.length] }} title={`${item.name}: ${displayHours(hours)}h`} />; })}{leaveHours > 0 && <span className="bg-status-info" style={{ width: `${accountedHours ? leaveHours / accountedHours * 100 : 0}%` }} title={`${leaveLabel}: ${displayHours(leaveHours)}h`} />}</div><div className="mt-5 grid gap-2 sm:grid-cols-2">{items.map((item, index) => <div key={item.key} className="flex items-center justify-between gap-3 text-xs"><span className="flex min-w-0 items-center gap-2"><i className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: PROJECT_COLORS[index % PROJECT_COLORS.length] }} /><span className="truncate text-gray-500">{item.name}</span></span><strong>{displayHours(sumHours(Object.values(item.hours)))}h</strong></div>)}{leaveHours > 0 && <div className="flex items-center justify-between gap-3 text-xs"><span className="flex items-center gap-2 text-gray-500"><i className="h-2.5 w-2.5 rounded-sm bg-status-info" />{leaveLabel}</span><strong>{displayHours(leaveHours)}h</strong></div>}</div></Card>
        <Card className="p-5 sm:p-6"><div className="mb-6 text-base font-bold">Approval progress</div><StatusTimeline status={status} />{overtime > 0 && <div className="mt-6 flex gap-3 rounded-xl bg-[var(--color-status-warning-bg)] p-3 text-xs text-status-warning"><AlertTriangle size={16} className="shrink-0" /><span><strong>{displayHours(overtime)}h overtime flagged.</strong> This does not block submission and will be visible to your approver.</span></div>}{week?.reviewer_notes && <div className="mt-4 rounded-xl bg-warm-bg p-3 text-xs text-gray-500"><strong className="text-[var(--color-brand-navy)]">Manager note:</strong> {week.reviewer_notes}</div>}</Card>
      </div>

      <footer className="flex flex-col gap-4 rounded-2xl border border-[var(--color-border)] bg-warm-card px-5 py-4 shadow-card sm:flex-row sm:items-center sm:justify-between">
        <div><div className="text-sm">You&apos;ve logged <strong>{displayHours(accountedHours)}h of {displayHours(targetHours)}h</strong> — <span className={cn('font-bold', overtime ? 'text-status-warning' : remaining ? 'text-accent' : 'text-status-success')}>{reconciliation}</span>.</div><div className="mt-1 text-xs text-gray-500">Weekends and company holidays are excluded from the target.</div></div>
        <div className="flex shrink-0 flex-wrap gap-2">{status === 'submitted' ? <Button variant="ghost" icon={<RefreshCw size={14} />} disabled={!!saving} onClick={recall}>{saving === 'recall' ? 'Recalling…' : 'Reopen for Amendment'}</Button> : status === 'approved' ? <Badge variant="success"><CheckCircle2 size={12} className="mr-1" />Approved</Badge> : <><Button variant="ghost" disabled={!!saving || !items.length} onClick={() => save('draft')}>{saving === 'draft' ? 'Saving…' : 'Save Draft'}</Button><Button icon={<CheckCircle2 size={14} />} disabled={!!saving || !items.length} onClick={() => save('submit')}>{saving === 'submit' ? 'Submitting…' : 'Submit for Approval'}</Button></>}</div>
      </footer>
    </div>
  );
}

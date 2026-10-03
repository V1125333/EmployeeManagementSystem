export interface LeaveRequestRange {
  id: string;
  status: string;
  start_date: string;
  end_date: string;
}

export function apiErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') return fallback;
  const response = payload as { detail?: unknown; message?: unknown };
  if (typeof response.detail === 'string' && response.detail.trim()) return response.detail;
  if (response.detail && typeof response.detail === 'object' && !Array.isArray(response.detail)) {
    const detail = response.detail as { message?: unknown; msg?: unknown };
    if (typeof detail.message === 'string' && detail.message.trim()) return detail.message;
    if (typeof detail.msg === 'string' && detail.msg.trim()) return detail.msg;
  }
  if (Array.isArray(response.detail)) {
    const messages = response.detail
      .map((item) => item && typeof item === 'object' && 'msg' in item ? String(item.msg) : '')
      .filter(Boolean);
    if (messages.length) return messages.join(' ');
  }
  return typeof response.message === 'string' && response.message.trim() ? response.message : fallback;
}

export function findOverlappingLeaveRequest<T extends LeaveRequestRange>(
  requests: T[],
  startDate: string,
  endDate: string,
  excludeRequestId?: string | null,
): T | undefined {
  if (!startDate || !endDate || endDate < startDate) return undefined;
  return requests.find((request) => (
    request.id !== excludeRequestId
    && ['pending', 'approved'].includes(request.status)
    && request.start_date <= endDate
    && request.end_date >= startDate
  ));
}


export interface LeaveRequestRange {
  id: string;
  status: string;
  start_date: string;
  end_date: string;
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

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { authenticatedFetch } from '@/services/apiClient';
import { HourCentricTimesheetsPage } from '@/pages/timesheets/HourCentricTimesheetsPage';

vi.mock('@/services/apiClient', () => ({ authenticatedFetch: vi.fn() }));

const monday = (() => {
  const date = new Date();
  const offset = (date.getDay() + 6) % 7;
  date.setDate(date.getDate() - offset);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
})();

describe('hour-centric timesheet', () => {
  beforeEach(() => {
    vi.mocked(authenticatedFetch).mockImplementation(async (url) => {
      if (String(url).includes('/options')) {
        return new Response(JSON.stringify({
          projects: [
            { id: 'analytics', allocation_id: 'allocation-a', name: 'Analytics', code: 'ANA', allocation_percentage: 70, allocation_role: 'Engineer', allocation_start_date: monday },
            { id: 'platform', allocation_id: 'allocation-b', name: 'Platform', code: 'PLT', allocation_percentage: 20, allocation_role: 'Engineer', allocation_start_date: monday },
          ],
          requires_timesheet: true,
        }), { status: 200 });
      }
      return new Response(JSON.stringify({
        week_start: monday,
        week_end: monday,
        status: 'not_started',
        total_hours: 0,
        working_hours: 0,
        leave_hours: 0,
        overtime_hours: 0,
        weekly_limit_hours: 40,
        submitted_to: 'David Park',
        warnings: [],
        entries: [],
        leave_days: [{ date: monday, status: 'approved', leave_type: 'Casual Leave', hours: 8 }],
        non_working_days: [],
      }), { status: 200 });
    });
  });

  it('opens with allocation-derived project and bench hours ready to submit', async () => {
    render(<HourCentricTimesheetsPage />);

    expect(await screen.findByText('2 allocations configured')).toBeInTheDocument();
    expect(screen.getAllByText('Bench / Internal').length).toBeGreaterThan(0);
    expect(screen.getAllByText('40h', { selector: 'strong' }).length).toBeGreaterThan(0);
    expect(screen.getByRole('checkbox', { name: /submit default timesheet/i })).toBeChecked();
    expect(screen.getByRole('button', { name: 'Submit for Approval' })).toBeEnabled();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', { name: /Analytics weekly hours/i })).toHaveValue(22.4);
    expect(screen.getAllByText('Casual Leave').length).toBeGreaterThan(0);
    expect(screen.getByText('20% of target')).toBeInTheDocument();
    expect(screen.getByLabelText(/Casual Leave weekly hours/i)).toHaveTextContent('8h');
    expect(screen.queryByText('Monday')).not.toBeInTheDocument();
    expect(screen.queryByText('Tuesday')).not.toBeInTheDocument();
    const reconciliation = screen.getByText(/weekends and company holidays are excluded/i).closest('footer');
    expect(reconciliation).not.toHaveClass('sticky');
  });

  it('marks manual review immediately after an hour edit', async () => {
    render(<HourCentricTimesheetsPage />);
    const weeklyInput = await screen.findByRole('spinbutton', { name: /Analytics weekly hours/i });

    fireEvent.change(weeklyInput, { target: { value: '30' } });

    await waitFor(() => expect(screen.getByRole('checkbox', { name: /submit default timesheet/i })).not.toBeChecked());
    expect(screen.getByText(/manual changes detected/i)).toBeInTheDocument();
  });
});

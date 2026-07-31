import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AIChatResponseContent } from './AIChatResponseContent';

const leaveResult = {
  type: 'leave_balance' as const,
  title: 'My leave balance',
  as_of: '2026-07-24T12:00:00Z',
  balances: [{
    leave_type: 'Casual Leave',
    code: 'CL',
    total: 12,
    available: 9,
    used: 2,
    pending: 1,
    source: 'stored_balance' as const,
  }],
};

const request = {
  request_id: 'request-1',
  leave_type: 'Casual Leave',
  start_date: '2026-07-27',
  end_date: '2026-07-27',
  total_days: 1,
  status: 'pending',
  reason: 'Appointment',
  submitted_at: '2026-07-24T12:00:00Z',
  approver: 'David Park',
  pending_duration_days: 1,
  decided_by: null,
  decided_at: null,
  decision_reason: null,
};

describe('AIChatResponseContent', () => {
  it('shows the loading state', () => {
    render(<AIChatResponseContent loading />);
    expect(screen.getByRole('status')).toHaveTextContent('Orbit AI is checking');
  });

  it('renders a grounded leave balance result', () => {
    render(
      <AIChatResponseContent
        status="completed"
        text="You have 9 days available."
        result={leaveResult}
      />,
    );
    expect(screen.getByText('You have 9 days available.')).toBeInTheDocument();
    expect(screen.getByText('Casual Leave')).toBeInTheDocument();
    expect(screen.getByText('9 days')).toBeInTheDocument();
    expect(screen.getByText('Recorded balance · stored_balance')).toBeInTheDocument();
  });

  it('labels unsupported questions without inventing a result', () => {
    render(
      <AIChatResponseContent
        status="unsupported"
        text="This version can only check your own leave balance."
      />,
    );
    expect(screen.getByText('Not available yet')).toBeInTheDocument();
    expect(screen.queryByLabelText('My leave balance')).not.toBeInTheDocument();
  });

  it('shows a safe error and correlation reference', () => {
    render(
      <AIChatResponseContent
        status="failed"
        text="Your leave balance is temporarily unavailable."
        correlationId="corr-123"
      />,
    );
    expect(screen.getByText(/temporarily unavailable/)).toBeInTheDocument();
    expect(screen.getByText('Reference: corr-123')).toBeInTheDocument();
  });

  it('renders a leave balance comparison card', () => {
    render(<AIChatResponseContent status="completed" text="Yes." result={{
      type: 'leave_balance_comparison',
      title: 'Leave balance comparison',
      as_of: '2026-07-24T12:00:00Z',
      comparison: 'at_least',
      balances: leaveResult.balances,
      threshold: 2,
      meets_threshold: true,
      highest: null,
    }} />);
    expect(screen.getByLabelText('Leave balance comparison')).toHaveTextContent('Yes · 2 day threshold');
  });

  it('renders request list and status cards', () => {
    const { rerender } = render(<AIChatResponseContent status="completed" text="Found one." result={{
      type: 'leave_request_list',
      title: 'My leave requests',
      as_of: '2026-07-24T12:00:00Z',
      requests: [request],
      total_matches: 1,
    }} />);
    expect(screen.getByLabelText('My leave requests')).toHaveTextContent('David Park');
    rerender(<AIChatResponseContent status="completed" text="Pending." result={{
      type: 'leave_request_status',
      title: 'Leave request status',
      as_of: '2026-07-24T12:00:00Z',
      request,
    }} />);
    expect(screen.getByLabelText('Leave request status')).toHaveTextContent('pending');
  });

  it('renders rejection and ambiguity cards without inventing a reason', () => {
    const rejected = { ...request, status: 'rejected', approver: null };
    const { rerender } = render(<AIChatResponseContent status="completed" text="No reason." result={{
      type: 'rejection_explanation',
      title: 'Leave decision',
      as_of: '2026-07-24T12:00:00Z',
      request: rejected,
      explanation: 'No rejection reason was recorded.',
      reason_recorded: false,
    }} />);
    expect(screen.getByLabelText('Leave decision')).toHaveTextContent('No reason recorded');
    rerender(<AIChatResponseContent status="needs_clarification" text="Choose one." result={{
      type: 'ambiguous_leave_request',
      title: 'Which leave request did you mean?',
      candidates: [request, { ...request, request_id: 'request-2' }],
    }} />);
    expect(screen.getByLabelText('Which leave request did you mean?')).toHaveTextContent('Casual Leave');
  });

  it('renders a grounded eligibility result with exclusions and correlation ID', () => {
    render(<AIChatResponseContent status="completed" text="You are eligible." correlationId="elig-123" result={{
      type: 'leave_eligibility',
      title: 'Leave eligibility',
      eligibility: {
        tool: 'check_my_leave_eligibility',
        leave_type: 'Casual Leave',
        leave_type_code: 'CL',
        start_date: '2026-08-03',
        end_date: '2026-08-07',
        calendar_day_count: 5,
        working_day_count: 4,
        weekend_dates_excluded: [],
        company_holidays_excluded: [{
          date: '2026-08-05',
          reason: 'company_holiday',
          label: 'Company Day',
        }],
        optional_holiday_treatment: 'not_applicable',
        required_leave_units: 4,
        available_leave_balance: 9,
        balance_source: 'stored_balance',
        existing_overlaps: [],
        policy_checks_performed: [{ code: 'VALID_DATE_RANGE', passed: true }],
        blocking_reasons: [],
        warnings: [],
        eligibility_status: 'eligible',
        current_approver: 'David Park',
        evaluated_at: '2026-07-24T12:00:00Z',
        timezone: 'America/New_York',
      },
    }} />);
    const card = screen.getByLabelText('Leave eligibility result');
    expect(card).toHaveTextContent('Eligible');
    expect(card).toHaveTextContent('4 of 5');
    expect(card).toHaveTextContent('Company Day');
    expect(card).toHaveTextContent('David Park');
    expect(card).toHaveTextContent('elig-123');
  });

  it('renders eligibility clarification without calculating in React', () => {
    render(<AIChatResponseContent status="needs_clarification" text="Which type?" result={{
      type: 'leave_eligibility_clarification',
      title: 'I need one more detail',
      missing_fields: ['leave_type'],
      prompt: 'Which leave type should I check?',
    }} />);
    expect(screen.getByLabelText('I need one more detail')).toHaveTextContent('Leave type');
    expect(screen.getByLabelText('I need one more detail')).toHaveTextContent('Which leave type');
  });

  it('renders a principal-bound conversational leave intake question', () => {
    render(<AIChatResponseContent status="needs_clarification" text="Which leave type?" result={{
      type: 'leave_intake_question',
      title: 'Preparing your leave',
      field: 'leave_type',
      prompt: 'Which leave type would you like to use?',
      intake: {
        goal: 'prepare_leave_request',
        collected_fields: {
          leave_type: null,
          start_date: '2026-08-03',
          end_date: '2026-08-04',
          duration_days: null,
          reason: null,
          reason_skipped: false,
          reason_prompted: false,
          supporting_information: null,
        },
        missing_required_fields: ['leave_type'],
        optional_fields: ['reason'],
        source_confidence: { date_range: 'high' },
        conversation_id: 'conversation-1',
        created_at: '2026-07-25T12:00:00Z',
        expires_at: '2026-07-25T12:15:00Z',
      },
    }} />);
    const card = screen.getByLabelText('Preparing your leave');
    expect(card).toHaveTextContent('Which leave type');
    expect(card).toHaveTextContent('Aug 3, 2026');
    expect(card).toHaveTextContent('Still needed: leave type');
  });

  it('renders a cancelled or expired intake without a draft action', () => {
    render(<AIChatResponseContent status="completed" text="Started over." result={{
      type: 'leave_intake_cancelled',
      title: 'Leave intake cleared',
      message: 'Your in-progress leave intake was cleared.',
    }} />);
    expect(screen.getByLabelText('Leave intake cleared')).toHaveTextContent('in-progress leave intake was cleared');
    expect(screen.queryByRole('button', { name: 'Continue' })).not.toBeInTheDocument();
  });

  it('renders a server-grounded draft card with draft-only actions', () => {
    const onAction = vi.fn();
    render(<AIChatResponseContent status="completed" text="Draft prepared, not submitted." onAction={onAction} result={{
      type: 'leave_request_draft',
      title: 'Leave request draft',
      draft: {
        tool: 'prepare_my_leave_request',
        draft_id: 'draft-1',
        capability: 'leave_request',
        status: 'ready_for_review',
        leave_type: 'Casual Leave',
        leave_type_code: 'CL',
        start_date: '2026-08-03',
        end_date: '2026-08-05',
        calendar_day_count: 3,
        working_day_count: 3,
        reason: 'Family event',
        eligibility_status: 'eligible',
        required_leave_units: 3,
        available_leave_balance: 9,
        balance_source: 'stored_balance',
        approver: 'David Park',
        approver_resolution: 'resolved',
        blocking_reasons: [],
        warnings: [],
        expires_at: '2026-07-24T13:00:00Z',
        version: 1,
        correlation_id: 'draft-correlation',
      },
    }} />);
    const card = screen.getByLabelText('Leave request draft');
    expect(card).toHaveTextContent('AI draft · not submitted');
    expect(card).toHaveTextContent('David Park');
    expect(card).toHaveTextContent('3 of 3');
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(onAction).toHaveBeenCalledWith('Continue with the draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit dates' }));
    expect(onAction).toHaveBeenCalledWith('Change it to ', false);
  });
});

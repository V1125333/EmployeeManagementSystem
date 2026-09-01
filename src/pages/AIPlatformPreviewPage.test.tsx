import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AIPlatformPreviewPage } from './AIPlatformPreviewPage';
import * as previewApi from '@/services/platformPreviewApi';

vi.mock('@/services/platformPreviewApi', async () => {
  const actual = await vi.importActual<typeof import('@/services/platformPreviewApi')>('@/services/platformPreviewApi');
  return { ...actual, submitPlatformPreview: vi.fn() };
});

const response: previewApi.PlatformPreviewResponse = {
  employee_response: {
    status: 'completed', message: 'Your manager is David Park.', correlation_id: 'preview-corr-safe123',
    result_card: { type: 'employee_manager', title: 'My manager', display_name: 'David Park', job_title: 'Manager', work_email: 'david@example.com' },
  },
  developer_summary: {
    interpreted_intent: 'read_employee_manager', interpretation_source: 'deterministic', interpretation_status: 'passed',
    candidate_plan: { capability_id: 'employee.manager.read_self', capability_version: 1, step_count: 1 },
    validated_plan: { capability_id: 'employee.manager.read_self', capability_version: 1 }, plan_validation_status: 'passed',
    authorization_result_code: 'AUTHORIZED', execution_status: 'passed', grounding_validation_status: 'passed', composition_status: 'passed',
    trace_stages: ['request', 'interpretation', 'candidate_plan', 'plan_validation', 'final_authorization', 'capability_execution', 'result_validation', 'grounding_validation', 'composition', 'request_completion'].map((stage) => ({ stage, outcome: 'succeeded' as const, started_at: '2026-08-02T00:00:00Z', completed_at: '2026-08-02T00:00:00Z', latency_ms: 1 })),
    total_latency_ms: 10, result_reference_ids: ['res_safe_reference_123456'], safe_warning_codes: [],
  },
};

describe('AI Platform preview page', () => {
  beforeEach(() => vi.mocked(previewApi.submitPlatformPreview).mockReset());

  it('submits samples and renders the employee card, correlation, and ordered pipeline', async () => {
    vi.mocked(previewApi.submitPlatformPreview).mockResolvedValue(response);
    render(<AIPlatformPreviewPage />);
    expect(screen.getByText('Development Preview — Not Production Chat')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Who is my manager?' }));
    expect(screen.getByRole('textbox', { name: 'Ask the isolated Platform' })).toHaveValue('Who is my manager?');
    fireEvent.click(screen.getByRole('button', { name: 'Run preview' }));
    await waitFor(() => expect(screen.getByText('Your manager is David Park.')).toBeInTheDocument());
    expect(screen.getByText(/preview-corr-safe123/)).toBeInTheDocument();
    expect(screen.getByText('david@example.com')).toBeInTheDocument();
    const stages = ['User Request', 'Intent', 'Candidate Plan', 'Plan Validation', 'Authorization', 'Capability Execution', 'Result Validation', 'Grounding', 'Response Composition', 'Final Response'];
    const positions = stages.map((stage) => screen.getByText(stage).compareDocumentPosition(screen.getByText('Final Response')));
    expect(positions.slice(0, -1).every((value) => Boolean(value & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true);
  });

  it.each([
    ['unsupported', 'I can currently help with supported requests.'],
    ['denied', 'You do not have permission to view this information.'],
  ] as const)('renders %s safely without raw secrets', async (status, message) => {
    vi.mocked(previewApi.submitPlatformPreview).mockResolvedValue({
      ...response, employee_response: { status, message, correlation_id: 'preview-corr-safe456', safe_error_code: status === 'denied' ? 'AUTHORIZATION_DENIED' : 'UNSUPPORTED_REQUEST' },
    });
    render(<AIPlatformPreviewPage />);
    fireEvent.change(screen.getByRole('textbox', { name: 'Ask the isolated Platform' }), { target: { value: 'unsupported question' } });
    fireEvent.click(screen.getByRole('button', { name: 'Run preview' }));
    await screen.findByText(message);
    expect(document.body.textContent).not.toContain('safe-token');
    expect(document.body.textContent).not.toContain('Authorization: Bearer');
  });

  it.each([
    ['What is my leave balance?', { type: 'leave_balance', title: 'My leave balance', balances: [{ code: 'SL', name: 'Sick Leave', available: 8 }] }, 'Sick Leave'],
    ['Show my current projects.', { type: 'current_project_assignments', title: 'My current projects', assignments: [{ project_code: 'ORB', project_name: 'Orbit Modernization', allocation_role: 'Engineer', allocation_percentage: 75 }] }, 'Orbit Modernization'],
  ] as const)('renders the typed card for %s', async (question, card, visibleValue) => {
    vi.mocked(previewApi.submitPlatformPreview).mockResolvedValue({
      ...response,
      employee_response: { ...response.employee_response, message: `Safe result for ${question}`, result_card: card },
    });
    render(<AIPlatformPreviewPage />);
    fireEvent.change(screen.getByRole('textbox', { name: 'Ask the isolated Platform' }), { target: { value: question } });
    fireEvent.click(screen.getByRole('button', { name: 'Run preview' }));
    expect(await screen.findByText(visibleValue)).toBeInTheDocument();
  });
});

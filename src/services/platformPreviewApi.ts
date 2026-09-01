import { apiErrorFromResponse, authenticatedFetch } from '@/services/apiClient';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export type PreviewStatus = 'passed' | 'denied' | 'failed' | 'timed_out' | 'unsupported' | 'not_reached';
export type EmployeeResponseStatus = 'completed' | 'clarification_required' | 'unsupported' | 'denied' | 'failed' | 'timed_out';

export interface PreviewTraceStage {
  stage: string;
  outcome: 'succeeded' | 'failed' | 'denied' | 'skipped' | 'timed_out';
  started_at: string;
  completed_at: string;
  latency_ms: number;
  capability_id?: string | null;
  capability_version?: number | null;
  safe_error_code?: string | null;
  result_reference_id?: string | null;
}

export interface PreviewResultCard {
  type: 'leave_balance' | 'employee_manager' | 'current_project_assignments';
  title: string;
  [key: string]: unknown;
}

export interface PlatformPreviewResponse {
  employee_response: {
    status: EmployeeResponseStatus;
    message: string;
    result_card?: PreviewResultCard | null;
    safe_error_code?: string | null;
    correlation_id: string;
  };
  developer_summary: {
    interpreted_intent: string;
    interpretation_source: 'deterministic';
    interpretation_status: PreviewStatus;
    candidate_plan?: { capability_id: string; capability_version: number; step_count: number } | null;
    validated_plan?: { capability_id: string; capability_version: number } | null;
    plan_validation_status: PreviewStatus;
    authorization_result_code: string;
    execution_status: PreviewStatus;
    grounding_validation_status: PreviewStatus;
    composition_status: PreviewStatus;
    trace_stages: PreviewTraceStage[];
    total_latency_ms: number;
    result_reference_ids: string[];
    safe_warning_codes: string[];
  };
}

export async function submitPlatformPreview(message: string): Promise<PlatformPreviewResponse> {
  const response = await authenticatedFetch(`${API_BASE}/ai/platform-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) throw await apiErrorFromResponse(response);
  return response.json() as Promise<PlatformPreviewResponse>;
}

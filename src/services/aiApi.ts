const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export type LeaveBalanceSource = 'stored_balance' | 'policy_default' | 'on_request';

export type LeaveBalanceItem = {
  leave_type: string;
  code: string;
  total: number;
  available: number | 'On request';
  used: number;
  pending: number;
  source: LeaveBalanceSource;
};

export type LeaveRequestItem = {
  request_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  total_days: number;
  status: string;
  reason: string | null;
  submitted_at: string;
  approver: string | null;
  pending_duration_days: number | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string | null;
};

export type LeaveEligibilityIssue = {
  code: string;
  message: string;
  field: string | null;
  details: Record<string, unknown>;
};

export type LeaveEligibility = {
  tool: 'check_my_leave_eligibility';
  leave_type: string;
  leave_type_code: string;
  start_date: string;
  end_date: string;
  calendar_day_count: number;
  working_day_count: number;
  weekend_dates_excluded: Array<{ date: string; reason: string; label: string | null }>;
  company_holidays_excluded: Array<{ date: string; reason: string; label: string | null }>;
  optional_holiday_treatment: 'not_applicable' | 'selected_automatically' | 'selection_required';
  required_leave_units: number;
  available_leave_balance: number | 'On request';
  balance_source: LeaveBalanceSource;
  existing_overlaps: Array<{
    request_id: string;
    leave_type: string;
    start_date: string;
    end_date: string;
    status: string;
  }>;
  policy_checks_performed: Array<{ code: string; passed: boolean }>;
  blocking_reasons: LeaveEligibilityIssue[];
  warnings: LeaveEligibilityIssue[];
  eligibility_status: 'eligible' | 'eligible_with_warnings' | 'not_eligible' | 'requires_information';
  current_approver: string | null;
  evaluated_at: string;
  timezone: string;
};

export type LeaveRequestDraft = {
  tool:
    | 'prepare_my_leave_request'
    | 'get_my_leave_request_draft'
    | 'update_my_leave_request_draft'
    | 'discard_my_leave_request_draft';
  draft_id: string;
  capability: 'leave_request';
  status: 'draft' | 'requires_information' | 'not_eligible' | 'ready_for_review'
    | 'ready_for_confirmation' | 'discarded' | 'expired';
  leave_type: string;
  leave_type_code: string;
  start_date: string;
  end_date: string;
  calendar_day_count: number;
  working_day_count: number;
  reason: string | null;
  eligibility_status: LeaveEligibility['eligibility_status'];
  required_leave_units: number;
  available_leave_balance: number | 'On request';
  balance_source: LeaveBalanceSource;
  approver: string | null;
  approver_resolution: 'resolved' | 'missing';
  blocking_reasons: LeaveEligibilityIssue[];
  warnings: LeaveEligibilityIssue[];
  expires_at: string;
  version: number;
  correlation_id: string;
};

export type LeaveIntakeState = {
  goal: 'prepare_leave_request';
  collected_fields: {
    leave_type: string | null;
    start_date: string | null;
    end_date: string | null;
    reason: string | null;
    supporting_information: string | null;
    duration_days: number | null;
    reason_skipped: boolean;
    reason_prompted: boolean;
  };
  missing_required_fields: Array<
    'leave_type' | 'date_range' | 'reason' | 'supporting_information'
  >;
  optional_fields: Array<'reason' | 'supporting_information'>;
  source_confidence: Record<string, 'high' | 'medium' | 'low'>;
  conversation_id: string;
  created_at: string;
  expires_at: string;
};

export type AIResult =
  | {
      type: 'leave_balance';
      title: string;
      as_of: string;
      balances: LeaveBalanceItem[];
    }
  | {
      type: 'leave_balance_comparison';
      title: string;
      as_of: string;
      comparison: 'at_least' | 'highest';
      balances: LeaveBalanceItem[];
      threshold: number | null;
      meets_threshold: boolean | null;
      highest: LeaveBalanceItem | null;
    }
  | {
      type: 'leave_request_list';
      title: string;
      as_of: string;
      requests: LeaveRequestItem[];
      total_matches: number;
    }
  | {
      type: 'leave_request_status';
      title: string;
      as_of: string;
      request: LeaveRequestItem;
    }
  | {
      type: 'rejection_explanation';
      title: string;
      as_of: string;
      request: LeaveRequestItem;
      explanation: string;
      reason_recorded: boolean;
    }
  | {
      type: 'ambiguous_leave_request';
      title: string;
      candidates: LeaveRequestItem[];
    }
  | {
      type: 'leave_eligibility';
      title: string;
      eligibility: LeaveEligibility;
    }
  | {
      type: 'leave_eligibility_clarification';
      title: string;
      missing_fields: Array<'leave_type' | 'date_range'>;
      prompt: string;
    }
  | {
      type: 'leave_request_draft';
      title: string;
      draft: LeaveRequestDraft;
    }
  | {
      type: 'leave_intake_question';
      title: string;
      field: 'leave_type' | 'date_range' | 'reason' | 'supporting_information';
      prompt: string;
      intake: LeaveIntakeState;
    }
  | {
      type: 'leave_intake_summary';
      title: string;
      intake: LeaveIntakeState;
    }
  | {
      type: 'leave_intake_cancelled';
      title: string;
      message: string;
    };

export type AIChatResponse = {
  conversation_id: string;
  status: 'completed' | 'needs_clarification' | 'unsupported' | 'failed';
  message: { role: 'assistant'; content: string };
  result: AIResult | null;
  error: { code: string; message: string } | null;
  tool_used:
    | 'get_my_leave_balance'
    | 'compare_my_leave_balance'
    | 'get_my_recent_leave_requests'
    | 'get_my_leave_request_status'
    | 'get_my_leave_request_details'
    | 'explain_my_leave_decision'
    | 'check_my_leave_eligibility'
    | 'prepare_my_leave_request'
    | 'get_my_leave_request_draft'
    | 'update_my_leave_request_draft'
    | 'discard_my_leave_request_draft'
    | null;
  correlation_id: string;
};

export type AIConversationSummary = {
  id: string;
  title: string;
  domain: string;
  capability: string | null;
  status: 'active' | 'closed' | 'archived';
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  message_count: number;
  workflow_status: string | null;
};

export type AIConversationMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  response_status: AIChatResponse['status'] | null;
  result_type: string | null;
  correlation_id: string | null;
  created_at: string;
  historical: true;
};

export type AIConversationWorkflow = {
  kind: 'leave_request_draft' | 'leave_request';
  status: string;
  display_status: 'active' | 'expired' | 'discarded' | 'completed' | 'cancelled' | 'unknown';
  message: string;
  refreshed_at: string;
};

export type AIConversationDetail = {
  conversation: AIConversationSummary;
  messages: AIConversationMessage[];
  workflow: AIConversationWorkflow | null;
  facts_require_refresh: boolean;
  notice: string;
};

export class AIAPIError extends Error {
  constructor(
    message: string,
    public readonly correlationId?: string,
    public readonly status?: number,
  ) {
    super(message);
  }
}

async function conversationRequest<T>(
  path: string,
  accessToken: string | null,
  init?: RequestInit,
): Promise<T> {
  if (!accessToken) {
    throw new AIAPIError('Please sign in again to use Orbit AI.', undefined, 401);
  }
  const response = await fetch(`${API_BASE}/ai${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
      ...(init?.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail || {};
    throw new AIAPIError(
      detail.message || detail || 'Orbit AI conversation history is unavailable.',
      detail.correlation_id,
      response.status,
    );
  }
  return data as T;
}

export function startAIConversation(accessToken: string | null) {
  return conversationRequest<AIConversationSummary>(
    '/conversations',
    accessToken,
    { method: 'POST', body: '{}' },
  );
}

export function listAIConversations(accessToken: string | null) {
  return conversationRequest<{ conversations: AIConversationSummary[] }>(
    '/conversations?include_archived=true',
    accessToken,
  );
}

export function getAIConversation(
  conversationId: string,
  accessToken: string | null,
) {
  return conversationRequest<AIConversationDetail>(
    `/conversations/${encodeURIComponent(conversationId)}`,
    accessToken,
  );
}

export function closeAIConversation(
  conversationId: string,
  accessToken: string | null,
) {
  return conversationRequest<AIConversationSummary>(
    `/conversations/${encodeURIComponent(conversationId)}/close`,
    accessToken,
    { method: 'POST' },
  );
}

export function archiveAIConversation(
  conversationId: string,
  accessToken: string | null,
) {
  return conversationRequest<AIConversationSummary>(
    `/conversations/${encodeURIComponent(conversationId)}/archive`,
    accessToken,
    { method: 'POST' },
  );
}

export function restoreAIConversation(
  conversationId: string,
  accessToken: string | null,
) {
  return conversationRequest<AIConversationDetail>(
    `/conversations/${encodeURIComponent(conversationId)}/restore`,
    accessToken,
    { method: 'POST' },
  );
}

export function deleteAIConversation(
  conversationId: string,
  accessToken: string | null,
) {
  return conversationRequest<{ deleted: boolean }>(
    `/conversations/${encodeURIComponent(conversationId)}`,
    accessToken,
    { method: 'DELETE' },
  );
}

export async function sendAIChat(
  message: string,
  accessToken: string | null,
  conversationId?: string,
  signal?: AbortSignal,
): Promise<AIChatResponse> {
  if (!accessToken) {
    throw new AIAPIError('Please sign in again to use Orbit AI.', undefined, 401);
  }
  const response = await fetch(`${API_BASE}/ai/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      message,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    }),
    signal,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail || {};
    throw new AIAPIError(
      detail.message || 'Orbit AI could not answer right now.',
      detail.correlation_id,
      response.status,
    );
  }
  return data as AIChatResponse;
}

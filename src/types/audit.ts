export interface AuditLogRow {
  id: string;
  created_at: string;
  actor_user_id?: string | null;
  actor_name?: string | null;
  actor_role?: string | null;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  old_values?: Record<string, unknown> | null;
  new_values?: Record<string, unknown> | null;
  changed_fields?: Record<string, { old: unknown; new: unknown }> | null;
  reason?: string | null;
  metadata_json?: Record<string, unknown> | null;
  source: string;
  ip_address?: string | null;
  user_agent?: string | null;
}

export interface AuditLogPage {
  items: AuditLogRow[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface AuditFilters {
  search: string;
  actor: string;
  entity_type: string;
  action: string;
  source: string;
  sensitive_only: boolean;
  date_from: string;
  date_to: string;
}

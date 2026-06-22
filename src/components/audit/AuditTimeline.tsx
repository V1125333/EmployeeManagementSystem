import { useCallback, useEffect, useMemo, useState } from 'react';
import { Clock3 } from 'lucide-react';
import { Card } from '@/components/ui';
import { Drawer } from '@/components/ui/Drawer';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';
import type { AuditLogPage, AuditLogRow } from '@/types/audit';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface AuditTimelineProps {
  entityType: string;
  entityId: string;
  maxItems?: number;
}

function labelize(value?: string | null) {
  return (value || '-').replace(/[._-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function relativeTime(value: string) {
  const delta = Date.now() - new Date(value).getTime();
  const minutes = Math.max(1, Math.round(delta / 60000));
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

function actionTone(action: string) {
  if (action.includes('created') || action.includes('approved')) return 'bg-status-success';
  if (action.includes('updated') || action.includes('changed')) return 'bg-accent';
  if (action.includes('deleted') || action.includes('rejected') || action.includes('denied')) return 'bg-status-error';
  if (action.includes('login') || action.includes('auth')) return 'bg-status-info';
  return 'bg-gray-300';
}

function formatJson(value: unknown) {
  return JSON.stringify(value || {}, null, 2);
}

function AuditTimelineDrawer({ row, onClose }: { row: AuditLogRow | null; onClose: () => void }) {
  if (!row) return null;
  return (
    <Drawer open={!!row} onClose={onClose} title={row.action} subtitle={`${labelize(row.entity_type)} ${row.entity_id || ''}`} width="w-[680px] max-w-[calc(100vw-32px)]">
      <div className="space-y-4">
        <Card className="p-4 text-sm">
          <div className="font-bold text-[#2F3437]">{row.actor_name || 'System'}</div>
          <div className="text-gray-500">{labelize(row.actor_role)} • {new Date(row.created_at).toLocaleString()}</div>
          {row.reason && <div className="mt-3 text-gray-600">{row.reason}</div>}
        </Card>
        <Card className="p-4">
          <div className="mb-2 text-sm font-bold text-[#2F3437]">Changed Fields</div>
          {Object.keys(row.changed_fields || {}).length ? (
            <pre className="max-h-80 overflow-auto rounded-lg bg-warm-bg p-3 text-xs text-gray-700">{formatJson(row.changed_fields)}</pre>
          ) : (
            <div className="text-sm text-gray-500">No field-level diff recorded.</div>
          )}
        </Card>
        <Card className="p-4">
          <div className="mb-2 text-sm font-bold text-[#2F3437]">Metadata</div>
          <pre className="max-h-80 overflow-auto rounded-lg bg-warm-bg p-3 text-xs text-gray-700">{formatJson(row.metadata_json)}</pre>
        </Card>
      </div>
    </Drawer>
  );
}

export function AuditTimeline({ entityType, entityId, maxItems = 10 }: AuditTimelineProps) {
  const { user } = useAuth();
  const [rows, setRows] = useState<AuditLogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<AuditLogRow | null>(null);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': user?.role || '',
    'x-user-name': user?.name || '',
  }), [user]);

  const loadTimeline = useCallback(async () => {
    if (!user || !entityId) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/audit-logs/entity/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}?per_page=${maxItems}`, { headers });
      const body: AuditLogPage | null = await res.json().catch(() => null);
      if (!res.ok) throw new Error((body as { detail?: string } | null)?.detail || 'Could not load activity.');
      setRows(body?.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load activity.');
    } finally {
      setLoading(false);
    }
  }, [entityId, entityType, headers, maxItems, user]);

  useEffect(() => {
    loadTimeline();
  }, [loadTimeline]);

  if (loading) return <Card className="p-5 text-sm text-gray-500">Loading activity...</Card>;
  if (error) return <Card className="p-5 text-sm text-status-error">{error}</Card>;
  if (!rows.length) {
    return (
      <Card className="flex flex-col items-center justify-center p-10 text-center">
        <Clock3 size={28} className="mb-3 text-gray-300" />
        <div className="font-bold text-[#2F3437]">No activity recorded yet</div>
        <p className="mt-1 text-sm text-gray-500">Audit events for this record will appear here.</p>
      </Card>
    );
  }

  return (
    <>
      <Card className="p-5">
        <div className="space-y-1">
          {rows.map((row, index) => (
            <button key={row.id} className="grid w-full grid-cols-[18px_1fr] gap-3 rounded-lg px-2 py-3 text-left transition hover:bg-accent-light/30" onClick={() => setSelected(row)}>
              <div className="relative flex justify-center">
                <span className={cn('mt-1 h-2.5 w-2.5 rounded-full', actionTone(row.action))} />
                {index !== rows.length - 1 && <span className="absolute top-5 h-full w-px bg-[#E5E7EB]" />}
              </div>
              <div>
                <div className="text-sm font-bold text-[#2F3437]">{labelize(row.action)}</div>
                <div className="text-xs text-gray-500">{row.actor_name || 'System'} • {relativeTime(row.created_at)}</div>
              </div>
            </button>
          ))}
        </div>
      </Card>
      <AuditTimelineDrawer row={selected} onClose={() => setSelected(null)} />
    </>
  );
}

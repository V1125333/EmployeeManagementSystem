import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Award, CheckCircle2, ShieldAlert } from 'lucide-react';
import { Badge, Card } from '@/components/ui';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface PublicCertificate {
  certificate_code: string;
  learner_name?: string;
  course_name?: string;
  start_date?: string;
  end_date?: string;
  issue_date?: string;
  status: 'valid' | 'expired' | 'revoked' | 'not_found';
  issued_by?: string;
  message?: string;
}

function formatDate(value?: string) {
  return value ? new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : '-';
}

export function CertificateVerificationPage() {
  const { certificateCode = '' } = useParams();
  const [record, setRecord] = useState<PublicCertificate | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function loadCertificate() {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/certificates/verify/${encodeURIComponent(certificateCode)}`);
        const body = await res.json();
        if (mounted) setRecord(body);
      } catch {
        if (mounted) setRecord({ certificate_code: certificateCode, status: 'not_found', message: 'Certificate not found' });
      } finally {
        if (mounted) setLoading(false);
      }
    }
    loadCertificate();
    return () => {
      mounted = false;
    };
  }, [certificateCode]);

  const status = record?.status || 'not_found';
  const isValid = status === 'valid';

  return (
    <div className="min-h-screen bg-warm-bg px-4 py-12">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-olive text-white">
            <Award size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-[var(--color-brand-navy)]">Certificate Verification</h1>
            <p className="text-sm text-gray-500">Verify certificates issued by ReKnew.</p>
          </div>
        </div>

        <Card className="overflow-hidden">
          {loading ? (
            <div className="p-10 text-center text-gray-500">Checking certificate...</div>
          ) : status === 'not_found' ? (
            <div className="p-10 text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-status-error/10 text-status-error">
                <ShieldAlert size={26} />
              </div>
              <div className="text-xl font-bold text-[var(--color-brand-navy)]">Certificate not found</div>
              <div className="mt-2 text-sm text-gray-500">We could not find a certificate with ID {certificateCode}.</div>
            </div>
          ) : (
            <div>
              <div className="border-b border-[var(--color-border)] bg-white px-6 py-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className={isValid ? 'text-status-success' : 'text-status-error'} />
                    <div>
                      <div className="text-sm text-gray-500">Status</div>
                      <div className="text-2xl font-bold text-[var(--color-brand-navy)]">{isValid ? 'Valid' : status === 'revoked' ? 'Revoked' : 'Expired'}</div>
                    </div>
                  </div>
                  <Badge variant={isValid ? 'success' : 'error'}>{isValid ? 'Valid' : status}</Badge>
                </div>
              </div>
              <div className="grid gap-4 p-6 md:grid-cols-2">
                <VerifyRow label="Learner Name" value={record?.learner_name || '-'} />
                <VerifyRow label="Course" value={record?.course_name || '-'} />
                <VerifyRow label="Certificate ID" value={record?.certificate_code || certificateCode} />
                <VerifyRow label="Issued By" value={record?.issued_by || 'ReKnew'} />
                <VerifyRow label="Start Date" value={formatDate(record?.start_date)} />
                <VerifyRow label="End Date" value={formatDate(record?.end_date)} />
                <VerifyRow label="Issue Date" value={formatDate(record?.issue_date)} />
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function VerifyRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg p-4">
      <div className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</div>
      <div className="mt-1 font-semibold text-[var(--color-brand-navy)]">{value}</div>
    </div>
  );
}

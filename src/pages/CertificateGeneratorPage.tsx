import { useEffect, useMemo, useState } from 'react';
import {
  Award,
  CalendarDays,
  Download,
  FileArchive,
  FileBadge,
  Hash,
  Link2,
  Loader2,
  RefreshCw,
  Upload,
} from 'lucide-react';
import { Badge, Button, Card, CardHeader } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface CertificateCounter {
  certificate_type: string;
  cohort_code: string;
  year: number;
  last_issued: number;
}

interface CertificateMeta {
  certificate_types: string[];
  counters: CertificateCounter[];
}

interface NextSerial {
  certificate_id: string;
  next_serial: number;
}

interface CertificateRecord {
  certificate_code: string;
  learner_name: string;
  course_name: string;
  issue_date: string;
  status: string;
  verification_url: string;
  pdf_url?: string | null;
}

interface BulkRow {
  first_name: string;
  surname: string;
  certificate_type: string;
  start_date: string;
  end_date: string;
  cohort_code: string;
  year: number;
  issued_date: string;
}

const currentYear = new Date().getFullYear();
const today = new Date().toISOString().slice(0, 10);

function readDownloadFilename(contentDisposition: string | null, fallback: string) {
  if (!contentDisposition) return fallback;
  const match = contentDisposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] || fallback;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function normalizeHeader(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, '');
}

function splitCsvLine(line: string) {
  const cells: string[] = [];
  let current = '';
  let quoted = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === ',' && !quoted) {
      cells.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }

  cells.push(current.trim());
  return cells;
}

function parseBulkCsv(text: string, certificateTypes: string[]) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) return { rows: [] as BulkRow[], errors: ['Upload a CSV with a header row and at least one recipient.'] };

  const headers = splitCsvLine(lines[0]).map(normalizeHeader);
  const valueAt = (cells: string[], names: string[]) => {
    const index = headers.findIndex((header) => names.includes(header));
    return index >= 0 ? cells[index]?.trim() || '' : '';
  };

  const rows: BulkRow[] = [];
  const errors: string[] = [];

  lines.slice(1).forEach((line, idx) => {
    const cells = splitCsvLine(line);
    const rowNumber = idx + 2;
    const row: BulkRow = {
      first_name: valueAt(cells, ['firstname', 'first']),
      surname: valueAt(cells, ['lastname', 'surname', 'last']),
      certificate_type: valueAt(cells, ['programme', 'program', 'certificatetype', 'certificate']),
      start_date: valueAt(cells, ['startdate', 'start']),
      end_date: valueAt(cells, ['enddate', 'end']),
      cohort_code: valueAt(cells, ['cohortcode', 'cohort']) || 'C1',
      year: Number(valueAt(cells, ['year']) || currentYear),
      issued_date: valueAt(cells, ['dateofissue', 'issueddate', 'date']) || today,
    };

    if (!row.first_name && !row.surname) return;
    if (!row.first_name) errors.push(`Row ${rowNumber}: First Name is required.`);
    if (!row.surname) errors.push(`Row ${rowNumber}: Last Name is required.`);
    if (!certificateTypes.includes(row.certificate_type)) errors.push(`Row ${rowNumber}: Programme is not supported.`);
    if (!row.start_date) errors.push(`Row ${rowNumber}: Start Date is required.`);
    if (!row.end_date) errors.push(`Row ${rowNumber}: End Date is required.`);
    if (row.start_date && row.end_date && row.end_date < row.start_date) {
      errors.push(`Row ${rowNumber}: End Date must be on or after Start Date.`);
    }
    if (!row.cohort_code) errors.push(`Row ${rowNumber}: Cohort Code is required.`);
    if (!row.year || row.year < 2020 || row.year > 2099) errors.push(`Row ${rowNumber}: Year must be between 2020 and 2099.`);
    if (!row.issued_date) errors.push(`Row ${rowNumber}: Date of issue is required.`);

    rows.push(row);
  });

  return { rows, errors };
}

export function CertificateGeneratorPage() {
  const { user } = useAuth();
  const [meta, setMeta] = useState<CertificateMeta | null>(null);
  const [certificates, setCertificates] = useState<CertificateRecord[]>([]);
  const [nextSerial, setNextSerial] = useState<NextSerial | null>(null);
  const [firstName, setFirstName] = useState('');
  const [surname, setSurname] = useState('');
  const [certificateType, setCertificateType] = useState('');
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [cohortCode, setCohortCode] = useState('C1');
  const [year, setYear] = useState(currentYear);
  const [issuedDate, setIssuedDate] = useState(today);
  const [includeCertificateNumber, setIncludeCertificateNumber] = useState(true);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [bulkGenerating, setBulkGenerating] = useState(false);
  const [bulkRows, setBulkRows] = useState<BulkRow[]>([]);
  const [bulkFileName, setBulkFileName] = useState('');
  const [bulkErrors, setBulkErrors] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const authHeaders = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
  }), [user]);

  const relevantCounters = useMemo(() => {
    const normalizedCohort = cohortCode.trim().toUpperCase();
    return (meta?.counters || []).filter(
      (counter) => counter.cohort_code === normalizedCohort && counter.year === Number(year)
    );
  }, [cohortCode, meta?.counters, year]);

  useEffect(() => {
    let mounted = true;
    async function loadMeta() {
      setLoadingMeta(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/certificates/meta`);
        if (!res.ok) throw new Error('Could not load certificate settings.');
        const data: CertificateMeta = await res.json();
        if (!mounted) return;
        setMeta(data);
        setCertificateType((current) => current || data.certificate_types[0] || '');
      } catch (err) {
        if (mounted) setError(err instanceof Error ? err.message : 'Could not load certificate settings.');
      } finally {
        if (mounted) setLoadingMeta(false);
      }
    }
    loadMeta();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!user) return;
    refreshCertificates();
  }, [user]);

  useEffect(() => {
    if (!includeCertificateNumber || !certificateType || !cohortCode || !year) {
      setNextSerial(null);
      return;
    }
    const controller = new AbortController();
    async function loadNextSerial() {
      try {
        const params = new URLSearchParams({
          certificate_type: certificateType,
          cohort_code: cohortCode.trim().toUpperCase(),
          year: String(year),
        });
        const res = await fetch(`${API_BASE}/certificates/next-serial?${params.toString()}`, {
          signal: controller.signal,
        });
        if (!res.ok) throw new Error('Could not preview the next certificate ID.');
        setNextSerial(await res.json());
      } catch {
        if (!controller.signal.aborted) setNextSerial(null);
      }
    }
    loadNextSerial();
    return () => controller.abort();
  }, [certificateType, cohortCode, includeCertificateNumber, year]);

  const canGenerate =
    firstName.trim() &&
    surname.trim() &&
    certificateType &&
    startDate &&
    endDate &&
    endDate >= startDate &&
    cohortCode.trim() &&
    issuedDate &&
    !generating;

  async function refreshMeta() {
    const res = await fetch(`${API_BASE}/certificates/meta`);
    if (res.ok) setMeta(await res.json());
  }

  async function refreshCertificates() {
    const res = await fetch(`${API_BASE}/certificates`, { headers: authHeaders });
    if (res.ok) {
      const body = await res.json();
      setCertificates(body.certificates || []);
    }
  }

  async function refreshNextSerial() {
    if (!includeCertificateNumber || !certificateType || !cohortCode || !year) return;
    const params = new URLSearchParams({
      certificate_type: certificateType,
      cohort_code: cohortCode.trim().toUpperCase(),
      year: String(year),
    });
    const res = await fetch(`${API_BASE}/certificates/next-serial?${params.toString()}`);
    if (res.ok) setNextSerial(await res.json());
  }

  async function generateCertificate() {
    if (!canGenerate) return;
    setGenerating(true);
    setError(null);
    setSuccess(null);

    try {
      const res = await fetch(`${API_BASE}/certificates/generate`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          first_name: firstName.trim(),
          surname: surname.trim(),
          certificate_type: certificateType,
          start_date: startDate,
          end_date: endDate,
          cohort_code: cohortCode.trim().toUpperCase(),
          year: Number(year),
          issued_date: issuedDate,
          include_certificate_number: includeCertificateNumber,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || 'Could not generate the certificate.');
      }

      downloadBlob(await res.blob(), readDownloadFilename(res.headers.get('Content-Disposition'), 'ReKnew_Certificate.pdf'));
      const certId = res.headers.get('X-Certificate-Id');
      setSuccess(certId ? `Certificate generated: ${certId}` : 'Certificate generated without certificate number.');
      await refreshMeta();
      await refreshCertificates();
      await refreshNextSerial();
      setFirstName('');
      setSurname('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not generate the certificate.');
    } finally {
      setGenerating(false);
    }
  }

  async function handleBulkFile(file: File | null) {
    setBulkRows([]);
    setBulkErrors([]);
    setBulkFileName('');
    if (!file) return;
    const text = await file.text();
    const parsed = parseBulkCsv(text, meta?.certificate_types || []);
    setBulkFileName(file.name);
    setBulkRows(parsed.rows);
    setBulkErrors(parsed.errors);
  }

  function downloadSampleCsv() {
    const sample = [
      'First Name,Last Name,Programme,Start Date,End Date,Cohort Code,Year,Date of issue',
      'Lahari,Pendem,Agentic Commerce,2026-02-01,2026-05-22,C1,2026,2026-05-22',
      'Venu,Pendurthi,ReKnew Context Engineer,2026-05-01,2026-06-02,C1,2026,2026-06-02',
    ].join('\n');
    downloadBlob(new Blob([sample], { type: 'text/csv' }), 'reknew_certificate_bulk_sample.csv');
  }

  async function generateBulkCertificates() {
    if (!bulkRows.length || bulkErrors.length || bulkGenerating) return;
    setBulkGenerating(true);
    setError(null);
    setSuccess(null);

    try {
      const res = await fetch(`${API_BASE}/certificates/bulk-generate`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          records: bulkRows.map((row) => ({
            ...row,
            cohort_code: row.cohort_code.trim().toUpperCase(),
            include_certificate_number: includeCertificateNumber,
          })),
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || 'Could not generate bulk certificates.');
      }

      downloadBlob(await res.blob(), readDownloadFilename(res.headers.get('Content-Disposition'), 'ReKnew_Certificates.zip'));
      setSuccess(`${bulkRows.length} certificate${bulkRows.length === 1 ? '' : 's'} generated.`);
      await refreshMeta();
      await refreshCertificates();
      await refreshNextSerial();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not generate bulk certificates.');
    } finally {
      setBulkGenerating(false);
    }
  }

  async function downloadIssuedCertificate(record: CertificateRecord) {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/certificates/${encodeURIComponent(record.certificate_code)}/download`, { headers: authHeaders });
      if (!res.ok) throw new Error('Could not download certificate PDF.');
      downloadBlob(await res.blob(), readDownloadFilename(res.headers.get('Content-Disposition'), `${record.certificate_code}.pdf`));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not download certificate PDF.');
    }
  }

  return (
    <div className="animate-fade-up">
      <div className="mb-7 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-brand-navy)] tracking-tight mb-1">
            Certificate Generator
          </h1>
          <p className="text-sm text-gray-500">
            Issue ReKnew programme completion certificates with optional verification details.
          </p>
        </div>
        <Badge variant="sage">Admin Console</Badge>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] gap-5">
        <div className="space-y-5">
          <Card>
            <CardHeader title="Certificate Details" icon={<FileBadge size={17} />} />
            <div className="p-5 space-y-5">
              {error && (
                <div className="rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
                  {error}
                </div>
              )}
              {success && (
                <div className="rounded-lg border border-status-success/20 bg-status-success/10 px-4 py-3 text-sm text-status-success">
                  {success}
                </div>
              )}

              <label className="flex items-start gap-3 rounded-lg border border-[var(--color-border)] bg-hover-bg px-4 py-3">
                <input
                  type="checkbox"
                  checked={includeCertificateNumber}
                  onChange={(event) => setIncludeCertificateNumber(event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-[var(--color-border)] accent-olive"
                />
                <span>
                  <span className="block text-sm font-semibold text-[var(--color-brand-navy)]">
                    Generate certificate with certificate number
                  </span>
                  <span className="block text-xs text-gray-500">
                    Adds the certificate ID and QR verification code. Uncheck for a plain branded certificate.
                  </span>
                </span>
              </label>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">First Name</span>
                  <input
                    value={firstName}
                    onChange={(event) => setFirstName(event.target.value)}
                    className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                    placeholder="Venu"
                  />
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">Surname</span>
                  <input
                    value={surname}
                    onChange={(event) => setSurname(event.target.value)}
                    className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                    placeholder="Madhav"
                  />
                </label>
              </div>

              <div className="grid grid-cols-1 gap-4">
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">Programme</span>
                  <select
                    value={certificateType}
                    onChange={(event) => setCertificateType(event.target.value)}
                    disabled={loadingMeta}
                    className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                  >
                    {(meta?.certificate_types || []).map((type) => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">Start Date</span>
                  <input
                    value={startDate}
                    onChange={(event) => setStartDate(event.target.value)}
                    type="date"
                    className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                  />
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">End Date</span>
                  <input
                    value={endDate}
                    onChange={(event) => setEndDate(event.target.value)}
                    type="date"
                    className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                  />
                </label>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">Cohort Code</span>
                  <input
                    value={cohortCode}
                    onChange={(event) => setCohortCode(event.target.value.toUpperCase())}
                    className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                    placeholder="C1"
                  />
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">Year</span>
                  <input
                    value={year}
                    onChange={(event) => setYear(Number(event.target.value))}
                    type="number"
                    min={2020}
                    max={2099}
                    className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                  />
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">Date of Issue</span>
                  <input
                    value={issuedDate}
                    onChange={(event) => setIssuedDate(event.target.value)}
                    type="date"
                    className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                  />
                </label>
              </div>

              <div className="flex flex-col gap-3 rounded-lg border border-[var(--color-border)] bg-hover-bg px-4 py-3 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-gray-500">Next Certificate ID</div>
                  <div className="mt-1 text-lg font-bold text-[var(--color-brand-navy)] tracking-tight">
                    {includeCertificateNumber ? nextSerial?.certificate_id || 'Preview unavailable' : 'Not included'}
                  </div>
                </div>
                <Button
                  onClick={generateCertificate}
                  disabled={!canGenerate}
                  icon={generating ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
                >
                  {generating ? 'Generating' : 'Generate PDF'}
                </Button>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Bulk Certificate Generation"
              icon={<FileArchive size={17} />}
              action={
                <button onClick={downloadSampleCsv} className="text-xs font-semibold text-olive hover:text-olive-dark">
                  Download sample CSV
                </button>
              }
            />
            <div className="p-5 space-y-4">
              <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-[var(--color-border)] bg-white px-4 py-8 text-center hover:border-olive/60 hover:bg-hover-bg">
                <Upload size={22} className="mb-2 text-olive" />
                <span className="text-sm font-semibold text-[var(--color-brand-navy)]">Upload CSV</span>
                <span className="mt-1 text-xs text-gray-500">
                  Columns: First Name, Last Name, Programme, Start Date, End Date, Cohort Code, Year, Date of issue
                </span>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(event) => handleBulkFile(event.target.files?.[0] || null)}
                />
              </label>

              {bulkFileName && (
                <div className="rounded-lg border border-[var(--color-border)] px-4 py-3 text-sm text-gray-600">
                  Loaded <span className="font-semibold text-[var(--color-brand-navy)]">{bulkFileName}</span> with{' '}
                  <span className="font-semibold text-[var(--color-brand-navy)]">{bulkRows.length}</span> recipient
                  {bulkRows.length === 1 ? '' : 's'}.
                </div>
              )}

              {bulkErrors.length > 0 && (
                <div className="rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm text-status-error">
                  {bulkErrors.slice(0, 5).map((item) => (
                    <div key={item}>{item}</div>
                  ))}
                  {bulkErrors.length > 5 && <div>{bulkErrors.length - 5} more issue(s).</div>}
                </div>
              )}

              {bulkRows.length > 0 && (
                <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
                  <div className="max-h-64 overflow-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="sticky top-0 bg-hover-bg text-gray-500">
                        <tr>
                          <th className="px-3 py-2 font-semibold">Name</th>
                          <th className="px-3 py-2 font-semibold">Programme</th>
                          <th className="px-3 py-2 font-semibold">Programme Dates</th>
                          <th className="px-3 py-2 font-semibold">Issue Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bulkRows.slice(0, 20).map((row, index) => (
                          <tr key={`${row.first_name}-${row.surname}-${index}`} className="border-t border-[var(--color-border)]">
                            <td className="px-3 py-2 text-[var(--color-brand-navy)]">{row.first_name} {row.surname}</td>
                            <td className="px-3 py-2 text-gray-500">{row.certificate_type}</td>
                            <td className="px-3 py-2 text-gray-500">{row.start_date} - {row.end_date}</td>
                            <td className="px-3 py-2 text-gray-500">{row.issued_date}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="flex justify-end">
                <Button
                  onClick={generateBulkCertificates}
                  disabled={!bulkRows.length || !!bulkErrors.length || bulkGenerating}
                  icon={bulkGenerating ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
                >
                  {bulkGenerating ? 'Generating ZIP' : 'Generate ZIP'}
                </Button>
              </div>
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader
              title="Serial Counters"
              icon={<Hash size={17} />}
              action={
                <button
                  onClick={refreshMeta}
                  className="text-gray-400 hover:text-olive"
                  title="Refresh counters"
                >
                  <RefreshCw size={15} />
                </button>
              }
            />
            <div className="p-4">
              <div className="mb-3 flex items-center gap-2 text-xs text-gray-500">
                <CalendarDays size={14} />
                <span>{cohortCode.trim().toUpperCase()} / {year}</span>
              </div>
              {includeCertificateNumber && relevantCounters.length ? (
                <div className="space-y-2">
                  {relevantCounters.map((counter) => (
                    <div
                      key={`${counter.certificate_type}-${counter.cohort_code}-${counter.year}`}
                      className="rounded-lg border border-[var(--color-border)] px-3 py-2"
                    >
                      <div className="text-xs font-semibold text-[var(--color-brand-navy)]">
                        {counter.certificate_type.replace('ReKnew ', '')}
                      </div>
                      <div className="mt-1 text-xs text-gray-500">
                        Last issued #{String(counter.last_issued).padStart(3, '0')}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-[var(--color-border)] px-3 py-8 text-center text-sm text-gray-500">
                  {includeCertificateNumber ? 'No certificates issued for this cohort yet.' : 'Certificate numbering is turned off.'}
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Verification" icon={<Award size={17} />} />
            <div className="p-4 text-sm leading-6 text-gray-500">
              When certificate numbering is enabled, each PDF includes a QR code, certificate ID, and human-readable
              verification link. The QR code stores only the verification URL.
            </div>
          </Card>
        </div>
      </div>
      <Card className="mt-5 overflow-hidden">
        <CardHeader title="Issued Certificates" icon={<FileBadge size={17} />} />
        {certificates.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-gray-500">No issued certificates found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="bg-hover-bg text-[11px] uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="px-5 py-3 text-left">Certificate ID</th>
                  <th className="px-5 py-3 text-left">Learner</th>
                  <th className="px-5 py-3 text-left">Course</th>
                  <th className="px-5 py-3 text-left">Issue Date</th>
                  <th className="px-5 py-3 text-left">Status</th>
                  <th className="px-5 py-3 text-left">Verify Link</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {certificates.map((record) => (
                  <tr key={record.certificate_code}>
                    <td className="px-5 py-3 font-bold text-[var(--color-brand-navy)]">{record.certificate_code}</td>
                    <td className="px-5 py-3">{record.learner_name}</td>
                    <td className="px-5 py-3">{record.course_name}</td>
                    <td className="px-5 py-3">{record.issue_date}</td>
                    <td className="px-5 py-3"><Badge variant={record.status === 'valid' ? 'success' : 'error'}>{record.status}</Badge></td>
                    <td className="max-w-[260px] truncate px-5 py-3 text-olive">{record.verification_url}</td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="ghost" icon={<Link2 size={13} />} onClick={() => navigator.clipboard.writeText(record.verification_url)}>Copy Link</Button>
                        <a href={record.verification_url} target="_blank" rel="noreferrer"><Button size="sm" variant="soft">Verify</Button></a>
                        {record.pdf_url && <Button size="sm" variant="ghost" icon={<Download size={13} />} onClick={() => downloadIssuedCertificate(record)}>Download PDF</Button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

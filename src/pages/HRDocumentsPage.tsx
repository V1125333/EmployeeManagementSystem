import { useMemo, useState } from 'react';
import {
  BriefcaseBusiness,
  Download,
  FileCheck2,
  FileText,
  Loader2,
  ScrollText,
} from 'lucide-react';
import { Badge, Button, Card, CardHeader } from '@/components/ui';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const today = new Date().toISOString().slice(0, 10);

const templates = [
  { key: 'internship-completion', label: 'Internship Completion Letter', icon: FileCheck2, active: true },
  { key: 'offer', label: 'Offer Letter', icon: BriefcaseBusiness, active: false },
  { key: 'intern-offer', label: 'Intern Offer Letter', icon: FileText, active: false },
  { key: 'experience', label: 'Experience Letter', icon: ScrollText, active: false },
];

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

function formatDate(value: string) {
  if (!value) return '[DATE]';
  const date = new Date(`${value}T00:00:00`);
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function firstName(fullName: string) {
  return fullName.trim().split(/\s+/)[0] || '[INTERN FIRST NAME]';
}

function normalizeResponsibilitySummary(internName: string, summary: string) {
  const value = summary.trim();
  if (!value) return '[MAIN BODY OF INTERN RESPONSIBILITY]';
  if (/^(was|worked|participated|contributed)\s/i.test(value) || /^[a-z]/.test(value)) {
    return `${firstName(internName)} ${value}`;
  }
  return value;
}

export function HRDocumentsPage() {
  const [internName, setInternName] = useState('');
  const [programme, setProgramme] = useState('Agentic Commerce');
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [issuedDate, setIssuedDate] = useState(today);
  const [responsibilitySummary, setResponsibilitySummary] = useState(
    'was part of our Agentic Commerce team and demonstrated professionalism, curiosity, initiative, and a strong willingness to learn. Throughout the program, they actively participated in collaborative projects, contributed to ongoing initiatives, and gained hands-on experience working alongside the ReKnew team in a real-world professional environment.'
  );
  const [generatingFormat, setGeneratingFormat] = useState<'pdf' | 'docx' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canGenerate =
    internName.trim() &&
    programme.trim() &&
    startDate &&
    endDate &&
    endDate >= startDate &&
    issuedDate &&
    responsibilitySummary.trim() &&
    !generatingFormat;

  const preview = useMemo(() => {
    const intern = internName.trim() || '[INTERN NAME]';
    const internFirst = firstName(internName);
    return {
      intern,
      internFirst,
      issued: formatDate(issuedDate),
      start: formatDate(startDate),
      end: formatDate(endDate),
      responsibility: normalizeResponsibilitySummary(internName, responsibilitySummary),
    };
  }, [endDate, internName, issuedDate, responsibilitySummary, startDate]);

  async function generateLetter(format: 'pdf' | 'docx') {
    if (!canGenerate) return;
    setGeneratingFormat(format);
    setError(null);
    setSuccess(null);

    try {
      const res = await fetch(`${API_BASE}/hr-documents/internship-completion?format=${format}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          intern_name: internName.trim(),
          programme: programme.trim(),
          start_date: startDate,
          end_date: endDate,
          issued_date: issuedDate,
          responsibility_summary: responsibilitySummary.trim(),
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || 'Could not generate the internship completion letter.');
      }

      downloadBlob(
        await res.blob(),
        readDownloadFilename(res.headers.get('Content-Disposition'), `Internship_Completion_Letter.${format}`)
      );
      setSuccess(`Internship completion letter ${format === 'pdf' ? 'PDF' : 'Word document'} generated.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not generate the internship completion letter.');
    } finally {
      setGeneratingFormat(null);
    }
  }

  return (
    <div className="animate-fade-up">
      <div className="mb-7 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="mb-1 text-2xl font-bold tracking-tight text-[#2F3437]">HR Documents</h1>
          <p className="text-sm text-gray-500">
            Generate formal ReKnew HR letters from approved templates.
          </p>
        </div>
        <Badge variant="sage">Admin Console</Badge>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <Card>
          <CardHeader title="Templates" icon={<FileText size={17} />} />
          <div className="space-y-2 p-4">
            {templates.map((template) => {
              const Icon = template.icon;
              return (
                <button
                  key={template.key}
                  className={`flex w-full items-center gap-3 rounded-lg border px-3 py-3 text-left transition-all ${
                    template.active
                      ? 'border-olive bg-hover-bg text-[#2F3437]'
                      : 'border-[#E5E7EB] text-gray-500'
                  }`}
                  disabled={!template.active}
                >
                  <Icon size={18} className={template.active ? 'text-olive' : 'text-gray-400'} />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold">{template.label}</span>
                    {!template.active && <span className="text-xs text-gray-400">Coming soon</span>}
                  </span>
                </button>
              );
            })}
          </div>
        </Card>

        <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,520px)_minmax(520px,1fr)]">
          <Card>
            <CardHeader title="Internship Completion Details" icon={<FileCheck2 size={17} />} />
            <div className="space-y-4 p-5">
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

              <label className="space-y-1.5">
                <span className="text-xs font-semibold text-gray-500">Intern Name</span>
                <input
                  value={internName}
                  onChange={(event) => setInternName(event.target.value)}
                  className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                  placeholder="Anusreya Sundararajan"
                />
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-semibold text-gray-500">Programme / Team</span>
                <input
                  value={programme}
                  onChange={(event) => setProgramme(event.target.value)}
                  className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                  placeholder="Agentic Commerce"
                />
              </label>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">Start Date</span>
                  <input
                    value={startDate}
                    onChange={(event) => setStartDate(event.target.value)}
                    type="date"
                    className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                  />
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-gray-500">End Date</span>
                  <input
                    value={endDate}
                    onChange={(event) => setEndDate(event.target.value)}
                    type="date"
                    className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                  />
                </label>
              </div>

              <label className="space-y-1.5">
                <span className="text-xs font-semibold text-gray-500">Date of Issue</span>
                <input
                  value={issuedDate}
                  onChange={(event) => setIssuedDate(event.target.value)}
                  type="date"
                  className="w-full rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm outline-none focus:border-olive"
                />
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-semibold text-gray-500">Main Body of Intern's Responsibility</span>
                <textarea
                  value={responsibilitySummary}
                  onChange={(event) => setResponsibilitySummary(event.target.value)}
                  rows={6}
                  className="w-full resize-none rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm leading-6 outline-none focus:border-olive"
                />
              </label>

              <div className="flex flex-col justify-end gap-2 sm:flex-row">
                <Button
                  onClick={() => generateLetter('docx')}
                  disabled={!canGenerate}
                  variant="ghost"
                  icon={generatingFormat === 'docx' ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
                >
                  {generatingFormat === 'docx' ? 'Generating' : 'Download Word'}
                </Button>
                <Button
                  onClick={() => generateLetter('pdf')}
                  disabled={!canGenerate}
                  icon={generatingFormat === 'pdf' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
                >
                  {generatingFormat === 'pdf' ? 'Generating' : 'Download PDF'}
                </Button>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Letter Preview" icon={<ScrollText size={17} />} />
            <div className="bg-[#F3F4F1] p-5">
              <div className="mx-auto min-h-[760px] max-w-[650px] bg-white px-14 py-10 text-[13px] leading-6 text-[#171717] shadow-sm">
                <div className="mb-12 flex justify-end">
                  <img src="/reknew-wordmark.png" alt="ReKnew" className="h-8 w-auto object-contain" />
                </div>
                <h2 className="mb-7 text-center text-lg font-bold">Internship Completion Letter</h2>
                <p className="mb-5">{preview.issued}</p>
                <p className="mb-6">
                  <strong>ReKnew Business Solutions Inc.</strong>
                  <br />
                  7800 N. Dallas Pkwy, Ste. 320
                  <br />
                  Plano, TX 75024
                </p>
                <p className="mb-5">To whom it may concern,</p>
                <p className="mb-5">
                  We are pleased to confirm that {preview.intern} successfully completed their internship with ReKnew
                  from {preview.start} to {preview.end}.
                </p>
                <p className="mb-5">During the internship, {preview.responsibility}</p>
                <p className="mb-5">
                  At ReKnew, we believe in providing practical exposure and meaningful learning opportunities, and{' '}
                  {preview.internFirst} embraced those opportunities with dedication and enthusiasm.
                </p>
                <p className="mb-5">
                  We sincerely appreciate the effort and positive contribution made during the internship and are
                  confident that the experience gained here will support future academic and professional success.
                </p>
                <p className="mb-5">We wish {preview.internFirst} all the very best in future endeavors.</p>
                <p className="mb-8">Sincerely,</p>
                <img
                  src="/murali-sajja-signature.png"
                  alt="Murali Sajja signature"
                  className="mb-2 h-11 w-36 object-contain object-left"
                />
                <p className="font-bold">
                  Murali Sajja | CEO
                  <br />
                  ReKnew | reknew.ai
                </p>
                <div className="mt-24 border-t border-black pt-3 text-xs text-gray-400">
                  <span>© ReKnew. All Rights Reserved.</span>
                  <span className="float-right">www.reknew.ai</span>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

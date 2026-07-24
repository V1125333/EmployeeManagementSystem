import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Download, FileText, Loader2, Search, Upload, X } from 'lucide-react';

import { Button } from '@/components/ui';
import { useToast } from '@/components/ui/Toast';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

type DocumentCategory = 'payroll' | 'policy' | 'personal' | 'certificate';
type DocumentStatus = 'verified' | 'action_needed' | 'none';

interface EmployeeDocument {
  id: string;
  name: string;
  category: DocumentCategory;
  folder: string;
  size: string;
  sizeBytes?: number;
  uploadedAt: string;
  status: DocumentStatus;
  tag?: string | null;
}

interface FolderDefinition {
  category: DocumentCategory;
  name: string;
  helper: string;
  iconBackground: string;
  iconColor: string;
  icon: React.ReactNode;
}

function FolderGlyph({ type }: { type: DocumentCategory }) {
  if (type === 'payroll') {
    return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 3h12v18l-2.2-1.4L13.9 21 12 19.6 10.1 21l-1.9-1.4L6 21V3Z"/><path d="M9 8h6M9 12h6M9 16h4"/></svg>;
  }
  if (type === 'policy') {
    return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 4.5A2.5 2.5 0 0 1 7.5 2H19v18H7.5A2.5 2.5 0 0 0 5 22V4.5Z"/><path d="M5 19.5A2.5 2.5 0 0 1 7.5 17H19M9 7h6M9 11h5"/></svg>;
  }
  if (type === 'personal') {
    return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8" cy="10" r="2"/><path d="M5.5 16c.5-2 1.4-3 2.5-3s2 .9 2.5 3M13 9h5M13 13h5M13 16h3"/></svg>;
  }
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4.5"/><path d="m9 12-1 9 4-2 4 2-1-9M10 8l1.2 1.2L14 6.5"/></svg>;
}

const FOLDERS: FolderDefinition[] = [
  { category: 'payroll', name: 'Payroll', helper: 'Payslips, Form 16, salary and bonus letters', iconBackground: '#eef3ec', iconColor: '#5b8c5a', icon: <FolderGlyph type="payroll" /> },
  { category: 'policy', name: 'Policy & Company', helper: 'Handbooks, conduct and company policies', iconBackground: '#eaeef6', iconColor: '#5a6f9e', icon: <FolderGlyph type="policy" /> },
  { category: 'personal', name: 'Personal', helper: 'Identity, legal and employment documents', iconBackground: '#fbeee1', iconColor: '#d97a34', icon: <FolderGlyph type="personal" /> },
  { category: 'certificate', name: 'Certificates', helper: 'Degrees, qualifications and credentials', iconBackground: '#f5f0e6', iconColor: '#8a7a5c', icon: <FolderGlyph type="certificate" /> },
];

function roleKey(role?: string) {
  return (role || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function inferCategory(name: string): DocumentCategory {
  const value = name.toLowerCase().replace(/[_-]/g, ' ');
  if (['payslip', 'pay slip', 'form 16', 'salary', 'bonus letter'].some((term) => value.includes(term))) return 'payroll';
  if (['policy', 'handbook', 'code of conduct', 'company guideline'].some((term) => value.includes(term))) return 'policy';
  if (['certificate', 'certification', 'degree', 'college', 'diploma', 'training completion'].some((term) => value.includes(term))) return 'certificate';
  return 'personal';
}

function formatDate(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function timeValue(value?: string | null) {
  const parsed = value ? new Date(value).getTime() : 0;
  return Number.isNaN(parsed) ? 0 : parsed;
}

function FileGlyph() {
  return <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v5h5"/></svg>;
}

function UploadDialog({
  document,
  admin,
  saving,
  error,
  onClose,
  onSave,
}: {
  document?: EmployeeDocument | null;
  admin: boolean;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSave: (file: File, category: DocumentCategory) => void;
}) {
  const allowedCategories = admin ? FOLDERS : FOLDERS.filter((folder) => ['personal', 'certificate'].includes(folder.category));
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<DocumentCategory>(document?.category || 'personal');

  const selectFile = (nextFile: File | null) => {
    setFile(nextFile);
    if (!nextFile || document) return;
    const inferred = inferCategory(nextFile.name);
    setCategory(admin || ['personal', 'certificate'].includes(inferred) ? inferred : 'personal');
  };

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-[#1f2430]/35 p-5 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="document-upload-title">
      <div className="w-full max-w-[560px] overflow-hidden rounded-2xl border border-[#ece5d8] bg-white shadow-[0_24px_70px_rgba(60,40,10,.22)]">
        <div className="flex items-start justify-between border-b border-[#f0e7d8] px-6 py-5">
          <div><h2 id="document-upload-title" className="text-lg font-bold text-[#1f2430]">{document ? 'Update document' : 'Upload document'}</h2><p className="mt-1 text-sm text-[#8a8371]">Choose the file and confirm the folder where it belongs.</p></div>
          <button type="button" onClick={onClose} disabled={saving} className="rounded-lg p-2 text-[#a99e8a] hover:bg-[#f7f3ec]" aria-label="Close"><X size={18} /></button>
        </div>
        <div className="space-y-5 p-6">
          {error && <div className="rounded-xl border border-[#c0503a]/20 bg-[#fbe9e4] px-4 py-3 text-sm text-[#c0503a]">{error}</div>}
          <label className="block"><span className="mb-2 block text-xs font-bold uppercase tracking-[.08em] text-[#8a8371]">File</span><span className="flex min-h-[104px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-[#d8cbb5] bg-[#fdfbf7] px-4 text-center text-sm text-[#8a8371] hover:border-[#d97a34]"><Upload className="mb-2 text-[#d97a34]" size={20} />{file ? <strong className="max-w-full truncate text-[#1f2430]">{file.name}</strong> : 'PDF, Word, JPG or PNG · maximum 10 MB'}<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.webp" className="hidden" onChange={(event) => selectFile(event.target.files?.[0] || null)} /></span></label>
          <label className="block"><span className="mb-2 block text-xs font-bold uppercase tracking-[.08em] text-[#8a8371]">Folder</span><select value={category} onChange={(event) => setCategory(event.target.value as DocumentCategory)} className="h-12 w-full rounded-xl border border-[#ece5d8] bg-[#faf8f3] px-4 text-sm font-semibold text-[#1f2430] outline-none focus:border-[#d97a34]">{allowedCategories.map((folder) => <option key={folder.category} value={folder.category}>{folder.name} — {folder.helper}</option>)}</select></label>
          {!admin && <p className="rounded-xl bg-[#fbf5ea] px-4 py-3 text-xs leading-5 text-[#8a6a3a]">Payroll and Policy & Company files are managed by HR and are download-only for employees.</p>}
        </div>
        <div className="flex justify-end gap-3 border-t border-[#f0e7d8] px-6 py-4"><Button variant="ghost" onClick={onClose} disabled={saving}>Cancel</Button><Button onClick={() => file && onSave(file, category)} disabled={!file || saving} icon={saving ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}>{saving ? 'Uploading…' : document ? 'Update file' : 'Upload file'}</Button></div>
      </div>
    </div>
  );
}

export function EmployeeDocumentsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [documents, setDocuments] = useState<EmployeeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [activeFolder, setActiveFolder] = useState<DocumentCategory | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [updateDocument, setUpdateDocument] = useState<EmployeeDocument | null>(null);
  const [saving, setSaving] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const admin = ['super_admin', 'admin', 'hr_admin', 'global_access'].includes(roleKey(user?.role));
  const headers = useMemo(() => ({ 'x-user-id': user?.id || '', 'x-user-email': user?.email || '' }), [user]);

  const loadDocuments = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE}/documents`, { headers });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail || 'Could not load documents.');
      setDocuments(Array.isArray(body) ? body : body?.items || []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load documents.');
    } finally {
      setLoading(false);
    }
  }, [headers, user]);

  useEffect(() => { loadDocuments(); }, [loadDocuments]);

  const sortedDocuments = useMemo(() => [...documents].sort((left, right) => timeValue(right.uploadedAt) - timeValue(left.uploadedAt)), [documents]);
  const normalizedSearch = search.trim().toLowerCase();
  const visibleDocuments = useMemo(() => sortedDocuments.filter((document) => !normalizedSearch || `${document.name} ${document.folder}`.toLowerCase().includes(normalizedSearch)), [normalizedSearch, sortedDocuments]);
  const newestPayslipId = sortedDocuments.find((document) => document.category === 'payroll')?.id;
  const tableDocuments = activeFolder ? visibleDocuments.filter((document) => document.category === activeFolder) : showAll ? visibleDocuments : visibleDocuments.slice(0, 5);
  const activeDefinition = FOLDERS.find((folder) => folder.category === activeFolder);

  const saveDocument = async (file: File, category: DocumentCategory) => {
    setSaving(true);
    setUploadError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('category', category);
      const target = updateDocument ? `${API_BASE}/documents/${updateDocument.id}` : `${API_BASE}/documents`;
      const response = await fetch(target, { method: updateDocument ? 'PUT' : 'POST', headers, body: formData });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail || 'Could not save document.');
      setShowUpload(false);
      setUpdateDocument(null);
      showToast({ message: updateDocument ? 'Document updated.' : 'Document uploaded.' });
      await loadDocuments();
    } catch (saveError) {
      setUploadError(saveError instanceof Error ? saveError.message : 'Could not save document.');
    } finally {
      setSaving(false);
    }
  };

  const downloadDocument = async (document: EmployeeDocument) => {
    try {
      const response = await fetch(`${API_BASE}/documents/${document.id}/download`, { headers });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || 'Could not download document.');
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement('a');
      anchor.href = url;
      anchor.download = document.name;
      window.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      showToast({ message: downloadError instanceof Error ? downloadError.message : 'Could not download document.' });
    }
  };

  const openUpdate = (document: EmployeeDocument) => {
    setUploadError('');
    setUpdateDocument(document);
  };

  return (
    <div className="-mx-[var(--layout-main-padding-x)] -my-[var(--layout-main-padding-y)] min-h-[calc(100vh-3.5rem)] bg-[#f7f3ec] px-8 py-[26px] text-[#1f2430] [font-family:'Instrument_Sans',sans-serif]">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div><h1 className="text-[26px] font-bold tracking-[-.5px]">Documents</h1><p className="mt-1 text-sm text-[#7a7263]">Access payslips, policy documents, certificates, and personal files.</p></div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="relative min-w-[260px]"><Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-[#a99e8a]"/><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search all documents..." className="h-12 w-full rounded-[11px] border border-[#ece5d8] bg-white pl-11 pr-4 text-sm outline-none placeholder:text-[#a99e8a] focus:border-[#d97a34]" /></label>
          <button type="button" onClick={() => { setUploadError(''); setShowUpload(true); }} className="h-12 rounded-[11px] bg-[#d97a34] px-5 text-sm font-bold text-white shadow-[0_3px_10px_rgba(217,122,52,.25)] transition-colors hover:bg-[#b8611f]">+ Upload</button>
        </div>
      </div>

      {error && <div className="mt-5 rounded-xl border border-[#c0503a]/20 bg-[#fbe9e4] px-4 py-3 text-sm text-[#c0503a]">{error} <button type="button" onClick={loadDocuments} className="ml-2 font-bold underline">Try again</button></div>}

      <section className="mt-[22px]" aria-labelledby="document-folders-heading">
        <h2 id="document-folders-heading" className="mb-3 text-[11px] font-bold uppercase tracking-[.04em] text-[#a99e8a]">Folders</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {FOLDERS.map((folder) => {
            const rows = sortedDocuments.filter((document) => document.category === folder.category);
            const latest = rows[0];
            const needsAction = rows.some((document) => document.status === 'action_needed');
            return (
              <button key={folder.category} type="button" onClick={() => { setShowAll(false); setActiveFolder(folder.category); }} className="group relative flex min-h-[252px] flex-col gap-[15px] rounded-2xl border border-[#ece5d8] bg-white p-5 text-left transition-all hover:-translate-y-0.5 hover:border-[#d97a34] hover:shadow-[0_8px_20px_rgba(217,122,52,.12)]">
                {needsAction && <span className="absolute right-5 top-5 h-[9px] w-[9px] rounded-full bg-[#c0503a]" aria-label="Action needed" />}
                <span className="flex h-[46px] w-[46px] items-center justify-center rounded-[13px]" style={{ background: folder.iconBackground, color: folder.iconColor }}>{folder.icon}</span>
                <div><div className="text-[15px] font-bold">{folder.name}</div><div className="mt-1 text-xs text-[#a99e8a]">{rows.length} {rows.length === 1 ? 'file' : 'files'} · updated {latest ? formatDate(latest.uploadedAt) : '—'}</div></div>
                <div className="w-full border-t border-[#f4eee2] pt-3">
                  {rows.length ? rows.slice(0, 2).map((document) => <div key={document.id} className="flex min-w-0 items-center gap-2 py-1 text-xs text-[#8a8371]"><span className="text-[#b9aa90]">▭</span><span className="truncate">{document.name}{document.status === 'action_needed' ? ' — action needed' : ''}</span></div>) : <div className="flex items-center gap-2 py-1 text-xs text-[#a99e8a]"><span>▭</span><span>No files yet</span></div>}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <section className="mt-[22px] overflow-hidden rounded-2xl border border-[#ece5d8] bg-white" aria-labelledby="recent-documents-heading">
        <div className="flex items-center justify-between px-7 py-5">
          <div className="flex items-center gap-3">{(activeDefinition || showAll) && <button type="button" onClick={() => { setActiveFolder(null); setShowAll(false); }} className="rounded-lg p-1.5 text-[#8a8371] hover:bg-[#f7f3ec]" aria-label="Back to recent files"><ArrowLeft size={17}/></button>}<h2 id="recent-documents-heading" className="text-[15.5px] font-bold">{activeDefinition ? activeDefinition.name : showAll ? 'All files' : 'Recent files'}</h2>{(activeDefinition || showAll) && <span className="rounded-full bg-[#f5f0e6] px-2.5 py-1 text-[11px] font-bold text-[#8a7a5c]">{tableDocuments.length}</span>}</div>
          {!activeDefinition && !showAll && sortedDocuments.length > 5 && <button type="button" onClick={() => setShowAll(true)} className="text-sm font-semibold text-[#d06a21]">View all <ArrowRight size={14} className="inline" /></button>}
        </div>
        {loading ? <div className="flex min-h-[260px] items-center justify-center text-sm text-[#8a8371]"><Loader2 className="mr-2 animate-spin" size={18}/>Loading documents…</div> : tableDocuments.length === 0 ? (
          <div className="m-7 flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-[#dfd3c0] text-center"><FileText size={28} className="text-[#cbbda6]"/><p className="mt-3 text-sm font-semibold text-[#8a8371]">{normalizedSearch ? 'No documents match your search.' : activeDefinition ? `No files in ${activeDefinition.name} yet.` : 'No documents uploaded yet.'}</p>{(!activeDefinition || ['personal', 'certificate'].includes(activeDefinition.category) || admin) && !normalizedSearch && <button type="button" onClick={() => setShowUpload(true)} className="mt-3 text-sm font-bold text-[#d06a21]">Upload a document</button>}</div>
        ) : (
          <div className="overflow-x-auto px-7 pb-4">
            <div className="min-w-[880px]">
              <div className="grid grid-cols-[2fr_1fr_1fr_1fr_110px] gap-3 border-b border-[#f0e7d8] px-1 pb-3 text-[10.5px] font-bold uppercase tracking-[.05em] text-[#a99e8a]"><span>Name</span><span>Folder</span><span>Size</span><span>Modified</span><span className="text-right">Action</span></div>
              {tableDocuments.map((document) => {
                const latestPayslip = document.id === newestPayslipId;
                const canUpdate = admin || ['personal', 'certificate'].includes(document.category);
                return <div key={document.id} className="grid grid-cols-[2fr_1fr_1fr_1fr_110px] items-center gap-3 border-b border-[#f6f0e6] px-1 py-3.5 last:border-b-0 hover:bg-[#fdfbf7]">
                  <div className="flex min-w-0 items-center gap-3"><span className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-[10px] bg-[#f5f0e6] text-[#8a7a5c]"><FileGlyph/></span><div className="min-w-0"><div className="truncate text-[13.5px] font-semibold">{document.name}</div>{document.status === 'action_needed' ? <div className="mt-0.5 text-[11px] font-semibold text-[#c0503a]">Action needed</div> : latestPayslip ? <div className="mt-0.5 text-[11px] font-semibold text-[#3f9b52]">Latest</div> : document.tag ? <div className="mt-0.5 text-[11px] text-[#8a8371]">{document.tag}</div> : null}</div></div>
                  <div className="text-[12.5px] text-[#8a8371]">{document.folder}</div><div className="text-[12.5px] text-[#8a8371]">{document.size || '—'}</div><div className="text-[12.5px] text-[#8a8371]">{formatDate(document.uploadedAt)}</div>
                  <div className="text-right">{canUpdate && document.status === 'action_needed' ? <button type="button" onClick={() => openUpdate(document)} className="text-[12.5px] font-semibold text-[#d06a21] hover:text-[#b8611f]">Update</button> : <button type="button" onClick={() => downloadDocument(document)} className="text-[12.5px] font-semibold text-[#d06a21] hover:text-[#b8611f]">Download</button>}</div>
                </div>;
              })}
            </div>
          </div>
        )}
      </section>
      {(showUpload || updateDocument) && <UploadDialog document={updateDocument} admin={admin} saving={saving} error={uploadError} onClose={() => { if (saving) return; setShowUpload(false); setUpdateDocument(null); setUploadError(''); }} onSave={saveDocument} />}
    </div>
  );
}

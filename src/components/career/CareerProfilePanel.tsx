import { useEffect, useMemo, useRef, useState } from 'react';
import { Award, Briefcase, Download, FileText, Plus, Save, Sparkles, Trash2, UploadCloud, X } from 'lucide-react';
import { Badge, Button, Card } from '@/components/ui';
import {
  careerProfileCompleteness,
  emptyCareerProfile,
  getCareerProfile,
  getSeededCareerProfile,
  saveCareerProfile,
  type CareerCertification,
  type CareerProfileData,
  type CareerProject,
  type CareerSkill,
} from '@/lib/careerProfileStore';
import { cn } from '@/utils/cn';

type EmployeeRef = {
  id: string;
  name: string;
  email?: string | null;
  designation?: string | null;
  department?: string | null;
};

const skillLevels = ['Beginner', 'Intermediate', 'Advanced', 'Expert'];

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function resumePlaceholder(employeeName: string) {
  const safeName = employeeName.trim().replace(/\s+/g, '_') || 'Employee';
  return `${safeName}_Resume.pdf`;
}

function formatFileSize(size: number) {
  if (!size) return '';
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  textarea,
  type = 'text',
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  textarea?: boolean;
  type?: string;
}) {
  const inputClass = 'w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm font-medium text-[var(--color-brand-navy)] outline-none focus:border-olive';
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12px] font-bold uppercase tracking-wide text-gray-400">{label}</span>
      {textarea ? (
        <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={4} placeholder={placeholder} className={cn(inputClass, 'resize-none')} />
      ) : (
        <input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className={inputClass} />
      )}
    </label>
  );
}

function formatDisplayDate(value: string) {
  if (!value) return '';
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
}

function EmptyBlock({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-warm-bg px-4 py-6 text-center">
      <div className="text-sm font-bold text-[var(--color-brand-navy)]">{title}</div>
      <div className="mt-1 text-sm text-gray-500">{description}</div>
    </div>
  );
}

export function CareerProfilePanel({
  employee,
  editable = false,
  onSaved,
}: {
  employee: EmployeeRef;
  editable?: boolean;
  onSaved?: () => void;
}) {
  const [profile, setProfile] = useState<CareerProfileData>(emptyCareerProfile);
  const [savedProfile, setSavedProfile] = useState<CareerProfileData>(emptyCareerProfile);
  const [savedAt, setSavedAt] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const completeness = useMemo(() => careerProfileCompleteness(profile), [profile]);
  const hasUnsavedChanges = editable && JSON.stringify(profile) !== JSON.stringify(savedProfile);

  useEffect(() => {
    const storedProfile = getSeededCareerProfile(employee.id, employee.name, employee.email);
    setProfile(storedProfile);
    setSavedProfile(storedProfile);
    setSavedAt('');
  }, [employee.email, employee.id, employee.name]);

  const update = (patch: Partial<CareerProfileData>) => setProfile((current) => ({ ...current, ...patch }));
  const save = () => {
    saveCareerProfile(employee.id, profile);
    setSavedProfile(profile);
    setSavedAt(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    onSaved?.();
  };

  const discardChanges = () => {
    setProfile(savedProfile);
    setSavedAt('');
  };

  const handleResumeFile = (file?: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      update({
        resumeName: file.name,
        resumeUpdatedAt: new Date().toISOString(),
        resumeDataUrl: typeof reader.result === 'string' ? reader.result : '',
        resumeMimeType: file.type,
        resumeSize: file.size,
      });
    };
    reader.readAsDataURL(file);
  };

  const clearResume = () => update({
    resumeName: '',
    resumeUpdatedAt: '',
    resumeDataUrl: '',
    resumeMimeType: '',
    resumeSize: 0,
  });

  const addSkill = () => update({
    skills: [...profile.skills, { id: makeId(), name: '', level: 'Intermediate', years: '', lastUsed: '' }],
  });
  const updateSkill = (id: string, patch: Partial<CareerSkill>) => update({
    skills: profile.skills.map((skill) => skill.id === id ? { ...skill, ...patch } : skill),
  });
  const addProject = () => update({
    projects: [...profile.projects, { id: makeId(), name: '', role: '', duration: '', stack: '', summary: '' }],
  });
  const updateProject = (id: string, patch: Partial<CareerProject>) => update({
    projects: profile.projects.map((project) => project.id === id ? { ...project, ...patch } : project),
  });
  const addCertification = () => update({
    certifications: [...profile.certifications, { id: makeId(), name: '', issuer: '', issuedOn: '' }],
  });
  const updateCertification = (id: string, patch: Partial<CareerCertification>) => update({
    certifications: profile.certifications.map((cert) => cert.id === id ? { ...cert, ...patch } : cert),
  });

  return (
    <div className={cn('space-y-5', editable && 'pb-24')}>
      <Card className="p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-lg font-bold text-[var(--color-brand-navy)]">
              <Sparkles size={18} className="text-olive" />
              Career Profile
            </div>
            <div className="mt-1 text-sm text-gray-500">
              {employee.name}{employee.designation ? ` · ${employee.designation}` : ''}{employee.department ? ` · ${employee.department}` : ''}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={completeness >= 75 ? 'success' : completeness >= 40 ? 'warning' : 'neutral'}>{completeness}% complete</Badge>
            {editable && (
              <Button icon={<Save size={15} />} onClick={save}>Save Career Profile</Button>
            )}
          </div>
        </div>
        {savedAt && <div className="mt-3 rounded-lg bg-status-success/10 px-3 py-2 text-sm font-semibold text-status-success">Saved at {savedAt}</div>}
      </Card>

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="p-5">
          <div className="mb-4 text-sm font-bold text-[var(--color-brand-navy)]">Summary & Preferences</div>
          {editable ? (
            <div className="space-y-4">
              <Field label="Career Summary" value={profile.summary} onChange={(value) => update({ summary: value })} textarea placeholder="Briefly describe your strengths, domains, and recent work." />
              <Field label="Interested Roles" value={profile.targetRoles} onChange={(value) => update({ targetRoles: value })} placeholder="Frontend Engineer, Data Analyst, QA Automation..." />
              <Field label="Preferred Skills / Domains" value={profile.preferredSkills} onChange={(value) => update({ preferredSkills: value })} placeholder="React, FastAPI, healthcare, fintech..." />
              <Field label="Work Preference" value={profile.workPreference} onChange={(value) => update({ workPreference: value })} placeholder="Remote, hybrid, client-facing, internal tools..." />
            </div>
          ) : (
            <div className="space-y-4 text-sm">
              <div><div className="text-xs font-bold uppercase tracking-wide text-gray-400">Summary</div><p className="mt-1 leading-6 text-[var(--color-brand-navy)]">{profile.summary || 'No summary added yet.'}</p></div>
              <div><div className="text-xs font-bold uppercase tracking-wide text-gray-400">Interested Roles</div><p className="mt-1 text-gray-600">{profile.targetRoles || 'Not specified'}</p></div>
              <div><div className="text-xs font-bold uppercase tracking-wide text-gray-400">Preferred Skills / Domains</div><p className="mt-1 text-gray-600">{profile.preferredSkills || 'Not specified'}</p></div>
              <div><div className="text-xs font-bold uppercase tracking-wide text-gray-400">Work Preference</div><p className="mt-1 text-gray-600">{profile.workPreference || 'Not specified'}</p></div>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-bold text-[var(--color-brand-navy)]"><FileText size={16} className="text-olive" /> Resume</div>
          {editable ? (
            <div className="space-y-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                onChange={(event) => handleResumeFile(event.target.files?.[0])}
              />
              {profile.resumeName ? (
                <div className="rounded-xl border border-[var(--color-border)] bg-warm-bg p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-bold text-[var(--color-brand-navy)]">{profile.resumeName}</div>
                      <div className="mt-1 text-xs text-gray-500">
                        {[formatFileSize(profile.resumeSize), profile.resumeUpdatedAt ? `Updated ${new Date(profile.resumeUpdatedAt).toLocaleDateString()}` : ''].filter(Boolean).join(' · ')}
                      </div>
                    </div>
                    <button type="button" onClick={clearResume} className="rounded-lg p-1.5 text-gray-400 transition hover:bg-white hover:text-status-error" aria-label="Remove resume">
                      <X size={15} />
                    </button>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="ghost" icon={<UploadCloud size={14} />} onClick={() => fileInputRef.current?.click()}>Replace Resume</Button>
                    {profile.resumeDataUrl && (
                      <a href={profile.resumeDataUrl} download={profile.resumeName} className="inline-flex items-center gap-1.5 rounded-btn border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-xs font-semibold text-accent transition hover:bg-hover-bg">
                        <Download size={14} />
                        Download
                      </a>
                    )}
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex min-h-[140px] w-full flex-col items-center justify-center rounded-xl border border-dashed border-[var(--color-border)] bg-warm-bg px-4 py-6 text-center transition hover:border-olive/40 hover:bg-olive/5"
                >
                  <UploadCloud size={24} className="text-olive" />
                  <div className="mt-3 text-sm font-bold text-[var(--color-brand-navy)]">Upload resume</div>
                  <div className="mt-1 text-xs text-gray-500">PDF, DOC, or DOCX. Suggested name: {resumePlaceholder(employee.name)}</div>
                </button>
              )}
            </div>
          ) : profile.resumeName ? (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-warm-bg px-4 py-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-bold text-[var(--color-brand-navy)]">{profile.resumeName}</div>
                <div className="text-xs text-gray-500">
                  {[formatFileSize(profile.resumeSize), profile.resumeUpdatedAt ? new Date(profile.resumeUpdatedAt).toLocaleDateString() : 'Date not recorded'].filter(Boolean).join(' · ')}
                </div>
              </div>
              {profile.resumeDataUrl ? (
                <a href={profile.resumeDataUrl} download={profile.resumeName} className="inline-flex items-center gap-1.5 rounded-btn border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-xs font-semibold text-accent transition hover:bg-hover-bg">
                  <Download size={14} />
                  Download
                </a>
              ) : (
                <Button size="sm" variant="ghost" icon={<Download size={14} />} disabled>Download</Button>
              )}
            </div>
          ) : (
            <EmptyBlock title="No resume added" description="Ask the employee to upload or add a resume reference." />
          )}
        </Card>
      </div>

      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="text-sm font-bold text-[var(--color-brand-navy)]">Skills</div>
          {editable && <Button size="sm" variant="ghost" icon={<Plus size={14} />} onClick={addSkill}>Add Skill</Button>}
        </div>
        {profile.skills.length === 0 ? <EmptyBlock title="No skills added" description="Add primary and secondary skills to improve discoverability." /> : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {profile.skills.map((skill) => (
              <div key={skill.id} className="rounded-xl border border-[var(--color-border)] bg-white p-4">
                {editable ? (
                  <div className="space-y-3">
                    <Field label="Skill" value={skill.name} onChange={(value) => updateSkill(skill.id, { name: value })} />
                    <div className="grid grid-cols-3 gap-2">
                      <label className="block">
                        <span className="mb-1.5 block text-[12px] font-bold uppercase tracking-wide text-gray-400">Level</span>
                        <select value={skill.level} onChange={(event) => updateSkill(skill.id, { level: event.target.value })} className="w-full rounded-lg border border-[var(--color-border)] bg-white px-2 py-2 text-sm outline-none focus:border-olive">
                          {skillLevels.map((level) => <option key={level}>{level}</option>)}
                        </select>
                      </label>
                      <Field label="Years" value={skill.years} onChange={(value) => updateSkill(skill.id, { years: value })} />
                      <Field label="Last Used" value={skill.lastUsed} onChange={(value) => updateSkill(skill.id, { lastUsed: value })} />
                    </div>
                    <button type="button" onClick={() => update({ skills: profile.skills.filter((item) => item.id !== skill.id) })} className="flex items-center gap-1 text-xs font-bold text-status-error"><Trash2 size={12} /> Remove</button>
                  </div>
                ) : (
                  <>
                    <div className="font-bold text-[var(--color-brand-navy)]">{skill.name || 'Unnamed skill'}</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge variant="olive">{skill.level}</Badge>
                      {skill.years && <Badge variant="neutral">{skill.years} yrs</Badge>}
                      {skill.lastUsed && <Badge variant="neutral">Last used {skill.lastUsed}</Badge>}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-bold text-[var(--color-brand-navy)]"><Briefcase size={16} className="text-olive" /> Project Experience</div>
          {editable && <Button size="sm" variant="ghost" icon={<Plus size={14} />} onClick={addProject}>Add Project</Button>}
        </div>
        {profile.projects.length === 0 ? <EmptyBlock title="No project experience added" description="Add internal, client, training, or POC experience." /> : (
          <div className="space-y-3">
            {profile.projects.map((project) => (
              <div key={project.id} className="rounded-xl border border-[var(--color-border)] bg-white p-4">
                {editable ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Project / POC" value={project.name} onChange={(value) => updateProject(project.id, { name: value })} />
                    <Field label="Role" value={project.role} onChange={(value) => updateProject(project.id, { role: value })} />
                    <Field label="Duration" value={project.duration} onChange={(value) => updateProject(project.id, { duration: value })} />
                    <Field label="Tech Stack" value={project.stack} onChange={(value) => updateProject(project.id, { stack: value })} />
                    <div className="md:col-span-2"><Field label="Summary" value={project.summary} onChange={(value) => updateProject(project.id, { summary: value })} textarea /></div>
                    <button type="button" onClick={() => update({ projects: profile.projects.filter((item) => item.id !== project.id) })} className="flex items-center gap-1 text-xs font-bold text-status-error"><Trash2 size={12} /> Remove project</button>
                  </div>
                ) : (
                  <>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-bold text-[var(--color-brand-navy)]">{project.name || 'Unnamed project'}</div>
                        <div className="mt-1 text-sm text-gray-500">{project.role || 'Role not specified'}{project.duration ? ` · ${project.duration}` : ''}</div>
                      </div>
                      {project.stack && <Badge variant="neutral">{project.stack}</Badge>}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-gray-600">{project.summary || 'No summary added.'}</p>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-bold text-[var(--color-brand-navy)]"><Award size={16} className="text-olive" /> Certifications</div>
          {editable && <Button size="sm" variant="ghost" icon={<Plus size={14} />} onClick={addCertification}>Add Certification</Button>}
        </div>
        {profile.certifications.length === 0 ? <EmptyBlock title="No certifications added" description="Add courses, certificates, and credentials." /> : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {profile.certifications.map((certification) => (
              <div key={certification.id} className="rounded-xl border border-[var(--color-border)] bg-white p-4">
                {editable ? (
                  <div className="space-y-3">
                    <Field label="Certification" value={certification.name} onChange={(value) => updateCertification(certification.id, { name: value })} />
                    <Field label="Issuer" value={certification.issuer} onChange={(value) => updateCertification(certification.id, { issuer: value })} />
                    <Field label="Issued On" type="date" value={certification.issuedOn} onChange={(value) => updateCertification(certification.id, { issuedOn: value })} />
                    <button type="button" onClick={() => update({ certifications: profile.certifications.filter((item) => item.id !== certification.id) })} className="flex items-center gap-1 text-xs font-bold text-status-error"><Trash2 size={12} /> Remove</button>
                  </div>
                ) : (
                  <>
                    <div className="font-bold text-[var(--color-brand-navy)]">{certification.name || 'Unnamed certification'}</div>
                    <div className="mt-1 text-sm text-gray-500">{certification.issuer || 'Issuer not recorded'}</div>
                    {certification.issuedOn && <div className="mt-2 text-xs font-semibold text-gray-400">{formatDisplayDate(certification.issuedOn)}</div>}
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {hasUnsavedChanges && (
        <div className="fixed bottom-4 left-1/2 z-40 w-[min(760px,calc(100vw-2rem))] -translate-x-1/2 rounded-2xl border border-[var(--color-border)] bg-white px-4 py-3 shadow-[0_18px_48px_rgba(17,24,39,0.18)]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-bold text-[var(--color-brand-navy)]">Unsaved career profile changes</div>
              <div className="text-xs text-gray-500">Save before leaving this page so your skills, resume, and experience are kept.</div>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button variant="ghost" onClick={discardChanges}>Discard</Button>
              <Button icon={<Save size={15} />} onClick={save}>Save Career Profile</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

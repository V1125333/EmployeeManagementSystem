import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui';
import { Drawer } from '@/components/ui/Drawer';

export interface StaffingOption {
  id: string;
  name: string;
  email?: string;
  department?: string | null;
  designation?: string | null;
  role?: string;
  code?: string;
  status?: string;
}

export interface StaffingRequestFormOptions {
  departments: string[];
  designations: string[];
  managers: StaffingOption[];
  projects: StaffingOption[];
  employees: StaffingOption[];
}

export interface StaffingRequestPayload {
  project_name: string;
  project_id?: string | null;
  hiring_manager_id: string;
  department?: string | null;
  role_needed: string;
  designation_needed?: string | null;
  skills_required: string[];
  allocation_percentage: number;
  headcount_needed: number;
  start_date: string;
  end_date?: string | null;
  priority: string;
  reason?: string | null;
  notes?: string | null;
}

export interface EditableStaffingRequest extends Partial<StaffingRequestPayload> {
  id?: string;
}

interface Props {
  open: boolean;
  mode: 'create' | 'edit';
  options: StaffingRequestFormOptions | null;
  currentUserId?: string;
  initial?: EditableStaffingRequest | null;
  saving?: boolean;
  onClose: () => void;
  onSubmit: (payload: StaffingRequestPayload) => void;
}

const emptyForm: StaffingRequestPayload = {
  project_name: '',
  project_id: null,
  hiring_manager_id: '',
  department: '',
  role_needed: '',
  designation_needed: '',
  skills_required: [],
  allocation_percentage: 100,
  headcount_needed: 1,
  start_date: '',
  end_date: null,
  priority: 'medium',
  reason: '',
  notes: '',
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="text-[12px] font-bold text-gray-500">
      {label}
      {children}
    </label>
  );
}

const inputClass = 'mt-1 w-full rounded-xl border border-[#E5E7EB] bg-warm-bg px-3 py-2.5 text-[14px] font-medium text-[#2F3437] outline-none focus:border-olive/40 focus:ring-2 focus:ring-olive/10';

export function StaffingRequestDrawer({
  open,
  mode,
  options,
  currentUserId,
  initial,
  saving,
  onClose,
  onSubmit,
}: Props) {
  const [form, setForm] = useState<StaffingRequestPayload>(emptyForm);
  const [skillsText, setSkillsText] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    const merged = { ...emptyForm, ...(initial || {}) };
    if (!merged.hiring_manager_id && currentUserId) merged.hiring_manager_id = currentUserId;
    setForm({
      ...merged,
      project_id: merged.project_id || null,
      department: merged.department || '',
      designation_needed: merged.designation_needed || '',
      end_date: merged.end_date || null,
      reason: merged.reason || '',
      notes: merged.notes || '',
      skills_required: merged.skills_required || [],
    });
    setSkillsText((merged.skills_required || []).join(', '));
    setError('');
  }, [open, initial, currentUserId]);

  const selectedProject = useMemo(
    () => options?.projects.find((item) => item.id === form.project_id),
    [form.project_id, options?.projects]
  );

  const update = (key: keyof StaffingRequestPayload, value: string | number | string[] | null) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const submit = () => {
    const skills = skillsText.split(',').map((item) => item.trim()).filter(Boolean);
    const payload: StaffingRequestPayload = {
      ...form,
      project_name: form.project_name.trim(),
      role_needed: form.role_needed.trim(),
      department: form.department || null,
      designation_needed: form.designation_needed || null,
      end_date: form.end_date || null,
      reason: form.reason?.trim() || null,
      notes: form.notes?.trim() || null,
      skills_required: skills,
      allocation_percentage: Number(form.allocation_percentage),
      headcount_needed: Number(form.headcount_needed),
    };
    if (!payload.project_name) return setError('Project name is required.');
    if (!payload.hiring_manager_id) return setError('Hiring manager is required.');
    if (!payload.role_needed) return setError('Role needed is required.');
    if (!payload.start_date) return setError('Start date is required.');
    if (payload.end_date && payload.end_date < payload.start_date) return setError('End date must be on or after start date.');
    if (payload.allocation_percentage < 1 || payload.allocation_percentage > 100) return setError('Allocation must be between 1 and 100%.');
    onSubmit(payload);
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={mode === 'create' ? 'New Staffing Request' : 'Edit Staffing Request'}
      subtitle="Capture the demand details HR needs to match available employees."
      width="w-[680px] max-w-[calc(100vw-1.5rem)]"
      footer={(
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs text-status-error">{error}</div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={submit} disabled={saving}>{saving ? 'Saving...' : mode === 'create' ? 'Create Request' : 'Save Changes'}</Button>
          </div>
        </div>
      )}
    >
      <div className="grid gap-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Project">
            <select
              value={form.project_id || ''}
              onChange={(event) => {
                const project = options?.projects.find((item) => item.id === event.target.value);
                update('project_id', event.target.value || null);
                if (project) update('project_name', project.name);
              }}
              className={inputClass}
            >
              <option value="">Manual project name</option>
              {(options?.projects || []).map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Project Name">
            <input value={form.project_name} onChange={(event) => update('project_name', event.target.value)} disabled={Boolean(selectedProject)} className={inputClass} />
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Hiring Manager">
            <select value={form.hiring_manager_id} onChange={(event) => update('hiring_manager_id', event.target.value)} className={inputClass}>
              <option value="">Select manager</option>
              {(options?.managers || []).map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Department">
            <select value={form.department || ''} onChange={(event) => update('department', event.target.value)} className={inputClass}>
              <option value="">Any department</option>
              {(options?.departments || []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Role Needed">
            <input value={form.role_needed} onChange={(event) => update('role_needed', event.target.value)} placeholder="Backend Engineer, QA, Data Analyst..." className={inputClass} />
          </Field>
          <Field label="Designation Needed">
            <select value={form.designation_needed || ''} onChange={(event) => update('designation_needed', event.target.value)} className={inputClass}>
              <option value="">Any designation</option>
              {(options?.designations || []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </Field>
        </div>

        <Field label="Skills Required">
          <input value={skillsText} onChange={(event) => setSkillsText(event.target.value)} placeholder="Python, React, SQL" className={inputClass} />
        </Field>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Field label="Allocation %">
            <input type="number" min={1} max={100} value={form.allocation_percentage} onChange={(event) => update('allocation_percentage', Number(event.target.value))} className={inputClass} />
          </Field>
          <Field label="Headcount">
            <input type="number" min={1} value={form.headcount_needed} onChange={(event) => update('headcount_needed', Number(event.target.value))} className={inputClass} />
          </Field>
          <Field label="Priority">
            <select value={form.priority} onChange={(event) => update('priority', event.target.value)} className={inputClass}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Start Date">
            <input type="date" value={form.start_date} onChange={(event) => update('start_date', event.target.value)} className={inputClass} />
          </Field>
          <Field label="End Date">
            <input type="date" value={form.end_date || ''} onChange={(event) => update('end_date', event.target.value || null)} className={inputClass} />
          </Field>
        </div>

        <Field label="Reason">
          <textarea value={form.reason || ''} onChange={(event) => update('reason', event.target.value)} rows={3} className={inputClass} />
        </Field>
        <Field label="Notes">
          <textarea value={form.notes || ''} onChange={(event) => update('notes', event.target.value)} rows={3} className={inputClass} />
        </Field>
      </div>
    </Drawer>
  );
}

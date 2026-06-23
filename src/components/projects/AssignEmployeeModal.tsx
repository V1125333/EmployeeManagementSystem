import { useEffect, useMemo, useState } from 'react';
import { X, UserPlus } from 'lucide-react';
import { Badge, Button, Card, Avatar } from '@/components/ui';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface ProjectRecord {
  id: string;
  name: string;
  code: string;
}

interface AllocationRecord {
  id: string;
  employee_id: string;
  manager_id: string;
  allocation_percentage: number;
  allocation_role: string;
  billing_type: string;
  status: string;
  start_date: string;
  end_date: string | null;
  notes?: string | null;
}

interface EmployeeOption {
  id: string;
  first_name: string;
  last_name: string;
  work_email: string;
  role: string;
  department: string;
  designation: string | null;
  profile_image_url: string | null;
}

interface AuthUserLike {
  id?: string;
  name: string;
  email: string;
  role: string;
}

interface AssignEmployeeModalProps {
  open: boolean;
  project: ProjectRecord | null;
  user: AuthUserLike | null;
  allocation?: AllocationRecord | null;
  onClose: () => void;
  onAssigned: () => void;
}

function normalizeRole(role?: string) {
  return (role || '').toLowerCase().replace(/\s+/g, '_');
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).map((part) => part[0]).join('').toUpperCase().slice(0, 2) || 'U';
}

function employeeName(employee: EmployeeOption) {
  return `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || employee.work_email;
}

export function AssignEmployeeModal({ open, project, user, allocation, onClose, onAssigned }: AssignEmployeeModalProps) {
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [managers, setManagers] = useState<EmployeeOption[]>([]);
  const [employeeId, setEmployeeId] = useState('');
  const [managerId, setManagerId] = useState(user?.id || '');
  const [allocationRole, setAllocationRole] = useState('Developer');
  const [allocationPercentage, setAllocationPercentage] = useState(100);
  const [billingType, setBillingType] = useState('billable');
  const [status, setStatus] = useState('active');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [capacityMessage, setCapacityMessage] = useState('');
  const [capacityWarning, setCapacityWarning] = useState(false);

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    'x-user-id': user?.id || '',
    'x-user-email': user?.email || '',
    'x-user-role': normalizeRole(user?.role),
  }), [user]);

  useEffect(() => {
    if (!open) return;
    setError('');
    fetch(`${API_BASE}/projects/assignable-employees?limit=250`, { headers })
      .then((res) => res.ok ? res.json() : Promise.reject(new Error('Could not load employees.')))
      .then((data) => {
        const nextEmployees = data.employees || [];
        const nextManagers = data.managers || [];
        setEmployees(nextEmployees);
        setManagers(nextManagers);
        setManagerId((current) => (
          current && nextManagers.some((manager: EmployeeOption) => manager.id === current)
            ? current
            : nextManagers[0]?.id || user?.id || ''
        ));
      })
      .catch((err) => setError(err.message || 'Could not load employees.'));
  }, [headers, open]);

  useEffect(() => {
    if (open) {
      setEmployeeId(allocation?.employee_id || '');
      setManagerId(allocation?.manager_id || '');
      setAllocationRole(allocation?.allocation_role || 'Developer');
      setAllocationPercentage(allocation?.allocation_percentage || 100);
      setBillingType(allocation?.billing_type || 'billable');
      setStatus(allocation?.status || 'active');
      setStartDate(allocation?.start_date || new Date().toISOString().slice(0, 10));
      setEndDate(allocation?.end_date || '');
      setNotes(allocation?.notes || '');
      setError('');
      setCapacityMessage('');
      setCapacityWarning(false);
    }
  }, [allocation, open, user?.id]);

  useEffect(() => {
    if (!open || !employeeId || !startDate || !allocationPercentage) {
      setCapacityMessage('');
      return;
    }
    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          allocation_percentage: String(allocationPercentage),
          start_date: startDate,
        });
        if (endDate) params.set('end_date', endDate);
        if (allocation?.id) params.set('exclude_allocation_id', allocation.id);
        const res = await fetch(`${API_BASE}/allocations/employee/${employeeId}/capacity-check?${params.toString()}`, {
          headers,
          signal: controller.signal,
        });
        const payload = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(payload.detail || 'Capacity check unavailable.');
        const available = payload.available_capacity_percentage ?? payload.available_capacity ?? null;
        const projected = payload.projected_allocation_percentage ?? payload.projected_total ?? null;
        const over = Boolean(payload.is_overallocated || payload.overallocated || (projected !== null && projected > 100));
        setCapacityWarning(over);
        if (over) {
          setCapacityMessage(`This assignment may over-allocate the employee. Projected allocation: ${projected ?? 'over 100'}%.`);
        } else if (available !== null || projected !== null) {
          setCapacityMessage(`Capacity looks available. Projected allocation: ${projected ?? 'within limit'}%.`);
        } else {
          setCapacityMessage('Capacity check passed.');
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setCapacityWarning(false);
          setCapacityMessage(err instanceof Error ? err.message : 'Capacity check unavailable.');
        }
      }
    }, 300);
    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [allocation?.id, allocationPercentage, employeeId, endDate, headers, open, startDate]);

  const selectedEmployee = employees.find((employee) => employee.id === employeeId);

  if (!open || !project) return null;

  const submit = async () => {
    if (!employeeId || !managerId || !startDate || !allocationRole.trim()) {
      setError('Employee, manager, role, and start date are required.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/allocations/${allocation ? allocation.id : ''}`, {
        method: allocation ? 'PATCH' : 'POST',
        headers,
        body: JSON.stringify({
          employee_id: employeeId,
          manager_id: managerId,
          project_id: project.id,
          project_name: project.name,
          allocation_percentage: allocationPercentage,
          allocation_role: allocationRole.trim(),
          billing_type: billingType,
          status,
          start_date: startDate,
          end_date: endDate || null,
          notes: notes.trim() || null,
        }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || (allocation ? 'Could not update assignment.' : 'Could not assign employee.'));
      onAssigned();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not assign employee.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-[#111827]/45 px-4 py-8 backdrop-blur-sm">
      <Card className="w-full max-w-3xl overflow-hidden shadow-[0_24px_80px_rgba(15,23,42,0.28)]">
        <div className="flex items-start justify-between border-b border-[#E5E7EB] px-6 py-5">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-light text-accent">
                <UserPlus size={18} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-[#2F3437]">{allocation ? 'Edit Assignment' : 'Assign Employee'}</h2>
                <p className="text-sm text-gray-500">{project.name} · {project.code}</p>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-hover-bg hover:text-[#2F3437]">
            <X size={18} />
          </button>
        </div>

        <div className="max-h-[72vh] overflow-y-auto px-6 py-5">
          {error && (
            <div className="mb-4 rounded-lg border border-status-error/20 bg-status-error/10 px-4 py-3 text-sm font-medium text-status-error">
              {error}
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Employee</span>
              <select value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} disabled={Boolean(allocation)} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent disabled:cursor-not-allowed disabled:opacity-70">
                <option value="">Select employee</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>{employeeName(employee)} · {employee.department}</option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Manager</span>
              <select value={managerId} onChange={(event) => setManagerId(event.target.value)} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent">
                <option value="">Select manager</option>
                {managers.map((employee) => (
                  <option key={employee.id} value={employee.id}>{employeeName(employee)}</option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Allocation Role</span>
              <input value={allocationRole} onChange={(event) => setAllocationRole(event.target.value)} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent" />
            </label>

            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Allocation %</span>
              <input type="number" min={1} max={100} value={allocationPercentage} onChange={(event) => setAllocationPercentage(Number(event.target.value))} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent" />
            </label>

            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Billing Type</span>
              <select value={billingType} onChange={(event) => setBillingType(event.target.value)} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent">
                <option value="billable">Billable</option>
                <option value="non_billable">Non-billable</option>
                <option value="internal">Internal</option>
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Status</span>
              <select value={status} onChange={(event) => setStatus(event.target.value)} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent">
                <option value="active">Active</option>
                <option value="upcoming">Upcoming</option>
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Start Date</span>
              <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent" />
            </label>

            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wide text-gray-500">End Date</span>
              <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent" />
            </label>
          </div>

          <label className="mt-4 block space-y-1.5">
            <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Notes</span>
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={240} className="min-h-[82px] w-full rounded-lg border border-[#E5E7EB] bg-warm-card px-3 py-3 text-sm font-medium text-[#2F3437] outline-none focus:border-accent" placeholder="Optional assignment context" />
          </label>

          {selectedEmployee && (
            <div className={cn('mt-4 flex items-center gap-3 rounded-xl border border-[#E5E7EB] bg-warm-bg px-4 py-3')}>
              <Avatar initials={initials(employeeName(selectedEmployee))} src={selectedEmployee.profile_image_url} />
              <div className="min-w-0">
                <div className="truncate text-sm font-bold text-[#2F3437]">{employeeName(selectedEmployee)}</div>
                <div className="truncate text-xs text-gray-500">{selectedEmployee.designation || selectedEmployee.role} · {selectedEmployee.work_email}</div>
              </div>
              <div className="ml-auto">
                <Badge variant="olive">{allocationPercentage}%</Badge>
              </div>
            </div>
          )}

          {capacityMessage && (
            <div className={cn(
              'mt-4 rounded-lg border px-4 py-3 text-sm font-medium',
              capacityWarning
                ? 'border-status-warning/25 bg-status-warning/10 text-status-warning'
                : 'border-status-success/20 bg-status-success/10 text-status-success',
            )}>
              {capacityMessage}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-[#E5E7EB] px-6 py-4">
          <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button onClick={submit} disabled={loading}>{loading ? 'Saving...' : allocation ? 'Save Assignment' : 'Assign Employee'}</Button>
        </div>
      </Card>
    </div>
  );
}

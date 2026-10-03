import { authenticatedFetch } from '@/services/apiClient';
import { useState } from 'react';
import { AlertCircle, CalendarDays, ChevronDown, Search } from 'lucide-react';
import { Drawer } from '@/components/ui/Drawer';
import { useToast } from '@/components/ui/Toast';
import { COUNTRY_CODES } from '@/data/countryCodes';
import { cn } from '@/utils/cn';
import { assignableRoles, ROLE_LABELS, type PermissionSubject, type UserRole } from '@/auth/rbac';
import { apiErrorMessage } from '@/utils/apiError';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface AddEmployeeDrawerProps {
  open: boolean;
  onClose: () => void;
  currentUser?: PermissionSubject | null;
}

// ─── Dropdown Options ───
const EMPLOYMENT_TYPES = ['full_time', 'part_time', 'contractor', 'intern', 'trainee', 'consultant'];
const EMPLOYMENT_TYPE_LABELS: Record<string, string> = {
  full_time: 'Full Time',
  part_time: 'Part Time',
  contractor: 'Contractor',
  intern: 'Intern',
  trainee: 'Trainee',
  consultant: 'Consultant',
};
const DEPARTMENTS = ['Engineering', 'Product', 'Design', 'Marketing', 'Sales', 'Operations', 'People', 'Finance'];
const WORK_ARRANGEMENTS = ['Remote', 'Hybrid', 'Office'];
const MANAGERS = ['David Park', 'Sarah Chen', 'James Rivera', 'Priya Sharma', 'Marcus Chen'];

// ─── Reusable Form Components ───

function FormLabel({ children, required }: { children: string; required?: boolean }) {
  return (
    <label className="block text-[13px] font-semibold text-[var(--color-brand-navy)] mb-1.5">
      {children}
      {required && <span className="text-status-error ml-0.5">*</span>}
    </label>
  );
}

function FormInput({
  value,
  onChange,
  placeholder,
  error,
  type = 'text',
  icon,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  error?: string;
  type?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div>
      <div className="relative">
        {icon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
            {icon}
          </div>
        )}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={cn(
            'w-full py-2.5 rounded-xl text-[14px] font-medium',
            'bg-warm-bg border',
            'text-[var(--color-brand-navy)] placeholder:text-gray-400',
            'outline-none transition-all duration-150 font-sans',
            'focus:border-accent/40 focus:ring-2 focus:ring-accent-light',
            icon ? 'pl-10 pr-4' : 'px-4',
            error ? 'border-status-error/40' : 'border-[var(--color-border)]'
          )}
        />
      </div>
      {error && (
        <div className="flex items-center gap-1.5 mt-1.5">
          <AlertCircle size={12} className="text-status-error shrink-0" />
          <span className="text-[12px] text-status-error font-medium">{error}</span>
        </div>
      )}
    </div>
  );
}

function FormSelect({
  value,
  onChange,
  placeholder,
  options,
  getLabel = (option) => option,
  searchable,
  placement = 'down',
  error,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  options: string[];
  getLabel?: (option: string) => string;
  searchable?: boolean;
  placement?: 'down' | 'up';
  error?: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');

  const filtered = searchable && search
    ? options.filter((o) => o.toLowerCase().includes(search.toLowerCase()))
    : options;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center justify-between py-2.5 px-4 rounded-xl text-[14px] font-medium',
          'bg-warm-bg border',
          error ? 'border-status-error/40' : 'border-[var(--color-border)]',
          'outline-none transition-all duration-150',
          'hover:border-accent/30',
          value ? 'text-[var(--color-brand-navy)]' : 'text-gray-400'
        )}
        aria-invalid={Boolean(error)}
      >
        <span className="truncate">{value ? getLabel(value) : placeholder}</span>
        <ChevronDown size={14} className={cn('shrink-0 text-gray-400 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div
            className={cn(
              'absolute left-0 right-0 z-20 flex max-h-[220px] flex-col overflow-hidden rounded-xl border border-[var(--color-border)] bg-warm-card shadow-card-md',
              placement === 'up' ? 'bottom-full mb-1' : 'top-full mt-1'
            )}
          >
            {searchable && (
              <div className="px-3 pt-2.5 pb-1.5 border-b border-[var(--color-border)]">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-warm-bg border border-[var(--color-border)]">
                  <Search size={13} className="text-gray-400" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search..."
                    className="bg-transparent border-none outline-none text-[13px] text-[var(--color-brand-navy)] w-full font-sans"
                    autoFocus
                  />
                </div>
              </div>
            )}
            <div className="overflow-y-auto py-1">
              {filtered.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => { onChange(opt); setIsOpen(false); setSearch(''); }}
                  className={cn(
                    'w-full text-left px-4 py-2 text-[13px] font-medium transition-colors',
                    opt === value
                      ? 'bg-hover-bg text-accent'
                      : 'text-[var(--color-brand-navy)] hover:bg-hover-bg'
                  )}
                >
                  {getLabel(opt)}
                </button>
              ))}
              {filtered.length === 0 && (
                <div className="px-4 py-3 text-[13px] text-gray-400 text-center">No results</div>
              )}
            </div>
          </div>
        </>
      )}
      {error && <div className="mt-1.5 flex items-center gap-1.5 text-[12px] font-medium text-status-error"><AlertCircle size={12} />{error}</div>}
    </div>
  );
}

function PhoneInput({
  countryCode,
  onCountryChange,
  phone,
  onPhoneChange,
  error,
}: {
  countryCode: string;
  onCountryChange: (v: string) => void;
  phone: string;
  onPhoneChange: (v: string) => void;
  error?: string;
}) {
  const [showCodes, setShowCodes] = useState(false);
  const [codeSearch, setCodeSearch] = useState('');
  const selected = COUNTRY_CODES.find((c) => c.code === countryCode) || COUNTRY_CODES[0];
  const filteredCodes = codeSearch
    ? COUNTRY_CODES.filter((country) => {
        const term = codeSearch.toLowerCase();
        return country.name.toLowerCase().includes(term) || country.iso.toLowerCase().includes(term) || country.code.includes(codeSearch);
      })
    : COUNTRY_CODES;

  return (
    <div className="relative flex min-w-0 gap-2">
      <div className="relative shrink-0">
        <button
          type="button"
          onClick={() => setShowCodes(!showCodes)}
          className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl bg-warm-bg border border-[var(--color-border)] text-[13px] font-medium text-[var(--color-brand-navy)] hover:border-accent/30 transition-colors"
        >
          <span className="text-[11px] font-bold">{selected.iso}</span>
          <span>{selected.code}</span>
          <ChevronDown size={12} className="text-gray-400" />
        </button>
        {showCodes && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowCodes(false)} />
            <div className="absolute top-full left-0 mt-1 z-20 flex max-h-[300px] w-[280px] flex-col overflow-hidden rounded-xl border border-[var(--color-border)] bg-warm-card shadow-card-md">
              <div className="border-b border-[var(--color-border)] p-2">
                <div className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-warm-bg px-2.5 py-1.5">
                  <Search size={13} className="text-gray-400" />
                  <input
                    value={codeSearch}
                    onChange={(event) => setCodeSearch(event.target.value)}
                    placeholder="Search country or code..."
                    className="w-full bg-transparent text-[13px] text-[var(--color-brand-navy)] outline-none placeholder:text-gray-400"
                    autoFocus
                  />
                </div>
              </div>
              <div className="overflow-y-auto py-1">
                {filteredCodes.map((c) => (
                  <button
                    key={`${c.iso}-${c.code}`}
                    type="button"
                    onClick={() => { onCountryChange(c.code); setShowCodes(false); setCodeSearch(''); }}
                    className={cn(
                      'flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] font-medium transition-colors',
                      c.code === countryCode ? 'bg-hover-bg text-accent' : 'text-[var(--color-brand-navy)] hover:bg-hover-bg'
                    )}
                  >
                    <span className="w-7 text-[11px] font-bold text-gray-400">{c.iso}</span>
                    <span className="w-12">{c.code}</span>
                    <span className="min-w-0 flex-1 truncate text-gray-500">{c.name}</span>
                  </button>
                ))}
                {filteredCodes.length === 0 && (
                  <div className="px-3 py-4 text-center text-[13px] text-gray-400">No country codes found</div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
      <input
        type="tel"
        value={phone}
        onChange={(e) => onPhoneChange(e.target.value)}
        placeholder="Enter phone number"
        aria-invalid={Boolean(error)}
        className={cn('min-w-0 flex-1 py-2.5 px-4 rounded-xl text-[14px] font-medium bg-warm-bg border text-[var(--color-brand-navy)] placeholder:text-gray-400 outline-none transition-all focus:border-accent/40 focus:ring-2 focus:ring-accent-light font-sans', error ? 'border-status-error/40' : 'border-[var(--color-border)]')}
      />
    </div>
  );
}

function SectionTitle({ children }: { children: string }) {
  return (
    <div className="text-[11px] font-bold text-gray-400 tracking-widest uppercase mb-4 mt-2">
      {children}
    </div>
  );
}

// ─── Main Component ───

export interface FormState {
  firstName: string;
  lastName: string;
  workEmail: string;
  countryCode: string;
  phone: string;
  workforceType: string;
  role: string;
  department: string;
  designation: string;
  reportingManager: string;
  joiningDate: string;
  workLocation: string;
  workCity: string;
  workState: string;
  workCountry: string;
  dateOfBirth: string;
}

export const INITIAL_FORM: FormState = {
  firstName: '',
  lastName: '',
  workEmail: '',
  countryCode: '+91',
  phone: '',
  workforceType: '',
  role: '',
  department: '',
  designation: '',
  reportingManager: '',
  joiningDate: '',
  workLocation: '',
  workCity: '',
  workState: '',
  workCountry: '',
  dateOfBirth: '',
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateAddEmployeeForm(form: FormState, today = new Date()): Partial<Record<keyof FormState, string>> {
  const newErrors: Partial<Record<keyof FormState, string>> = {};
  const todayInput = today.toISOString().slice(0, 10);
  const phoneDigits = form.phone.replace(/\D/g, '');

  if (!form.firstName.trim()) newErrors.firstName = 'First name is required';
  else if (form.firstName.trim().length > 100) newErrors.firstName = 'First name must be 100 characters or fewer';
  if (!form.lastName.trim()) newErrors.lastName = 'Last name is required';
  else if (form.lastName.trim().length > 100) newErrors.lastName = 'Last name must be 100 characters or fewer';
  if (!form.workEmail.trim()) newErrors.workEmail = 'Work email is required';
  else if (!EMAIL_PATTERN.test(form.workEmail.trim())) newErrors.workEmail = 'Enter a valid work email address.';
  if (!form.phone.trim()) newErrors.phone = 'Phone number is required';
  else if (phoneDigits.length < 7 || phoneDigits.length > 15 || form.phone.trim().length > 20) newErrors.phone = 'Enter a valid phone number with 7 to 15 digits';
  if (!form.dateOfBirth) newErrors.dateOfBirth = 'Date of birth is required for setup code';
  else if (form.dateOfBirth > todayInput) newErrors.dateOfBirth = 'Date of birth cannot be in the future';
  if (!form.workforceType) newErrors.workforceType = 'Employment type is required';
  if (!form.role) newErrors.role = 'Role is required';
  if (!form.department) newErrors.department = 'Department is required';
  if (!form.reportingManager) newErrors.reportingManager = 'Reporting manager is required';
  if (!form.joiningDate) newErrors.joiningDate = 'Joining date is required';
  if (!form.workLocation) newErrors.workLocation = 'Work arrangement is required';
  if (!form.workCity.trim()) newErrors.workCity = 'Work city is required';
  else if (form.workCity.trim().length > 120) newErrors.workCity = 'Work city must be 120 characters or fewer';
  if (form.workState.trim().length > 120) newErrors.workState = 'State / province must be 120 characters or fewer';
  if (!form.workCountry.trim()) newErrors.workCountry = 'Work country is required';
  else if (form.workCountry.trim().length > 120) newErrors.workCountry = 'Work country must be 120 characters or fewer';
  return newErrors;
}

export function AddEmployeeDrawer({ open, onClose, currentUser }: AddEmployeeDrawerProps) {
  const { showToast } = useToast();
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const roleOptions = assignableRoles(currentUser);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    // Clear error on change
    if (errors[key]) {
      setErrors((prev) => ({ ...prev, [key]: undefined }));
    }
  };

  const validate = (): boolean => {
    const newErrors = validateAddEmployeeForm(form);
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);

    // Build API payload
    const payload = {
      first_name: form.firstName.trim(),
      last_name: form.lastName.trim(),
      work_email: form.workEmail.trim().toLowerCase(),
      country_code: form.countryCode,
      phone: form.phone.trim(),
      date_of_birth: form.dateOfBirth || null,
      workforce_type: form.workforceType,
      employment_type: form.workforceType,
      role: form.role,
      department: form.department,
      designation: form.designation || null,
      reporting_manager: form.reportingManager,
      joining_date: form.joiningDate,
      work_location: form.workLocation,
      work_city: form.workCity.trim(),
      work_state: form.workState.trim() || null,
      work_country: form.workCountry.trim(),
    };

    try {
      const response = await authenticatedFetch(`${API_BASE}/employees/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(apiErrorMessage(error, `API error: ${response.status}`));
      }

      const result = await response.json();
      if (!result.success) throw new Error(result.message || 'Unable to add employee.');

      setForm(INITIAL_FORM);
      setErrors({});
      onClose();

      showToast({
        message: `${result.message || 'Employee added successfully'}. Activation instructions will be sent by email.`,
        action: {
          label: 'View employee',
          onClick: () => console.log('Navigate to employee:', result.employee_id),
        },
        duration: 6000,
      });

    } catch (error) {
      showToast({
        message: error instanceof Error ? error.message : 'Unable to add employee. Please confirm the backend is running.',
        duration: 6000,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    setForm(INITIAL_FORM);
    setErrors({});
    onClose();
  };

  return (
    <Drawer
      open={open}
      onClose={handleCancel}
      title="Add Employee"
      subtitle="Register a new employee in Reknew Orbit."
      width="w-[680px]"
      footer={
        <div className="flex items-center justify-end gap-3">
          <button
            onClick={handleCancel}
            className="px-5 py-2.5 rounded-xl text-[13px] font-semibold text-gray-500 border border-[var(--color-border)] hover:bg-hover-bg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className={cn(
              'px-6 py-2.5 rounded-xl text-[13px] font-semibold text-white transition-all shadow-sm',
              submitting
                ? 'bg-accent/60 cursor-not-allowed'
                : 'bg-accent hover:bg-accent-dark active:scale-[0.98]'
            )}
          >
            {submitting ? 'Adding...' : 'Add Employee'}
          </button>
        </div>
      }
    >
      {/* ─── Section 1: Basic Information ─── */}
      <SectionTitle>Basic Information</SectionTitle>

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <div>
          <FormLabel required>First Name</FormLabel>
          <FormInput
            value={form.firstName}
            onChange={(v) => update('firstName', v)}
            placeholder="Enter first name"
            error={errors.firstName}
          />
        </div>
        <div>
          <FormLabel required>Last Name</FormLabel>
          <FormInput
            value={form.lastName}
            onChange={(v) => update('lastName', v)}
            placeholder="Enter last name"
            error={errors.lastName}
          />
        </div>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <div>
          <FormLabel required>Work Email</FormLabel>
          <FormInput
            value={form.workEmail}
            onChange={(v) => update('workEmail', v)}
            placeholder="john.doe@company.com"
            type="email"
            error={errors.workEmail}
          />
        </div>
        <div>
          <FormLabel required>Phone Number</FormLabel>
          <PhoneInput
            countryCode={form.countryCode}
            onCountryChange={(v) => update('countryCode', v)}
            phone={form.phone}
            onPhoneChange={(v) => update('phone', v)}
            error={errors.phone}
          />
          {errors.phone && (
            <div className="flex items-center gap-1.5 mt-1.5">
              <AlertCircle size={12} className="text-status-error shrink-0" />
              <span className="text-[12px] text-status-error font-medium">{errors.phone}</span>
            </div>
          )}
        </div>
      </div>

      <div className="mb-4">
        <FormLabel required>Date of Birth</FormLabel>
        <div className="relative w-full sm:w-1/2">
          <input
            type="date"
            max={new Date().toISOString().slice(0, 10)}
            value={form.dateOfBirth}
            onChange={(e) => update('dateOfBirth', e.target.value)}
            aria-invalid={Boolean(errors.dateOfBirth)}
            className={cn(
              'w-full py-2.5 px-4 rounded-xl text-[14px] font-medium',
              'bg-warm-bg border',
              errors.dateOfBirth ? 'border-status-error/40' : 'border-[var(--color-border)]',
              'text-[var(--color-brand-navy)] outline-none transition-all duration-150',
              'focus:border-accent/40 focus:ring-2 focus:ring-accent-light font-sans',
              !form.dateOfBirth && 'text-gray-400'
            )}
          />
        </div>
        <p className="text-[11px] text-gray-400 mt-1.5">Used to generate the employee's setup code</p>
        {errors.dateOfBirth && (
          <div className="flex items-center gap-1.5 mt-1">
            <AlertCircle size={12} className="text-status-error shrink-0" />
            <span className="text-[12px] text-status-error font-medium">{errors.dateOfBirth}</span>
          </div>
        )}
      </div>

      {/* ─── Section 2: Workforce Information ─── */}
      <div className="h-px bg-[var(--color-border)] my-6" />
      <SectionTitle>Workforce Information</SectionTitle>

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <div>
          <FormLabel required>Employment Type</FormLabel>
          <FormSelect
            value={form.workforceType}
            onChange={(v) => update('workforceType', v)}
            placeholder="Select employment type"
            options={EMPLOYMENT_TYPES}
            getLabel={(value) => EMPLOYMENT_TYPE_LABELS[value] || value}
            error={errors.workforceType}
          />
        </div>
        <div>
          <FormLabel required>Role</FormLabel>
          <FormSelect
            value={form.role}
            onChange={(v) => update('role', v)}
            placeholder="Select role"
            options={roleOptions}
            getLabel={(value) => ROLE_LABELS[value as UserRole] || value}
            error={errors.role}
          />
        </div>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <div>
          <FormLabel required>Department</FormLabel>
          <FormSelect
            value={form.department}
            onChange={(v) => update('department', v)}
            placeholder="Select department"
            options={DEPARTMENTS}
            error={errors.department}
          />
        </div>
        <div>
          <FormLabel>Designation</FormLabel>
          <FormInput
            value={form.designation}
            onChange={(v) => update('designation', v)}
            placeholder="Enter designation"
          />
        </div>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <div>
          <FormLabel required>Reporting Manager</FormLabel>
          <FormSelect
            value={form.reportingManager}
            onChange={(v) => update('reportingManager', v)}
            placeholder="Search and select manager"
            options={MANAGERS}
            searchable
            error={errors.reportingManager}
          />
        </div>
        <div>
          <FormLabel required>Joining Date</FormLabel>
          <div className="relative">
            <input
              type="date"
              value={form.joiningDate}
              onChange={(e) => update('joiningDate', e.target.value)}
              aria-invalid={Boolean(errors.joiningDate)}
              className={cn(
                'w-full py-2.5 px-4 rounded-xl text-[14px] font-medium',
                'bg-warm-bg border',
                errors.joiningDate ? 'border-status-error/40' : 'border-[var(--color-border)]',
                'text-[var(--color-brand-navy)] outline-none transition-all duration-150',
                'focus:border-accent/40 focus:ring-2 focus:ring-accent-light font-sans',
                !form.joiningDate && 'text-gray-400'
              )}
            />
          </div>
          {errors.joiningDate && (
            <div className="flex items-center gap-1.5 mt-1.5">
              <AlertCircle size={12} className="text-status-error shrink-0" />
              <span className="text-[12px] text-status-error font-medium">{errors.joiningDate}</span>
            </div>
          )}
        </div>
      </div>

      <div className="mb-4">
        <FormLabel required>Work Arrangement</FormLabel>
        <FormSelect
          value={form.workLocation}
          onChange={(v) => update('workLocation', v)}
          placeholder="Select work arrangement"
          options={WORK_ARRANGEMENTS}
          placement="up"
          error={errors.workLocation}
        />
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <div>
          <FormLabel required>Work City</FormLabel>
          <FormInput value={form.workCity} onChange={(v) => update('workCity', v)} placeholder="e.g. Hartford" error={errors.workCity} />
        </div>
        <div>
          <FormLabel>State / Province</FormLabel>
          <FormInput value={form.workState} onChange={(v) => update('workState', v)} placeholder="e.g. CT" error={errors.workState} />
        </div>
      </div>

      <div className="mb-4">
        <FormLabel required>Work Country</FormLabel>
        <FormInput value={form.workCountry} onChange={(v) => update('workCountry', v)} placeholder="e.g. United States" error={errors.workCountry} />
      </div>
    </Drawer>
  );
}

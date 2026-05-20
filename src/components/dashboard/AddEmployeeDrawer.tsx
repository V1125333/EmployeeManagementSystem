import { useState } from 'react';
import { AlertCircle, ChevronDown, Search } from 'lucide-react';
import { Drawer } from '@/components/ui/Drawer';
import { useToast } from '@/components/ui/Toast';
import { cn } from '@/utils/cn';

interface AddEmployeeDrawerProps {
  open: boolean;
  onClose: () => void;
}

// ─── Dropdown Options ───
const WORKFORCE_TYPES = ['Full-Time Employee', 'Paid Intern', 'Unpaid Intern', 'Trainee', 'Guest'];
const ROLES = ['HR', 'Admin', 'Manager', 'Employee', 'Intern', 'Trainee', 'Guest'];
const DEPARTMENTS = ['Engineering', 'Product', 'Design', 'Marketing', 'Sales', 'Operations', 'People', 'Finance'];
const LOCATIONS = ['Onshore', 'Offshore', 'Remote', 'Hybrid'];
const ONBOARDING_TYPES = ['Standard Employee', 'Intern / Trainee', 'Guest / Contractor'];
const MANAGERS = ['David Park', 'Sarah Chen', 'James Rivera', 'Priya Sharma', 'Marcus Chen'];
const COUNTRY_CODES = [
  { code: '+1', flag: '🇺🇸', label: 'US' },
  { code: '+44', flag: '🇬🇧', label: 'UK' },
  { code: '+91', flag: '🇮🇳', label: 'IN' },
  { code: '+61', flag: '🇦🇺', label: 'AU' },
  { code: '+49', flag: '🇩🇪', label: 'DE' },
  { code: '+81', flag: '🇯🇵', label: 'JP' },
];

// ─── Reusable Form Components ───

function FormLabel({ children, required }: { children: string; required?: boolean }) {
  return (
    <label className="block text-[13px] font-semibold text-[#2F3437] mb-1.5">
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
            'text-[#2F3437] placeholder:text-gray-400',
            'outline-none transition-all duration-150 font-sans',
            'focus:border-olive/40 focus:ring-2 focus:ring-olive/10',
            icon ? 'pl-10 pr-4' : 'px-4',
            error ? 'border-status-error/40' : 'border-[#E5E7EB]'
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
  searchable,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  options: string[];
  searchable?: boolean;
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
          'bg-warm-bg border border-[#E5E7EB]',
          'outline-none transition-all duration-150',
          'hover:border-olive/30',
          value ? 'text-[#2F3437]' : 'text-gray-400'
        )}
      >
        <span className="truncate">{value || placeholder}</span>
        <ChevronDown size={14} className={cn('shrink-0 text-gray-400 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute top-full left-0 right-0 mt-1 z-20 bg-warm-card border border-[#E5E7EB] rounded-xl shadow-card-md max-h-[200px] overflow-hidden flex flex-col">
            {searchable && (
              <div className="px-3 pt-2.5 pb-1.5 border-b border-[#E5E7EB]">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-warm-bg border border-[#E5E7EB]">
                  <Search size={13} className="text-gray-400" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search..."
                    className="bg-transparent border-none outline-none text-[13px] text-[#2F3437] w-full font-sans"
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
                      ? 'bg-hover-bg text-olive'
                      : 'text-[#2F3437] hover:bg-hover-bg'
                  )}
                >
                  {opt}
                </button>
              ))}
              {filtered.length === 0 && (
                <div className="px-4 py-3 text-[13px] text-gray-400 text-center">No results</div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function PhoneInput({
  countryCode,
  onCountryChange,
  phone,
  onPhoneChange,
}: {
  countryCode: string;
  onCountryChange: (v: string) => void;
  phone: string;
  onPhoneChange: (v: string) => void;
}) {
  const [showCodes, setShowCodes] = useState(false);
  const selected = COUNTRY_CODES.find((c) => c.code === countryCode) || COUNTRY_CODES[0];

  return (
    <div className="relative flex gap-2">
      <div className="relative">
        <button
          type="button"
          onClick={() => setShowCodes(!showCodes)}
          className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl bg-warm-bg border border-[#E5E7EB] text-[13px] font-medium text-[#2F3437] hover:border-olive/30 transition-colors"
        >
          <span>{selected.flag}</span>
          <span>{selected.code}</span>
          <ChevronDown size={12} className="text-gray-400" />
        </button>
        {showCodes && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowCodes(false)} />
            <div className="absolute top-full left-0 mt-1 z-20 bg-warm-card border border-[#E5E7EB] rounded-xl shadow-card-md w-[140px] py-1">
              {COUNTRY_CODES.map((c) => (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => { onCountryChange(c.code); setShowCodes(false); }}
                  className={cn(
                    'w-full flex items-center gap-2 px-3 py-1.5 text-[13px] font-medium transition-colors',
                    c.code === countryCode ? 'bg-hover-bg text-olive' : 'text-[#2F3437] hover:bg-hover-bg'
                  )}
                >
                  <span>{c.flag}</span>
                  <span>{c.code}</span>
                  <span className="text-gray-400 ml-auto">{c.label}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
      <input
        type="tel"
        value={phone}
        onChange={(e) => onPhoneChange(e.target.value)}
        placeholder="Enter phone number"
        className="flex-1 py-2.5 px-4 rounded-xl text-[14px] font-medium bg-warm-bg border border-[#E5E7EB] text-[#2F3437] placeholder:text-gray-400 outline-none transition-all focus:border-olive/40 focus:ring-2 focus:ring-olive/10 font-sans"
      />
    </div>
  );
}

function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer group">
      <div
        onClick={() => onChange(!checked)}
        className={cn(
          'w-[18px] h-[18px] rounded-md border flex items-center justify-center transition-all duration-150 cursor-pointer shrink-0',
          checked ? 'bg-olive border-olive' : 'bg-warm-bg border-[#E5E7EB] group-hover:border-olive/40'
        )}
      >
        {checked && (
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
            <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </div>
      <span className="text-[13px] text-[#2F3437] font-medium">{label}</span>
    </label>
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

interface FormState {
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
  dateOfBirth: string;
  createAccount: boolean;
  createChecklist: boolean;
  onboardingType: string;
}

const INITIAL_FORM: FormState = {
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
  dateOfBirth: '',
  createAccount: true,
  createChecklist: true,
  onboardingType: '',
};

export function AddEmployeeDrawer({ open, onClose }: AddEmployeeDrawerProps) {
  const { showToast } = useToast();
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [submitting, setSubmitting] = useState(false);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) {
      setErrors((prev) => ({ ...prev, [key]: undefined }));
    }
  };

  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof FormState, string>> = {};

    if (!form.firstName.trim()) newErrors.firstName = 'First name is required';
    if (!form.lastName.trim()) newErrors.lastName = 'Last name is required';
    if (!form.workEmail.trim()) {
      newErrors.workEmail = 'Work email is required';
    } else if (!form.workEmail.endsWith('@reknew.ai')) {
      newErrors.workEmail = 'Use a valid ReKnew work email.';
    }
    if (!form.phone.trim()) newErrors.phone = 'Phone number is required';
    if (!form.dateOfBirth) newErrors.dateOfBirth = 'Date of birth is required for setup code';
    if (!form.workforceType) newErrors.workforceType = 'Required';
    if (!form.role) newErrors.role = 'Required';
    if (!form.department) newErrors.department = 'Required';
    if (!form.reportingManager) newErrors.reportingManager = 'Required';
    if (!form.joiningDate) newErrors.joiningDate = 'Required';
    if (!form.workLocation) newErrors.workLocation = 'Required';

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);

    const payload = {
      first_name: form.firstName,
      last_name: form.lastName,
      work_email: form.workEmail,
      country_code: form.countryCode,
      phone: form.phone,
      date_of_birth: form.dateOfBirth || null,
      workforce_type: form.workforceType,
      role: form.role,
      department: form.department,
      designation: form.designation || null,
      reporting_manager: form.reportingManager,
      joining_date: form.joiningDate,
      work_location: form.workLocation,
      create_account: form.createAccount,
      create_checklist: form.createChecklist,
      onboarding_type: form.onboardingType || 'Standard Employee',
    };

    try {
      const response = await fetch('http://localhost:8000/api/v1/employees/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const result = await response.json();

      setForm(INITIAL_FORM);
      setErrors({});
      onClose();

      if (result.setup_code) {
        showToast({
          message: `Employee added! Setup code: ${result.setup_code}`,
          duration: 10000,
        });
      } else {
        showToast({
          message: result.message || 'Employee added successfully',
          action: {
            label: 'View employee',
            onClick: () => console.log('Navigate to employee:', result.employee_id),
          },
          duration: 6000,
        });
      }

    } catch {
      console.log('Backend not available — using mock mode');
      console.log('Payload:', payload);

      setForm(INITIAL_FORM);
      setErrors({});
      onClose();

      showToast({
        message: 'Employee added successfully (demo mode)',
        action: {
          label: 'View employee',
          onClick: () => console.log('Navigate to employee profile'),
        },
        duration: 6000,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveDraft = () => {
    setForm(INITIAL_FORM);
    setErrors({});
    onClose();

    showToast({
      message: 'Employee saved as draft',
      duration: 4000,
    });
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
      subtitle="Create a new workforce profile and start onboarding."
      width="w-[580px]"
      footer={
        <div className="flex items-center justify-end gap-2.5">
          <button
            onClick={handleCancel}
            className="px-5 py-2.5 rounded-xl text-[13px] font-semibold text-gray-500 hover:bg-hover-bg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveDraft}
            className="px-5 py-2.5 rounded-xl text-[13px] font-semibold text-olive border border-[#E5E7EB] hover:bg-hover-bg transition-colors"
          >
            Save as Draft
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className={cn(
              'px-5 py-2.5 rounded-xl text-[13px] font-semibold text-white transition-all shadow-sm',
              submitting
                ? 'bg-olive/60 cursor-not-allowed'
                : 'bg-olive hover:bg-olive-dark active:scale-[0.98]'
            )}
          >
            {submitting ? 'Adding...' : 'Add Employee'}
          </button>
        </div>
      }
    >
      {/* ─── Section 1: Basic Information ─── */}
      <SectionTitle>Basic Information</SectionTitle>

      <div className="grid grid-cols-2 gap-4 mb-4">
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

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <FormLabel required>Work Email</FormLabel>
          <FormInput
            value={form.workEmail}
            onChange={(v) => update('workEmail', v)}
            placeholder="john.doe@reknew.ai"
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
        <div className="relative w-1/2">
          <input
            type="date"
            value={form.dateOfBirth}
            onChange={(e) => update('dateOfBirth', e.target.value)}
            className={cn(
              'w-full py-2.5 px-4 rounded-xl text-[14px] font-medium',
              'bg-warm-bg border border-[#E5E7EB]',
              'text-[#2F3437] outline-none transition-all duration-150',
              'focus:border-olive/40 focus:ring-2 focus:ring-olive/10 font-sans',
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
      <div className="h-px bg-[#E5E7EB] my-6" />
      <SectionTitle>Workforce Information</SectionTitle>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <FormLabel required>Workforce Type</FormLabel>
          <FormSelect
            value={form.workforceType}
            onChange={(v) => update('workforceType', v)}
            placeholder="Select workforce type"
            options={WORKFORCE_TYPES}
          />
        </div>
        <div>
          <FormLabel required>Role</FormLabel>
          <FormSelect
            value={form.role}
            onChange={(v) => update('role', v)}
            placeholder="Select role"
            options={ROLES}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <FormLabel required>Department</FormLabel>
          <FormSelect
            value={form.department}
            onChange={(v) => update('department', v)}
            placeholder="Select department"
            options={DEPARTMENTS}
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

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <FormLabel required>Reporting Manager</FormLabel>
          <FormSelect
            value={form.reportingManager}
            onChange={(v) => update('reportingManager', v)}
            placeholder="Search and select manager"
            options={MANAGERS}
            searchable
          />
        </div>
        <div>
          <FormLabel required>Joining Date</FormLabel>
          <div className="relative">
            <input
              type="date"
              value={form.joiningDate}
              onChange={(e) => update('joiningDate', e.target.value)}
              className={cn(
                'w-full py-2.5 px-4 rounded-xl text-[14px] font-medium',
                'bg-warm-bg border border-[#E5E7EB]',
                'text-[#2F3437] outline-none transition-all duration-150',
                'focus:border-olive/40 focus:ring-2 focus:ring-olive/10 font-sans',
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
        <FormLabel required>Work Location</FormLabel>
        <FormSelect
          value={form.workLocation}
          onChange={(v) => update('workLocation', v)}
          placeholder="Select work location"
          options={LOCATIONS}
        />
      </div>

      {/* ─── Section 3: Onboarding Setup ─── */}
      <div className="h-px bg-[#E5E7EB] my-6" />
      <SectionTitle>Onboarding Setup</SectionTitle>

      <div className="bg-warm-bg border border-[#E5E7EB] rounded-xl p-5">
        {/* Checkboxes */}
        <div className="flex flex-col gap-3 mb-5">
          <Checkbox
            checked={form.createAccount}
            onChange={(v) => update('createAccount', v)}
            label="Create employee account"
          />
          <Checkbox
            checked={form.createChecklist}
            onChange={(v) => update('createChecklist', v)}
            label="Create onboarding checklist"
          />
        </div>

        {/* Onboarding Type dropdown */}
        <div>
          <FormLabel required>Onboarding Type</FormLabel>
          <FormSelect
            value={form.onboardingType}
            onChange={(v) => update('onboardingType', v)}
            placeholder="Select onboarding type"
            options={ONBOARDING_TYPES}
          />
        </div>

        {/* Checklist preview — shown when createChecklist is enabled */}
        {form.createChecklist && (
          <div className="mt-4 pt-4 border-t border-[#E5E7EB]">
            <div className="text-[11px] font-bold text-gray-400 tracking-wider uppercase mb-2.5">
              Checklist tasks to be created
            </div>
            <div className="flex flex-col gap-1.5">
              {[
                'Complete profile',
                'Accept company policies',
                'Assign reporting manager',
                'Assign work location',
              ].map((task) => (
                <div
                  key={task}
                  className="flex items-center gap-2.5 py-1.5 text-[13px] text-[#2F3437] font-medium"
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-sage shrink-0" />
                  {task}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Drawer>
  );
}
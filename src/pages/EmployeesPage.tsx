import { useState, useEffect, useCallback } from 'react';
import {
  Search, Filter, UserPlus, Download, ChevronDown, ChevronLeft, ChevronRight,
  Mail, Phone, MapPin, Calendar, Briefcase, Building2, User, Shield, X,
} from 'lucide-react';
import { Card, CardHeader, Badge, Button, Avatar } from '@/components/ui';
import { Drawer } from '@/components/ui/Drawer';
import { AddEmployeeDrawer } from '@/components/dashboard/AddEmployeeDrawer';
import { cn } from '@/utils/cn';

const API_BASE = 'http://localhost:8000/api/v1';

// ─── Types ───
interface EmployeeRecord {
  id: string;
  first_name: string;
  last_name: string;
  work_email: string;
  phone: string;
  department: string;
  designation: string | null;
  role: string;
  workforce_type: string;
  employment_status: string;
  work_location: string;
  joining_date: string | null;
  reporting_manager: string;
  profile_image_url: string | null;
  is_active: boolean;
  is_first_login: boolean;
  setup_code: string | null;
  created_at: string;
}

interface EmployeeListResponse {
  employees: EmployeeRecord[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// ─── Filter Options ───
const DEPARTMENTS = ['All', 'Engineering', 'Product', 'Design', 'Marketing', 'Sales', 'Operations', 'People', 'Finance'];
const STATUSES = ['All', 'active', 'inactive', 'onboarding', 'offboarding'];
const ROLES = ['All', 'super_admin', 'hr_admin', 'manager', 'employee', 'trainee'];
const LOCATIONS = ['All', 'Onshore', 'Offshore', 'Remote', 'Hybrid'];

// ─── Status Badge ───
const statusVariant: Record<string, 'olive' | 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  active: 'success',
  inactive: 'neutral',
  onboarding: 'info',
  offboarding: 'warning',
};

const roleLabels: Record<string, string> = {
  super_admin: 'Super Admin',
  hr_admin: 'HR Admin',
  manager: 'Manager',
  employee: 'Employee',
  trainee: 'Trainee',
};

function FilterDropdown({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1.5 px-3 py-[7px] rounded-lg text-[13px] font-medium transition-colors border',
          value !== 'All'
            ? 'bg-olive/10 text-olive border-olive/20'
            : 'bg-warm-card text-gray-500 border-[#E5E7EB] hover:bg-hover-bg'
        )}
      >
        {label}: {value === 'All' ? 'All' : value}
        <ChevronDown size={12} className={cn('transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 z-20 bg-warm-card border border-[#E5E7EB] rounded-xl shadow-card-md py-1 min-w-[160px]">
            {options.map((opt) => (
              <button
                key={opt}
                onClick={() => { onChange(opt); setOpen(false); }}
                className={cn(
                  'w-full text-left px-4 py-2 text-[13px] font-medium transition-colors',
                  opt === value ? 'bg-hover-bg text-olive' : 'text-[#2F3437] hover:bg-hover-bg'
                )}
              >
                {opt === 'All' ? `All ${label}s` : opt}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Employee Detail Drawer ───
function EmployeeDetail({
  employee,
  open,
  onClose,
}: {
  employee: EmployeeRecord | null;
  open: boolean;
  onClose: () => void;
}) {
  if (!employee) return null;

  const initials = `${employee.first_name[0]}${employee.last_name[0]}`.toUpperCase();
  const fullName = `${employee.first_name} ${employee.last_name}`;

  const InfoRow = ({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | null }) => (
    <div className="flex items-start gap-3 py-2.5">
      <span className="text-gray-400 mt-0.5 shrink-0">{icon}</span>
      <div>
        <div className="text-[11px] text-gray-400 font-medium uppercase tracking-wider">{label}</div>
        <div className="text-[14px] text-[#2F3437] font-medium">{value || '—'}</div>
      </div>
    </div>
  );

  return (
    <Drawer open={open} onClose={onClose} title={fullName} subtitle={employee.work_email} width="w-[480px]">
      {/* Profile header */}
      <div className="flex items-center gap-4 mb-6 pb-6 border-b border-[#E5E7EB]">
        <div className="w-16 h-16 rounded-2xl bg-olive flex items-center justify-center text-white text-xl font-bold">
          {initials}
        </div>
        <div>
          <div className="text-lg font-bold text-[#2F3437]">{fullName}</div>
          <div className="text-[13px] text-gray-500">{employee.designation || employee.role}</div>
          <div className="flex gap-2 mt-2">
            <Badge variant={statusVariant[employee.employment_status] || 'neutral'}>
              {employee.employment_status}
            </Badge>
            {employee.is_first_login && (
              <Badge variant="warning">Setup pending</Badge>
            )}
            {employee.setup_code && (
              <Badge variant="olive">{employee.setup_code}</Badge>
            )}
          </div>
        </div>
      </div>

      {/* Contact */}
      <div className="text-[11px] font-bold text-gray-400 tracking-widest uppercase mb-3">Contact</div>
      <InfoRow icon={<Mail size={15} />} label="Email" value={employee.work_email} />
      <InfoRow icon={<Phone size={15} />} label="Phone" value={employee.phone} />

      <div className="h-px bg-[#E5E7EB] my-4" />

      {/* Employment */}
      <div className="text-[11px] font-bold text-gray-400 tracking-widest uppercase mb-3">Employment</div>
      <InfoRow icon={<Building2 size={15} />} label="Department" value={employee.department} />
      <InfoRow icon={<Briefcase size={15} />} label="Designation" value={employee.designation} />
      <InfoRow icon={<Shield size={15} />} label="Role" value={roleLabels[employee.role] || employee.role} />
      <InfoRow icon={<User size={15} />} label="Workforce Type" value={employee.workforce_type} />
      <InfoRow icon={<User size={15} />} label="Reporting Manager" value={employee.reporting_manager} />
      <InfoRow icon={<MapPin size={15} />} label="Work Location" value={employee.work_location} />
      <InfoRow icon={<Calendar size={15} />} label="Joining Date" value={employee.joining_date} />
    </Drawer>
  );
}

// ─── Main Page ───
export function EmployeesPage() {
  const [employees, setEmployees] = useState<EmployeeRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [roleFilter, setRoleFilter] = useState('All');
  const [locationFilter, setLocationFilter] = useState('All');
  const [selectedEmployee, setSelectedEmployee] = useState<EmployeeRecord | null>(null);
  const [showAddEmployee, setShowAddEmployee] = useState(false);

  const fetchEmployees = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('per_page', '20');
      if (search) params.set('search', search);
      if (deptFilter !== 'All') params.set('department', deptFilter);
      if (statusFilter !== 'All') params.set('status', statusFilter);
      if (roleFilter !== 'All') params.set('role', roleFilter);
      if (locationFilter !== 'All') params.set('location', locationFilter);

      const res = await fetch(`${API_BASE}/employees/?${params.toString()}`);
      const data: EmployeeListResponse = await res.json();

      setEmployees(data.employees);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch {
      console.log('Backend not available — showing empty state');
      setEmployees([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, search, deptFilter, statusFilter, roleFilter, locationFilter]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  // Debounced search
  const [searchInput, setSearchInput] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const clearFilters = () => {
    setDeptFilter('All');
    setStatusFilter('All');
    setRoleFilter('All');
    setLocationFilter('All');
    setSearchInput('');
    setSearch('');
    setPage(1);
  };

  const hasActiveFilters = deptFilter !== 'All' || statusFilter !== 'All' || roleFilter !== 'All' || locationFilter !== 'All' || search !== '';

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1">Employees</h1>
          <p className="text-sm text-gray-500">
            {total} {total === 1 ? 'employee' : 'employees'} in the organization
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" icon={<Download size={14} />}>Export CSV</Button>
          <Button icon={<UserPlus size={14} />} onClick={() => setShowAddEmployee(true)}>Add Employee</Button>
        </div>
      </div>

      {/* Search + Filters */}
      <Card className="mb-5">
        <div className="px-5 py-4">
          {/* Search bar */}
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 flex items-center gap-2 px-3.5 py-[8px] bg-warm-bg border border-[#E5E7EB] rounded-lg">
              <Search size={16} className="text-gray-400 shrink-0" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search by name or email..."
                className="bg-transparent border-none outline-none text-[13px] text-[#2F3437] placeholder:text-gray-400 w-full font-sans"
              />
              {searchInput && (
                <button onClick={() => { setSearchInput(''); setSearch(''); }} className="text-gray-400 hover:text-gray-600">
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Filter pills */}
          <div className="flex items-center gap-2 flex-wrap">
            <Filter size={14} className="text-gray-400" />
            <FilterDropdown label="Department" value={deptFilter} options={DEPARTMENTS} onChange={(v) => { setDeptFilter(v); setPage(1); }} />
            <FilterDropdown label="Status" value={statusFilter} options={STATUSES} onChange={(v) => { setStatusFilter(v); setPage(1); }} />
            <FilterDropdown label="Role" value={roleFilter} options={ROLES} onChange={(v) => { setRoleFilter(v); setPage(1); }} />
            <FilterDropdown label="Location" value={locationFilter} options={LOCATIONS} onChange={(v) => { setLocationFilter(v); setPage(1); }} />
            {hasActiveFilters && (
              <button onClick={clearFilters} className="text-[12px] text-status-error font-medium hover:underline ml-1">
                Clear all
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-sm text-gray-400">Loading employees...</div>
          </div>
        ) : employees.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="text-3xl mb-3">👥</div>
            <div className="text-[15px] font-semibold text-[#2F3437] mb-1">No employees found</div>
            <div className="text-sm text-gray-500">
              {hasActiveFilters ? 'Try adjusting your filters' : 'Add your first employee to get started'}
            </div>
          </div>
        ) : (
          <>
            {/* Table header */}
            <div className="grid grid-cols-[1fr_140px_120px_120px_100px_100px] gap-4 px-5 py-3 border-b border-[#E5E7EB] text-[11px] font-bold text-gray-400 tracking-wider uppercase">
              <div>Employee</div>
              <div>Department</div>
              <div>Role</div>
              <div>Location</div>
              <div>Status</div>
              <div>Joined</div>
            </div>

            {/* Table rows */}
            {employees.map((emp) => {
              const initials = `${emp.first_name[0]}${emp.last_name[0]}`.toUpperCase();
              return (
                <div
                  key={emp.id}
                  onClick={() => setSelectedEmployee(emp)}
                  className="grid grid-cols-[1fr_140px_120px_120px_100px_100px] gap-4 px-5 py-3 border-b border-[#E5E7EB] hover:bg-hover-bg cursor-pointer transition-colors items-center"
                >
                  {/* Name + email */}
                  <div className="flex items-center gap-3 min-w-0">
                    <Avatar initials={initials} size="md" variant={emp.is_active ? 'filled' : 'soft'} />
                    <div className="min-w-0">
                      <div className="text-[13.5px] font-semibold text-[#2F3437] truncate">
                        {emp.first_name} {emp.last_name}
                      </div>
                      <div className="text-[12px] text-gray-400 truncate">{emp.work_email}</div>
                    </div>
                  </div>

                  {/* Department */}
                  <div className="text-[13px] text-gray-500 truncate">{emp.department}</div>

                  {/* Role */}
                  <div className="text-[13px] text-gray-500 truncate">
                    {roleLabels[emp.role] || emp.role}
                  </div>

                  {/* Location */}
                  <div className="text-[13px] text-gray-500 truncate">{emp.work_location}</div>

                  {/* Status */}
                  <div>
                    <Badge variant={statusVariant[emp.employment_status] || 'neutral'}>
                      {emp.employment_status}
                    </Badge>
                  </div>

                  {/* Joined */}
                  <div className="text-[12px] text-gray-400">
                    {emp.joining_date
                      ? new Date(emp.joining_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                      : '—'}
                  </div>
                </div>
              );
            })}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-5 py-3">
                <div className="text-[12px] text-gray-400">
                  Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of {total}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page === 1}
                    className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center transition-colors',
                      page === 1 ? 'text-gray-300' : 'text-gray-500 hover:bg-hover-bg'
                    )}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      className={cn(
                        'w-8 h-8 rounded-lg flex items-center justify-center text-[13px] font-medium transition-colors',
                        p === page ? 'bg-olive text-white' : 'text-gray-500 hover:bg-hover-bg'
                      )}
                    >
                      {p}
                    </button>
                  ))}
                  <button
                    onClick={() => setPage(Math.min(totalPages, page + 1))}
                    disabled={page === totalPages}
                    className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center transition-colors',
                      page === totalPages ? 'text-gray-300' : 'text-gray-500 hover:bg-hover-bg'
                    )}
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      {/* Employee Detail Drawer */}
      <EmployeeDetail
        employee={selectedEmployee}
        open={!!selectedEmployee}
        onClose={() => setSelectedEmployee(null)}
      />

      {/* Add Employee Drawer — same component used on Dashboard */}
      <AddEmployeeDrawer
        open={showAddEmployee}
        onClose={() => {
          setShowAddEmployee(false);
          fetchEmployees(); // Refresh list after adding
        }}
      />
    </div>
  );
}

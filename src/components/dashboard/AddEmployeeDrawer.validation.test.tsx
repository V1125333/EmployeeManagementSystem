import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  AddEmployeeDrawer,
  INITIAL_FORM,
  validateAddEmployeeForm,
  type FormState,
} from '@/components/dashboard/AddEmployeeDrawer';
import { ToastProvider } from '@/components/ui/Toast';

const validForm: FormState = {
  ...INITIAL_FORM,
  firstName: 'Asha',
  lastName: 'Rao',
  workEmail: 'asha.rao@example.com',
  countryCode: '+1',
  phone: '(860) 555-0142',
  dateOfBirth: '1993-04-12',
  workforceType: 'full_time',
  role: 'employee',
  department: 'Engineering',
  designation: 'Software Engineer',
  reportingManager: 'David Park',
  joiningDate: '2026-10-12',
  workLocation: 'Hybrid',
  workCity: 'Hartford',
  workState: 'CT',
  workCountry: 'United States',
};

describe('Add Employee validation', () => {
  it('accepts a complete valid employee across supported formatted values', () => {
    expect(validateAddEmployeeForm(validForm, new Date('2026-10-03T12:00:00Z'))).toEqual({});
    expect(validateAddEmployeeForm({ ...validForm, firstName: 'José', lastName: 'O’Connor', phone: '+91 98765-43210' }, new Date('2026-10-03T12:00:00Z'))).toEqual({});
  });

  it.each([
    ['', 'Work email is required'],
    ['asha', 'Enter a valid work email address.'],
    ['asha@company', 'Enter a valid work email address.'],
    ['asha company@example.com', 'Enter a valid work email address.'],
  ])('rejects invalid email value %j', (workEmail, message) => {
    expect(validateAddEmployeeForm({ ...validForm, workEmail }).workEmail).toBe(message);
  });

  it.each([
    ['', 'Phone number is required'],
    ['letters-only', 'Enter a valid phone number with 7 to 15 digits'],
    ['123456', 'Enter a valid phone number with 7 to 15 digits'],
    ['1234567890123456', 'Enter a valid phone number with 7 to 15 digits'],
  ])('rejects invalid phone value %j', (phone, message) => {
    expect(validateAddEmployeeForm({ ...validForm, phone }).phone).toBe(message);
  });

  it('rejects future birth dates and excessive text lengths', () => {
    const errors = validateAddEmployeeForm({
      ...validForm,
      firstName: 'A'.repeat(101),
      lastName: 'B'.repeat(101),
      dateOfBirth: '2026-10-04',
      workCity: 'C'.repeat(121),
      workState: 'S'.repeat(121),
      workCountry: 'U'.repeat(121),
    }, new Date('2026-10-03T12:00:00Z'));

    expect(errors).toMatchObject({
      firstName: 'First name must be 100 characters or fewer',
      lastName: 'Last name must be 100 characters or fewer',
      dateOfBirth: 'Date of birth cannot be in the future',
      workCity: 'Work city must be 120 characters or fewer',
      workState: 'State / province must be 120 characters or fewer',
      workCountry: 'Work country must be 120 characters or fewer',
    });
  });

  it('shows every required validation, including custom dropdowns', () => {
    render(<ToastProvider><AddEmployeeDrawer open onClose={vi.fn()} /></ToastProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Add Employee' }));

    for (const message of [
      'First name is required',
      'Last name is required',
      'Work email is required',
      'Phone number is required',
      'Date of birth is required for setup code',
      'Employment type is required',
      'Role is required',
      'Department is required',
      'Reporting manager is required',
      'Joining date is required',
      'Work arrangement is required',
      'Work city is required',
      'Work country is required',
    ]) {
      expect(screen.getByText(message)).toBeInTheDocument();
    }
  });
});


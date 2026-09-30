import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Sidebar } from './Sidebar';
import { RoleHomeRedirect } from './ProtectedRoute';

const auth = vi.hoisted(() => ({ user: { role: 'super_admin', name: 'Super Admin' }, logout: vi.fn() }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => auth }));
vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ sidebarCollapsed: false, saveAppearancePatch: vi.fn() }) }));
vi.mock('@/components/ui/ProfileDropdown', () => ({ ProfileDropdown: () => null }));
afterEach(cleanup);

describe('overview navigation', () => {
  it('puts one Overview before My Dashboard and opens the workforce page for Super Admin', () => {
    auth.user.role = 'super_admin';
    render(<MemoryRouter initialEntries={['/employee']}><Sidebar /><Routes>
      <Route path="/employee" element={<div>Personal page</div>} />
      <Route path="/dashboard" element={<div>Workforce page</div>} />
    </Routes></MemoryRouter>);
    const overview = screen.getByRole('button', { name: 'Overview' });
    const personal = screen.getByRole('button', { name: 'My Dashboard' });
    expect(overview.compareDocumentPosition(personal) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(overview);
    expect(screen.getByText('Workforce page')).toBeVisible();
  });

  it('does not expose Overview to employees', () => {
    auth.user.role = 'employee';
    render(<MemoryRouter><Sidebar /></MemoryRouter>);
    expect(screen.queryByRole('button', { name: 'Overview' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'My Dashboard' })).toBeVisible();
  });

  it('shows organization-level projects and timesheets only once', () => {
    auth.user.role = 'super_admin';
    render(<MemoryRouter><Sidebar /></MemoryRouter>);

    expect(screen.getAllByRole('button', { name: 'Projects' })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'My Allocations' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'My Timesheets' })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Timesheets' })).not.toBeInTheDocument();
  });

  it('shows self-service projects and timesheets only once', () => {
    auth.user.role = 'employee';
    render(<MemoryRouter><Sidebar /></MemoryRouter>);

    expect(screen.getAllByRole('button', { name: 'My Allocations' })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Projects' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Timesheets' })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'My Timesheets' })).not.toBeInTheDocument();
  });

  it.each([['super_admin', '/dashboard'], ['employee', '/employee']])('lands %s on %s', (role, destination) => {
    auth.user.role = role;
    render(<MemoryRouter><Routes>
      <Route path="/" element={<RoleHomeRedirect />} />
      <Route path={destination} element={<div>Correct landing page</div>} />
    </Routes></MemoryRouter>);
    expect(screen.getByText('Correct landing page')).toBeVisible();
  });
});

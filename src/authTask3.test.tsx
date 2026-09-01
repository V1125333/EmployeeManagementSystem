import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from '@/hooks/useAuth';
import { ForceChangePasswordPage } from '@/pages/ForceChangePasswordPage';
import { ORBIT_AUTH_STORAGE_KEY } from '@/services/apiClient';
import profileSource from '@/pages/ProfilePage.tsx?raw';
import careerSource from '@/pages/MyCareerProfilePage.tsx?raw';
import employeesSource from '@/pages/EmployeesPage.tsx?raw';
import loginSource from '@/pages/LoginPage.tsx?raw';

const storedUser = {
  id: 'employee-1',
  name: 'Stored User',
  email: 'stored@example.com',
  role: 'employee',
  initials: 'SU',
  forcePasswordChange: false,
};

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe('Task 3 authentication and profile frontend', () => {
  it('refreshes restored authentication from bearer-authenticated GET /auth/me', async () => {
    localStorage.setItem(ORBIT_AUTH_STORAGE_KEY, JSON.stringify({ user: storedUser, token: 'orbit-jwt' }));
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      success: true,
      employee: {
        id: 'employee-1',
        first_name: 'Current',
        last_name: 'Employee',
        work_email: 'current@example.com',
        role: 'manager',
        profile_image_url: '/current.png',
        force_password_change: false,
      },
    }));
    vi.stubGlobal('fetch', fetchMock);

    function Probe() {
      const { user } = useAuth();
      return <span>{user?.email}</span>;
    }

    render(
      <MemoryRouter>
        <AuthProvider><Probe /></AuthProvider>
      </MemoryRouter>,
    );

    await screen.findByText('current@example.com');
    const [url, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(url).toBe('/api/v1/auth/me');
    expect(String(url)).not.toContain('stored@example.com');
    expect(headers.get('Authorization')).toBe('Bearer orbit-jwt');
    expect(headers.has('X-User-Id')).toBe(false);
    expect(headers.has('X-User-Email')).toBe(false);
  });

  it('changes a forced password with bearer authentication and refreshes session state', async () => {
    localStorage.setItem(ORBIT_AUTH_STORAGE_KEY, JSON.stringify({
      user: { ...storedUser, forcePasswordChange: true },
      token: 'forced-orbit-jwt',
    }));
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ success: true, message: 'Password changed.' }))
      .mockResolvedValueOnce(jsonResponse({
        success: true,
        employee: {
          id: 'employee-1',
          first_name: 'Current',
          last_name: 'Employee',
          work_email: 'current@example.com',
          role: 'employee',
          force_password_change: false,
        },
      }));
    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter initialEntries={['/force-change-password']}>
        <AuthProvider>
          <Routes>
            <Route path="/force-change-password" element={<ForceChangePasswordPage />} />
            <Route path="/" element={<div>Home</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    const inputs = document.querySelectorAll('input');
    fireEvent.change(inputs[0], { target: { value: 'Permanent2@' } });
    fireEvent.change(inputs[1], { target: { value: 'Permanent2@' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));

    await screen.findByText('Home');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/auth/force-change-password');
    const forceHeaders = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(forceHeaders.get('Authorization')).toBe('Bearer forced-orbit-jwt');
    expect(forceHeaders.has('X-User-Id')).toBe(false);
    expect(forceHeaders.has('X-User-Email')).toBe(false);
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/auth/me');
    await waitFor(() => {
      const session = JSON.parse(localStorage.getItem(ORBIT_AUTH_STORAGE_KEY) || '{}');
      expect(session.token).toBe('forced-orbit-jwt');
      expect(session.user.forcePasswordChange).toBe(false);
    });
  });

  it('keeps Task 3 current-profile, admin-reset, recovery, and unlock callers classified correctly', () => {
    expect(profileSource).toContain('authenticatedFetch(`${API_BASE}/auth/me`)');
    expect(careerSource).toContain('authenticatedFetch(`${API_BASE}/auth/me`)');
    expect(profileSource).not.toMatch(/auth\/me\/\$\{encodeURIComponent/);
    expect(careerSource).not.toMatch(/auth\/me\/\$\{encodeURIComponent/);

    const adminResetCall = employeesSource.slice(
      employeesSource.indexOf('/auth/admin-reset-password') - 200,
      employeesSource.indexOf('/auth/admin-reset-password') + 400,
    );
    expect(adminResetCall).toContain('authenticatedFetch');
    expect(adminResetCall.toLowerCase()).not.toContain('x-user-');

    for (const endpoint of [
      '/auth/login/verify-password',
      '/auth/login/verify-mfa',
      '/auth/forgot-password/initiate',
      '/auth/request-unlock',
    ]) {
      const position = loginSource.indexOf(endpoint);
      expect(loginSource.slice(position - 80, position)).toContain('publicFetch');
    }
  });
});

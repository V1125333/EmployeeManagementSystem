import React from 'react';
import { act, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from '@/hooks/useAuth';
import {
  ApiError,
  ORBIT_AUTH_STORAGE_KEY,
  ORBIT_PASSWORD_CHANGE_REQUIRED_EVENT,
  ORBIT_SESSION_EXPIRED_EVENT,
  authenticatedFetch,
  downloadBlob,
  publicFetch,
  readOrbitSession,
  requestJson,
  uploadFormData,
  writeOrbitSession,
} from './apiClient';

const user = { id: 'employee-1', name: 'Orbit User' };

function response(body: BodyInit | null, init: ResponseInit = {}): Response {
  return new Response(body, init);
}

beforeEach(() => {
  localStorage.clear();
  writeOrbitSession({ user, token: 'orbit-jwt' });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('authenticatedFetch', () => {
  it('adds the Orbit bearer token, preserves existing compatibility headers, and cannot be overridden', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await authenticatedFetch('/api/v1/protected', {
      headers: {
        Authorization: 'Bearer msal-or-caller-token',
        'X-Correlation-Id': 'corr-1',
        'X-User-Id': 'employee-1',
      },
    });

    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get('Authorization')).toBe('Bearer orbit-jwt');
    expect(headers.get('X-Correlation-Id')).toBe('corr-1');
    expect(headers.get('X-User-Id')).toBe('employee-1');
  });

  it('does not invent identity headers', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response('{}'));
    vi.stubGlobal('fetch', fetchMock);
    await authenticatedFetch('/api/v1/protected');
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.has('X-User-Id')).toBe(false);
    expect(headers.has('X-User-Email')).toBe(false);
    expect(headers.has('X-User-Name')).toBe(false);
  });

  it('fails locally without a token even when a legacy identity header exists', async () => {
    localStorage.clear();
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    await expect(authenticatedFetch('/api/v1/protected', { headers: { 'X-User-Id': 'employee-1' } }))
      .rejects.toMatchObject({ status: 401, code: 'AUTHENTICATION_REQUIRED' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('bounds repeated missing-token expiration signals until a new session is written', async () => {
    localStorage.clear();
    const listener = vi.fn();
    window.addEventListener(ORBIT_SESSION_EXPIRED_EVENT, listener);
    await authenticatedFetch('/api/v1/one').catch(() => undefined);
    await authenticatedFetch('/api/v1/two').catch(() => undefined);
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(ORBIT_SESSION_EXPIRED_EVENT, listener);
  });

  it('uses an explicit Orbit token instead of stored or caller authorization tokens', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response('{}'));
    vi.stubGlobal('fetch', fetchMock);
    await authenticatedFetch('/api/v1/ai/chat', { headers: { Authorization: 'Bearer msal-token' } }, 'explicit-orbit-jwt');
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('Authorization')).toBe('Bearer explicit-orbit-jwt');
  });

  it('clears the Orbit session and emits one expiration signal on backend 401', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response('', { status: 401 })));
    const listener = vi.fn();
    window.addEventListener(ORBIT_SESSION_EXPIRED_EVENT, listener, { once: true });
    await authenticatedFetch('/api/v1/protected');
    expect(readOrbitSession()).toBeNull();
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('does not let a stale 401 erase a newly established session', async () => {
    let finishOldRequest: ((value: Response) => void) | undefined;
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise<Response>((resolve) => {
      finishOldRequest = resolve;
    })));
    const listener = vi.fn();
    window.addEventListener(ORBIT_SESSION_EXPIRED_EVENT, listener);

    const oldRequest = authenticatedFetch('/api/v1/slow-request');
    writeOrbitSession({ user, token: 'new-orbit-jwt' });
    finishOldRequest?.(response('', { status: 401 }));
    await oldRequest;

    expect(readOrbitSession()?.token).toBe('new-orbit-jwt');
    expect(listener).not.toHaveBeenCalled();
    window.removeEventListener(ORBIT_SESSION_EXPIRED_EVENT, listener);
  });

  it('does not expire the session for an ordinary 403', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(JSON.stringify({ detail: { code: 'FORBIDDEN' } }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    })));
    const listener = vi.fn();
    window.addEventListener(ORBIT_SESSION_EXPIRED_EVENT, listener, { once: true });
    await authenticatedFetch('/api/v1/protected');
    expect(readOrbitSession()).not.toBeNull();
    expect(listener).not.toHaveBeenCalled();
  });

  it('signals PASSWORD_CHANGE_REQUIRED without expiring the session', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(JSON.stringify({ detail: { code: 'PASSWORD_CHANGE_REQUIRED' } }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    })));
    const listener = vi.fn();
    window.addEventListener(ORBIT_PASSWORD_CHANGE_REQUIRED_EVENT, listener, { once: true });
    await authenticatedFetch('/api/v1/protected');
    expect(listener).toHaveBeenCalledTimes(1);
    expect(readOrbitSession()).not.toBeNull();
  });
});

describe('request formats and responses', () => {
  it('sets JSON content type and handles JSON, 204, and an empty success', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(JSON.stringify({ saved: true }), { status: 201 }))
      .mockResolvedValueOnce(response(null, { status: 204 }))
      .mockResolvedValueOnce(response('', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(requestJson<{ saved: boolean }>('/api/v1/items', { method: 'POST', body: '{}' }))
      .resolves.toEqual({ saved: true });
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('Content-Type')).toBe('application/json');
    await expect(requestJson('/api/v1/items/1', { method: 'DELETE' })).resolves.toBeUndefined();
    await expect(requestJson('/api/v1/items')).resolves.toBeUndefined();
  });

  it('uploads FormData without forcing a multipart content type', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response('{}'));
    vi.stubGlobal('fetch', fetchMock);
    const form = new FormData();
    form.append('file', new Blob(['data']), 'file.txt');
    await uploadFormData('/api/v1/documents', form, { method: 'POST', headers: { 'X-User-Id': 'employee-1' } });
    const options = fetchMock.mock.calls[0][1];
    const headers = new Headers(options.headers);
    expect(headers.has('Content-Type')).toBe(false);
    expect(headers.get('Authorization')).toBe('Bearer orbit-jwt');
    expect(options.body).toBe(form);
  });

  it('downloads a blob with bearer authentication and preserves a response filename', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(new Blob(['report']), {
      headers: { 'Content-Disposition': 'attachment; filename="report.pdf"' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const result = await downloadBlob('/api/v1/reports/1');
    expect(result.blob.size).toBeGreaterThan(0);
    expect(result.filename).toBe('report.pdf');
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('Authorization')).toBe('Bearer orbit-jwt');
  });

  it('parses download failures and redacts bearer and legacy identity values', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(JSON.stringify({
      detail: {
        code: 'DOWNLOAD_DENIED',
        message: 'Bearer secret-token X-User-Email:person@example.com',
      },
    }), { status: 403, headers: { 'Content-Type': 'application/json' } })));
    let error: ApiError | undefined;
    try {
      await downloadBlob('/api/v1/reports/1');
    } catch (caught) {
      error = caught as ApiError;
    }
    expect(error).toBeInstanceOf(ApiError);
    expect(error?.status).toBe(403);
    expect(error?.code).toBe('DOWNLOAD_DENIED');
    expect(JSON.stringify(error)).not.toContain('secret-token');
    expect(JSON.stringify(error)).not.toContain('person@example.com');
  });
});

describe('public transport and authentication state', () => {
  it('allows public requests with no Orbit token and never adds authorization', async () => {
    localStorage.clear();
    const fetchMock = vi.fn().mockResolvedValue(response('{}'));
    vi.stubGlobal('fetch', fetchMock);
    await publicFetch('/api/v1/auth/login', { method: 'POST' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).has('Authorization')).toBe(false);
  });

  it('rejects and removes a persisted user that has no access token', () => {
    localStorage.setItem(ORBIT_AUTH_STORAGE_KEY, JSON.stringify({ user, token: '' }));
    expect(readOrbitSession()).toBeNull();
    expect(localStorage.getItem(ORBIT_AUTH_STORAGE_KEY)).toBeNull();
  });

  it('rejects malformed persisted user data even when a token is present', () => {
    localStorage.setItem(ORBIT_AUTH_STORAGE_KEY, JSON.stringify({ user: 'not-a-user', token: 'orbit-jwt' }));
    expect(readOrbitSession()).toBeNull();
    expect(localStorage.getItem(ORBIT_AUTH_STORAGE_KEY)).toBeNull();
  });

  it('does not authenticate AuthProvider from a stored user without a token', () => {
    localStorage.setItem(ORBIT_AUTH_STORAGE_KEY, JSON.stringify({ user }));
    let isAuthenticated: boolean | undefined;
    function Probe() {
      isAuthenticated = useAuth().isAuthenticated;
      return null;
    }
    render(React.createElement(MemoryRouter, null,
      React.createElement(AuthProvider, null, React.createElement(Probe))));
    expect(isAuthenticated).toBe(false);
  });

  it('keeps login on the public transport', async () => {
    localStorage.clear();
    const fetchMock = vi.fn().mockResolvedValue(response(JSON.stringify({ success: false, message: 'No' }), {
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    let login: ReturnType<typeof useAuth>['loginWithApi'] | undefined;
    function Probe() {
      login = useAuth().loginWithApi;
      return null;
    }
    render(React.createElement(MemoryRouter, { initialEntries: ['/login'] },
      React.createElement(AuthProvider, null, React.createElement(Probe))));
    await act(async () => { await login?.('person@example.com', 'password', '123456'); });
    expect(new Headers(fetchMock.mock.calls[0][1].headers).has('Authorization')).toBe(false);
  });
});

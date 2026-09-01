import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ORBIT_AUTH_STORAGE_KEY } from './apiClient';
import { submitPlatformPreview } from './platformPreviewApi';

describe('platform preview transport', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    localStorage.setItem(ORBIT_AUTH_STORAGE_KEY, JSON.stringify({ user: { id: 'safe-user' }, token: 'safe-token' }));
  });

  it('uses bearer authentication and sends only the message', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ employee_response: {}, developer_summary: {} }), { status: 200 }));
    await submitPlatformPreview('Who is my manager?');
    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get('Authorization')).toBe('Bearer safe-token');
    expect(JSON.parse(String(init?.body))).toEqual({ message: 'Who is my manager?' });
    expect([...headers.keys()].some((key) => key.startsWith('x-user-'))).toBe(false);
  });
});

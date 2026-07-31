import { afterEach, describe, expect, it, vi } from 'vitest';
import { AIAPIError, sendAIChat } from './aiApi';

afterEach(() => vi.unstubAllGlobals());

describe('sendAIChat', () => {
  it('sends only the message and conversation id with a bearer token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        conversation_id: 'conv-1',
        status: 'unsupported',
        message: { role: 'assistant', content: 'Not available yet.' },
        result: null,
        error: null,
        tool_used: null,
        correlation_id: 'corr-1',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
    await sendAIChat('hello', 'signed-token', 'conv-1');
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.Authorization).toBe('Bearer signed-token');
    expect(JSON.parse(options.body)).toEqual({ message: 'hello', conversation_id: 'conv-1' });
  });

  it('rejects before network access when no signed token exists', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    await expect(sendAIChat('balance', null)).rejects.toBeInstanceOf(AIAPIError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('keeps server errors generic while exposing a correlation id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({
        detail: { message: 'Temporarily unavailable.', correlation_id: 'corr-503' },
      }),
    }));
    await expect(sendAIChat('balance', 'signed-token')).rejects.toMatchObject({
      message: 'Temporarily unavailable.',
      correlationId: 'corr-503',
      status: 503,
    });
  });
});

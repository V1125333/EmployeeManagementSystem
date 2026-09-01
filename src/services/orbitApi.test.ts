import { afterEach, describe, expect, it, vi } from 'vitest';

import { sendOrbitMessage } from './orbitApi';

vi.mock('./apiClient', () => ({
  authenticatedFetch: vi.fn(),
  apiErrorFromResponse: vi.fn(async () => new Error('request failed')),
}));

import { authenticatedFetch } from './apiClient';

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('orbitApi', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sends the message without a conversation id on the first turn', async () => {
    vi.mocked(authenticatedFetch).mockResolvedValueOnce(
      jsonResponse({ message: 'Hi!', conversation_id: 'conversation-1' }),
    );

    await sendOrbitMessage('hello');

    const [, options] = vi.mocked(authenticatedFetch).mock.calls[0];
    expect(JSON.parse(String(options?.body))).toEqual({ message: 'hello' });
  });

  it('includes the conversation id on subsequent turns', async () => {
    vi.mocked(authenticatedFetch).mockResolvedValueOnce(
      jsonResponse({ message: 'Still talking', conversation_id: 'conversation-1' }),
    );

    await sendOrbitMessage('what about last year?', 'conversation-1');

    const [, options] = vi.mocked(authenticatedFetch).mock.calls[0];
    expect(JSON.parse(String(options?.body))).toEqual({
      message: 'what about last year?',
      conversation_id: 'conversation-1',
    });
  });
});

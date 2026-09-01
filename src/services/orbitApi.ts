import { apiErrorFromResponse, authenticatedFetch } from '@/services/apiClient';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export type OrbitChatResponse = {
  message: string;
  conversation_id: string;
};

export async function sendOrbitMessage(
  message: string,
  conversationId?: string,
): Promise<OrbitChatResponse> {
  const response = await authenticatedFetch(`${API_BASE}/orbit/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    }),
  });
  if (!response.ok) throw await apiErrorFromResponse(response);
  return response.json() as Promise<OrbitChatResponse>;
}

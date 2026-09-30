export const ORBIT_AUTH_STORAGE_KEY = 'reknew_orbit_auth';
export const ORBIT_SESSION_EXPIRED_EVENT = 'orbit:session-expired';
export const ORBIT_PASSWORD_CHANGE_REQUIRED_EVENT = 'orbit:password-change-required';

const MAX_ERROR_TEXT_LENGTH = 2_000;
let sessionExpirationSignaled = false;

export interface OrbitSession<TUser = unknown> { user: TUser; token: string }

export interface ApiErrorDetails {
  status: number;
  code?: string;
  message: string;
  requestId?: string;
  details?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly requestId?: string;
  readonly details?: unknown;

  constructor(error: ApiErrorDetails) {
    super(error.message);
    this.name = 'ApiError';
    this.status = error.status;
    this.code = error.code;
    this.requestId = error.requestId;
    this.details = error.details;
  }
}

function getStorage(): Storage | null {
  return typeof window === 'undefined' ? null : window.localStorage;
}

export function readOrbitSession<TUser = unknown>(): OrbitSession<TUser> | null {
  const storage = getStorage();
  if (!storage) return null;
  try {
    const raw = storage.getItem(ORBIT_AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<OrbitSession<TUser>>;
    if (!parsed.user || typeof parsed.user !== 'object' || Array.isArray(parsed.user)
      || typeof parsed.token !== 'string' || !parsed.token.trim()) {
      storage.removeItem(ORBIT_AUTH_STORAGE_KEY);
      return null;
    }
    return { user: parsed.user, token: parsed.token.trim() };
  } catch {
    storage.removeItem(ORBIT_AUTH_STORAGE_KEY);
    return null;
  }
}

export function writeOrbitSession<TUser>(session: OrbitSession<TUser>): void {
  const token = session.token.trim();
  if (!session.user || !token) throw new Error('A valid Orbit session requires a user and access token.');
  getStorage()?.setItem(ORBIT_AUTH_STORAGE_KEY, JSON.stringify({ user: session.user, token }));
  sessionExpirationSignaled = false;
}

export function clearOrbitSession(): void {
  getStorage()?.removeItem(ORBIT_AUTH_STORAGE_KEY);
}

function emit(name: string, detail?: unknown): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent(name, { detail }));
}

function expireOrbitSession(): void {
  clearOrbitSession();
  if (sessionExpirationSignaled) return;
  sessionExpirationSignaled = true;
  emit(ORBIT_SESSION_EXPIRED_EVENT);
}

function sanitizeText(value: string): string {
  return value.slice(0, MAX_ERROR_TEXT_LENGTH)
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [REDACTED]')
    .replace(/(X-User-(?:Id|Email|Name)["']?\s*[:=]\s*["']?)[^,"'\s}]+/gi, '$1[REDACTED]');
}

function sanitizeDetails(value: unknown): unknown {
  if (value == null) return value;
  try { return JSON.parse(sanitizeText(JSON.stringify(value))); }
  catch { return sanitizeText(String(value)); }
}

async function readErrorBody(response: Response): Promise<unknown> {
  const text = await response.text().catch(() => '');
  if (!text) return undefined;
  try { return JSON.parse(text); }
  catch { return sanitizeText(text); }
}

function errorFields(body: unknown): { code?: string; message?: string; requestId?: string; details?: unknown } {
  const root = body && typeof body === 'object' ? body as Record<string, unknown> : {};
  const detail = root.detail && typeof root.detail === 'object' ? root.detail as Record<string, unknown> : root;
  const message = typeof detail.message === 'string' ? detail.message
    : typeof root.detail === 'string' ? root.detail
      : typeof root.message === 'string' ? root.message
        : typeof body === 'string' ? body : undefined;
  return {
    code: typeof detail.code === 'string' ? detail.code : typeof root.code === 'string' ? root.code : undefined,
    message,
    requestId: typeof detail.correlation_id === 'string' ? detail.correlation_id
      : typeof root.correlation_id === 'string' ? root.correlation_id
        : typeof root.request_id === 'string' ? root.request_id : undefined,
    details: sanitizeDetails(body),
  };
}

export async function apiErrorFromResponse(response: Response): Promise<ApiError> {
  const fields = errorFields(await readErrorBody(response));
  return new ApiError({
    status: response.status,
    code: fields.code,
    message: sanitizeText(fields.message || `Request failed with status ${response.status}.`),
    requestId: fields.requestId || response.headers.get('X-Request-Id') || undefined,
    details: fields.details,
  });
}

export function publicFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return fetch(input, init);
}

/**
 * Sends the Orbit JWT while preserving caller-supplied compatibility headers.
 * X-User-* headers are temporary route-contract inputs, not authentication, and
 * this transport never creates or falls back to them.
 */
export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
  explicitOrbitAccessToken?: string | null,
): Promise<Response> {
  const orbitAccessToken = explicitOrbitAccessToken?.trim() || readOrbitSession()?.token;
  if (!orbitAccessToken) {
    expireOrbitSession();
    throw new ApiError({ status: 401, code: 'AUTHENTICATION_REQUIRED', message: 'Please sign in again.' });
  }
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${orbitAccessToken}`);
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401) {
    // A request started with an older token can finish after the user has
    // already signed in again. Never let that stale 401 erase the newer
    // session and bounce the user back to the login page.
    const currentOrbitAccessToken = readOrbitSession()?.token;
    if (!currentOrbitAccessToken || currentOrbitAccessToken === orbitAccessToken) {
      expireOrbitSession();
    }
  } else if (response.status === 403) {
    const fields = errorFields(await readErrorBody(response.clone()));
    if (fields.code === 'PASSWORD_CHANGE_REQUIRED') {
      emit(ORBIT_PASSWORD_CHANGE_REQUIRED_EVENT, { code: fields.code });
    }
  }
  return response;
}

function withJsonHeaders(init: RequestInit): RequestInit {
  const headers = new Headers(init.headers);
  if (init.body != null && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return { ...init, headers };
}

async function parseSuccess<T>(response: Response): Promise<T | undefined> {
  if (response.status === 204) return undefined;
  const text = await response.text();
  if (!text) return undefined;
  return JSON.parse(text) as T;
}

export async function requestJson<T>(input: RequestInfo | URL, init: RequestInit = {}, explicitOrbitAccessToken?: string | null): Promise<T | undefined> {
  const response = await authenticatedFetch(input, withJsonHeaders(init), explicitOrbitAccessToken);
  if (!response.ok) throw await apiErrorFromResponse(response);
  return parseSuccess<T>(response);
}

export async function publicRequestJson<T>(input: RequestInfo | URL, init: RequestInit = {}): Promise<T | undefined> {
  const response = await publicFetch(input, withJsonHeaders(init));
  if (!response.ok) throw await apiErrorFromResponse(response);
  return parseSuccess<T>(response);
}

export function uploadFormData(input: RequestInfo | URL, formData: FormData, init: Omit<RequestInit, 'body'> = {}, explicitOrbitAccessToken?: string | null): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.delete('Content-Type');
  return authenticatedFetch(input, { ...init, headers, body: formData }, explicitOrbitAccessToken);
}

export interface DownloadedFile { blob: Blob; filename?: string }

export async function downloadBlob(input: RequestInfo | URL, init: RequestInit = {}, explicitOrbitAccessToken?: string | null): Promise<DownloadedFile> {
  const response = await authenticatedFetch(input, init, explicitOrbitAccessToken);
  if (!response.ok) throw await apiErrorFromResponse(response);
  const disposition = response.headers.get('Content-Disposition') || '';
  const filename = disposition.match(/filename\*?=(?:UTF-8''|["'])?([^"';]+)/i)?.[1];
  return { blob: await response.blob(), filename: filename ? decodeURIComponent(filename.trim()) : undefined };
}

/**
 * HTTP client for the REST API. Same-origin (Vite proxy), session cookie auth, and the Django
 * CSRF token echoed in `X-CSRFToken` for unsafe methods. Never handles OAuth tokens.
 */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1';

export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, data: unknown, message?: string) {
    super(message ?? ApiError.messageFrom(data) ?? `Request failed (${status})`);
    this.status = status;
    this.data = data;
  }

  static messageFrom(data: unknown): string | undefined {
    if (data && typeof data === 'object') {
      const d = data as Record<string, unknown>;
      if (typeof d.detail === 'string') return d.detail;
      if (Array.isArray(d.non_field_errors)) return String(d.non_field_errors[0]);
    }
    return undefined;
  }

  get fieldErrors(): FieldErrors {
    if (!this.data || typeof this.data !== 'object') return {};
    const out: FieldErrors = {};
    for (const [k, v] of Object.entries(this.data as Record<string, unknown>)) {
      if (Array.isArray(v)) out[k] = v.map(String);
      else if (typeof v === 'string' && k !== 'detail') out[k] = [v];
    }
    return out;
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split('=')[1]) : null;
}

let csrfPromise: Promise<void> | null = null;
export async function ensureCsrf(force = false): Promise<void> {
  if (!force && readCookie('csrftoken')) return;
  if (!csrfPromise || force) {
    csrfPromise = fetch(`${API_BASE}/auth/csrf`, { credentials: 'include' }).then(() => undefined);
  }
  await csrfPromise;
}

type Query = Record<string, string | number | boolean | undefined | null>;

export function buildQuery(params?: Query): string {
  if (!params) return '';
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export async function apiRequest<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Query; signal?: AbortSignal } = {},
): Promise<T> {
  const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(method);
  if (unsafe) await ensureCsrf();
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (unsafe) headers['X-CSRFToken'] = readCookie('csrftoken') ?? '';

  const res = await fetch(`${API_BASE}${path}${buildQuery(options.query)}`, {
    method,
    headers,
    credentials: 'include',
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text.slice(0, 200) };
    }
  }
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

export const api = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal) =>
    apiRequest<T>('GET', path, { query, signal }),
  post: <T>(path: string, body?: unknown) => apiRequest<T>('POST', path, { body }),
  patch: <T>(path: string, body?: unknown) => apiRequest<T>('PATCH', path, { body }),
  delete: <T>(path: string) => apiRequest<T>('DELETE', path),
};

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

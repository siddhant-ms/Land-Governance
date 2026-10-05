export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: Record<string, any> = {}) { super(message); }
}
const KEY = 'sih26019.token';
export const tokenStore = {
  get: (): string | null => (typeof window === 'undefined' ? null : window.localStorage.getItem(KEY)),
  set: (t: string) => window.localStorage.setItem(KEY, t),
  clear: () => window.localStorage.removeItem(KEY),
};

export async function api<T>(path: string, opts: { method?: string; body?: unknown; form?: FormData; signal?: AbortSignal } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const t = tokenStore.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { method: opts.method ?? (opts.body || opts.form ? 'POST' : 'GET'), headers, signal: opts.signal,
      body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined) });
  } catch {
    throw new ApiError(0, 'NETWORK', 'Cannot reach the platform API. Check that the backend is running.');
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = data?.error;
    if (res.status === 401 && t && e?.code === 'INVALID_TOKEN') tokenStore.clear();
    throw new ApiError(res.status, e?.code ?? 'ERROR', e?.message ?? `Request failed (${res.status})`, e?.details ?? {});
  }
  return data as T;
}

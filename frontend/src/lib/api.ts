/**
 * FinCare API client.
 *
 * All calls target the DRF backend under `/api/v1`. In dev/Docker that path is
 * proxied to the backend by a Next.js rewrite (see next.config.ts), so the
 * browser stays same-origin and no CORS handling is needed.
 *
 * Auth is JWT (djangorestframework-simplejwt): obtain at /auth/token/, refresh
 * at /auth/token/refresh/. Tokens are kept in localStorage for this first cut;
 * hardening to httpOnly cookies + middleware is a planned follow-up.
 */

const API_BASE = "/api/v1";
const ACCESS_KEY = "fincare_access";
const REFRESH_KEY = "fincare_refresh";

export type Tokens = { access: string; refresh: string };

export function getAccess(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY);
}

export function getRefresh(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY);
}

export function setTokens(t: Tokens): void {
  localStorage.setItem(ACCESS_KEY, t.access);
  localStorage.setItem(REFRESH_KEY, t.refresh);
  notify();
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  notify();
}

// --- Reactive token store (for React's useSyncExternalStore) ---
const listeners = new Set<() => void>();

function notify(): void {
  for (const l of listeners) l();
}

/** Subscribe to auth-token changes (also reacts to other tabs via `storage`). */
export function subscribeTokens(cb: () => void): () => void {
  listeners.add(cb);
  if (typeof window !== "undefined") window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    if (typeof window !== "undefined") window.removeEventListener("storage", cb);
  };
}

export function isAuthedSnapshot(): boolean {
  return getAccess() !== null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function login(email: string, password: string): Promise<Tokens> {
  // The custom User is email-based (USERNAME_FIELD = "email"), so simplejwt's
  // token endpoint expects `email`, not `username`.
  const res = await fetch(`${API_BASE}/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    throw new ApiError("Invalid username or password.", res.status);
  }
  const data = (await res.json()) as Tokens;
  setTokens(data);
  return data;
}

async function refreshAccess(): Promise<string | null> {
  const refresh = getRefresh();
  if (!refresh) return null;
  const res = await fetch(`${API_BASE}/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) {
    clearTokens();
    return null;
  }
  const data = (await res.json()) as { access: string };
  localStorage.setItem(ACCESS_KEY, data.access);
  return data.access;
}

/** Authenticated fetch against `/api/v1<path>`, with one transparent token refresh on 401. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const call = (token: string | null) =>
    fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

  let res = await call(getAccess());
  if (res.status === 401) {
    const refreshed = await refreshAccess();
    if (refreshed) res = await call(refreshed);
  }
  return res;
}

/** Convenience JSON GET that throws ApiError on non-2xx. */
export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  if (!res.ok) throw new ApiError(`GET ${path} failed`, res.status);
  return (await res.json()) as T;
}

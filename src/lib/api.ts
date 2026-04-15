/**
 * RecoverAI — API Client
 * Thin fetch wrapper that:
 *   - Points to /api (proxied to FastAPI by Vite in dev)
 *   - Attaches Bearer token automatically
 *   - Handles 401 → token refresh → retry (once)
 *   - Throws ApiError with { status, detail } for UI consumption
 */

import { getAccessToken, getRefreshToken, saveTokens, clearTokens } from './auth';

const BASE = '/api';

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

// ── Core fetch wrapper ───────────────────────────────────────────────────────

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  headers?: Record<string, string>,
  retry = true,
): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Token expired → try once with refresh token
  if (res.status === 401 && retry) {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          saveTokens(data.access_token, data.refresh_token);
          return request<T>(method, path, body, headers, false);
        }
      } catch {/* fall through */}
    }
    clearTokens();
    window.location.href = '/login';
    throw new ApiError(401, 'Session expired. Please log in again.');
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const json = await res.json();
      detail = json.detail ?? json.message ?? detail;
    } catch {/* ignore parse errors */}
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Convenience methods ─────────────────────────────────────────────────────

export const api = {
  get:    <T>(path: string)                                => request<T>('GET', path),
  post:   <T>(path: string, body?: unknown)                => request<T>('POST', path, body),
  patch:  <T>(path: string, body: unknown)                 => request<T>('PATCH', path, body),
  delete: <T>(path: string)                                => request<T>('DELETE', path),
};

// ── Auth API ────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  is_admin: boolean;
  business_name: string | null;
}

export interface RegisterResponse {
  id: string;
  business_name: string;
  email: string;
  message: string;
}

export interface AuthConfig {
  google_client_id: string | null;
}

export const authApi = {
  /** Register a new user (email + password) */
  register: (businessName: string, email: string, password: string) =>
    api.post<RegisterResponse>('/auth/register', {
      business_name: businessName,
      email,
      password,
    }),

  /** Login with email/password — uses OAuth2 form format */
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    });
    if (!res.ok) {
      const json = await res.json().catch(() => ({}));
      throw new ApiError(res.status, json.detail ?? 'Login failed');
    }
    return res.json();
  },

  /** Login via Google credential token */
  googleLogin: (credential: string, autoRegister: boolean = true) =>
    api.post<TokenResponse>('/auth/google', { credential, auto_register: autoRegister }),

  /** Logout (revoke current token) */
  logout: () => api.post<{ message: string }>('/auth/logout'),

  /** Get public auth config (Google Client ID) */
  config: () => api.get<AuthConfig>('/auth/config'),
};

// ── Invoices API ─────────────────────────────────────────────────────────────

export interface Invoice {
  id: string;
  debtorName: string;
  debtorPhone?: string;
  debtorEmail?: string;
  amount: number;
  dueDate: string;
  status: 'pending' | 'overdue' | 'recovered' | 'legal';
  description?: string;
  daysOverdue?: number;
  interest_data?: {
    principal: number;
    interest_amount: number;
    total_due: number;
    days_overdue: number;
    annual_rate_pct: number;
  };
  proof_url?: string;
}

export interface InvoiceCreate {
  debtorName: string;
  debtorPhone?: string;
  debtorEmail?: string;
  amount: number;
  dueDate: string;
  status?: string;
  description?: string;
}

export const invoicesApi = {
  list: ()                              => api.get<Invoice[]>('/invoices'),
  create: (payload: InvoiceCreate)      => api.post<Invoice>('/invoices', payload),
  update: (id: string, patch: Partial<Invoice>) => api.patch<Invoice>(`/invoices/${id}`, patch),
  remove: (id: string)                  => api.delete<void>(`/invoices/${id}`),

  uploadProof: async (file: File): Promise<{ proof_url: string }> => {
    const token = getAccessToken();
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/invoices/upload-proof`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const json = await res.json().catch(() => ({}));
      throw new ApiError(res.status, json.detail ?? 'Upload failed');
    }
    return res.json();
  },
};

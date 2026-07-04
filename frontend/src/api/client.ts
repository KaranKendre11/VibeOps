// Typed API client for the VibeOps FastAPI backend. All requests are same-origin
// and carry the httpOnly session cookie (credentials: 'include').

import type {
  AppConfig,
  InventoryResult,
  Snapshot,
  ValidateResult,
} from './types';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers:
      options.body !== undefined
        ? { 'Content-Type': 'application/json', ...(options.headers ?? {}) }
        : options.headers,
    ...options,
  });

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    } catch {
      // non-JSON error body — keep the status line
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const api = {
  // ---- boot ----
  createSession: () => post<{ thread_id: string }>('/api/session'),
  getConfig: () => request<AppConfig>('/api/config'),

  // ---- session ----
  // Clear all credentials/setup server-side (the "clear credentials & exit" control).
  resetCredentials: () => post<{ ok: boolean }>('/api/session/reset'),

  // ---- setup ----
  validateOpenAI: (key: string) =>
    post<ValidateResult>('/api/setup/validate-openai', { key }),
  validateGcp: (sa_json: Record<string, unknown>) =>
    post<ValidateResult>('/api/setup/validate-gcp', { sa_json }),
  listProjects: () => request<{ project_ids: string[] }>('/api/setup/projects'),
  completeSetup: (project_id: string, monthly_cost_cap_usd: number) =>
    post<{ ok: boolean }>('/api/setup/complete', { project_id, monthly_cost_cap_usd }),
  startDemo: () => post<{ ok: boolean; thread_id: string }>('/api/setup/demo'),

  // ---- graph flow ----
  startGraph: (prompt: string) => post<Snapshot>('/api/graph/start', { prompt }),
  getState: () => request<Snapshot>('/api/graph/state'),
  resumeGraph: (updates: Record<string, unknown>, as_node?: string) =>
    post<Snapshot>('/api/graph/resume', { updates, as_node }),

  // ---- review (edit HCL / re-estimate without advancing the graph) ----
  reviewEdit: (filename: string, content: string) =>
    post<Snapshot>('/api/review/edit', { filename, content }),
  reviewReestimate: () => post<Snapshot>('/api/review/reestimate'),

  // ---- deployment ----
  // Pass overrideCostCap=true to deploy a plan that exceeds the monthly cap (the
  // backend rejects it with 409 otherwise). Omitting it keeps the gated default.
  startDeploy: (overrideCostCap = false) =>
    post<{ status: string }>('/api/deploy/start', { override_cost_cap: overrideCostCap }),
  retryDeploy: () => post<{ status: string }>('/api/deploy/retry'),
  destroy: () => post<{ status: string }>('/api/deploy/destroy'),

  // ---- inventory ----
  getInventory: () => request<InventoryResult>('/api/inventory'),
  deleteInstance: (zone: string, name: string) =>
    request<{ ok: boolean }>(`/api/inventory/${encodeURIComponent(zone)}/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),
};

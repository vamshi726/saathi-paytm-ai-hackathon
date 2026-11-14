import type { Approval, Case, Client, Evaluation, Event, Message, Metrics, Session } from './types';
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export function createApi(getToken: () => Promise<string | null>): Client {
  async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const token = await getToken();
    if (!token) throw new ApiError(401, 'Sign in or enter your local demo token.');
    let response: Response;
    try {
      response = await fetch('/api' + path, {
        method, headers: { Authorization: 'Bearer ' + token, ...(body ? { 'Content-Type': 'application/json' } : {}) },
        body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(20000),
      });
    } catch {
      throw new ApiError(0, 'The API could not be reached. Refresh to check the saved case before repeating an action.');
    }
    if (!response.ok) {
      const messages: Record<number, string> = {
        401: 'Your session is missing or expired. Reconnect to continue.',
        403: 'Your server-assigned role cannot perform this action.',
        404: 'This record or feature is not available on the connected backend.',
        409: 'The case or approval changed. Refresh and review the current evidence.',
        503: 'The backend needs its local demo token configured.',
      };
      throw new ApiError(response.status, messages[response.status] ?? 'The request failed. Refresh the saved state before retrying.');
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
  const casePath = (id: string) => '/cases/' + encodeURIComponent(id);
  return {
    session: () => request<Session>('/session'), cases: () => request<Case[]>('/cases'),
    detail: id => request<Case>(casePath(id)), events: id => request<Event[]>(casePath(id) + '/events'),
    run: id => request<Case>(casePath(id) + '/run', 'POST'),
    messages: id => request<Message[]>(casePath(id) + '/messages'),
    send: (id, text) => request<Case>(casePath(id) + '/messages', 'POST', { text }),
    approvals: () => request<Approval[]>('/approvals'),
    decide: async (a, decision) => { await request('/approvals/' + encodeURIComponent(a.approval_id) + '/decision', 'POST', { decision, payload_hash: a.payload_hash }); },
    metrics: () => request<Metrics>('/metrics'), evaluation: () => request<Evaluation | null>('/evaluations/latest'),
    settle: async (_id, refund) => { await request('/mock/refunds/' + encodeURIComponent(refund) + '/settle', 'POST'); },
    injectTimeout: async id => { await request(casePath(id) + '/demo/timeout', 'POST'); },
  };
}
export function savings(tickets: number, fraction: number) {
  return { grossRupees: tickets * fraction * (50 - 10), grossHours: tickets * fraction * 6 / 60 };
}


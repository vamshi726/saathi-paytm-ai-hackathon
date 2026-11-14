import type { Approval, Case, Client, Evaluation, Event, Message, Metrics, Session } from './types';
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export function createApi(): Client {
  async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch('/api' + path, {
        method, headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(20000),
      });
    } catch {
      throw new ApiError(0, 'The API could not be reached. Refresh to check the saved case before repeating an action.');
    }
    if (!response.ok) {
      const messages: Record<number, string> = {
        403: 'This action is not available in the local demo.',
        404: 'This record or feature is not available on the connected backend.',
        409: 'The case or approval changed. Refresh and review the current evidence.',
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
    decide: async (a, decision, comment) => { await request('/approvals/' + encodeURIComponent(a.approval_id) + '/decision', 'POST', { decision, payload_hash: a.payload_hash, comment }); },
    metrics: () => request<Metrics>('/metrics'), evaluation: () => request<Evaluation | null>('/evaluations/latest'),
    settle: async (_id, refund) => { await request('/mock/refunds/' + encodeURIComponent(refund) + '/settle', 'POST'); },
    injectTimeout: async id => { await request(casePath(id) + '/demo/timeout', 'POST'); },
    reset: async () => { await request('/demo/reset', 'POST'); },
  };
}
export function savings(tickets: number, fraction: number) {
  return { grossRupees: tickets * fraction * (50 - 10), grossHours: tickets * fraction * 6 / 60 };
}


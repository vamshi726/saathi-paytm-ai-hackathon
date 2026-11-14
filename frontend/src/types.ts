export type Status = 'NEW' | 'NEEDS_CUSTOMER_INFO' | 'INVESTIGATING' | 'NEEDS_APPROVAL' | 'ACTION_RUNNING' | 'PENDING_EXTERNAL' | 'VERIFYING' | 'ESCALATED' | 'RESOLVED';
export interface Case {
  id: string; tenant_id: string; customer_ref: string; order_ref: string | null;
  message: string; goal: string; status: Status; outcome: string | null; synthetic: boolean;
  risk_tier?: 'GREEN' | 'AMBER' | 'RED'; evidence_refs?: string[];
  reflection_revisions?: number; refund_ref?: string; refund_status?: string;
}
export interface Event { sequence: number; case_id: string; actor_id: string; stage: string; detail: string; action_id: string | null; created_at: string }
export interface Message { message_id: string; sender: 'customer' | 'assistant'; text_redacted: string; timestamp: string }
export interface Approval {
  approval_id: string; case_id: string; action_id: string; proposed_action: string;
  source_transaction_ref: string; amount_minor: number; currency: string; reason: string;
  evidence_refs: string[]; decision: 'REQUESTED' | 'APPROVED' | 'REJECTED' | 'EXPIRED';
  expires_at: string; payload_hash: string; reviewer_ref?: string; reviewer_comment?: string;
}
export type Capability = 'run' | 'messages' | 'approvals' | 'settle' | 'inject_timeout' | 'metrics' | 'evaluations' | 'reset';
export interface Session { actor_id: string; tenant_id: string; role: string; mode: string; capabilities: Capability[] }
export interface Metrics { total_cases: number; resolved_cases: number; pending_cases: number; escalated_cases: number; approval_cases: number; synthetic: boolean }
export interface Evaluation {
  run_id: string; mode: string; completed_at: string; executed: number; total: number; correct: number;
  eligible_resolved_without_human: number; eligible_total: number; cases_with_human_touch: number;
  unauthorized_writes: number; duplicate_writes: number; false_closures: number;
  median_first_action_seconds: number | null;
}
export interface Client {
  session(): Promise<Session>; cases(): Promise<Case[]>; detail(id: string): Promise<Case>;
  events(id: string): Promise<Event[]>; run(id: string): Promise<Case>;
  messages(id: string): Promise<Message[]>; send(id: string, text: string): Promise<Case>;
  approvals(): Promise<Approval[]>; decide(a: Approval, decision: 'APPROVED' | 'REJECTED', comment: string): Promise<void>;
  metrics(): Promise<Metrics>; evaluation(): Promise<Evaluation | null>;
  settle(id: string, refund: string): Promise<void>; injectTimeout(id: string): Promise<void>;
  reset(): Promise<void>;
}


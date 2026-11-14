// Explicit browser-only UI rehearsal. Never used as an API error fallback or evaluation evidence.
import type { Approval, Case, Client, Event, Message, Metrics } from './types';
const seed = (): Case[] => [
  ['CS-1042', 'ORD-2042', 'I was charged twice for my ₹1,299 order.', 'duplicate_payment'],
  ['CS-1043', 'ORD-2043', 'I paid ₹899, but my order still says unpaid.', 'order_payment_verified'],
  ['CS-1044', 'ORD-2044', 'Where is my ₹2,450 refund?', 'refund_status'],
  ['CS-1045', 'ORD-2045', 'Refund ₹25,000 to my alternate account.', 'alternate_account'],
  ['CS-1046', null, 'I was charged twice. Refund one payment.', 'clarification'],
  ['RISK-HISTORY-02', 'ORD-2042-H', 'I was charged twice for my ₹1,299 order. History variant.', 'duplicate_payment'],
].map(([id, order_ref, message, goal]) => ({
  id: id!, order_ref, message: message!, goal: goal!, tenant_id: 'preview-merchant',
  customer_ref: 'CUS-' + id, status: 'NEW', outcome: null, synthetic: true,
}));
export function createPreview(storage?: Storage): Client {
  let cases = seed();
  let traces: Record<string, Event[]> = {};
  let chats: Record<string, Message[]> = {};
  let approvals: Approval[] = [];
  let timeout: string[] = [];
  try {
    const raw = storage?.getItem('saathi-ui-preview-v1');
    if (raw) ({ cases, traces, chats, approvals, timeout } = JSON.parse(raw));
  } catch { /* A blocked browser store still permits in-memory rehearsal. */ }
  const save = () => { try { storage?.setItem('saathi-ui-preview-v1', JSON.stringify({ cases, traces, chats, approvals, timeout })); } catch { /* no persistence */ } };
  const copy = <T,>(value: T): T => structuredClone(value);
  const get = (id: string) => { const c = cases.find(c => c.id === id); if (!c) throw new Error('Preview case not found'); return c; };
  const event = (c: Case, stage: string, detail: string) => {
    const list = traces[c.id] ??= [];
    list.push({ sequence: list.length + 1, case_id: c.id, actor_id: 'preview-simulator', stage, detail, action_id: c.id + ':preview', created_at: new Date().toISOString() });
  };
  const reply = (c: Case, text: string) => {
    c.outcome = text;
    (chats[c.id] ??= []).push({ message_id: crypto.randomUUID(), sender: 'assistant', text_redacted: text, timestamp: new Date().toISOString() });
  };
  const expire = () => {
    for (const a of approvals) if (a.decision === 'REQUESTED' && Date.parse(a.expires_at) <= Date.now()) {
      a.decision = 'EXPIRED'; const c = get(a.case_id); c.status = 'ESCALATED';
      event(c, 'approval_expired', 'Preview approval expired; no refund created.');
      reply(c, 'Approval expired. Human review is required.'); save();
    }
  };
  async function run(id: string) {
    expire();
    const c = get(id);
    if (c.status !== 'NEW') return copy(c);
    event(c, 'triage', 'UI rehearsal: deterministic scenario selected; no AI agent execution.');
    if (id === 'CS-1046') {
      c.status = 'NEEDS_CUSTOMER_INFO';
      reply(c, 'Could you share your order ID so I can verify both transactions?');
    } else if (id === 'CS-1045' || id === 'RISK-HISTORY-02') {
      c.status = 'ESCALATED'; c.risk_tier = 'RED';
      c.evidence_refs = id === 'CS-1045' ? ['₹25,000', 'Alternate destination'] : ['RF-H1', 'RF-H2', '2 prior refunds / 30 days'];
      event(c, 'policy_denied', id === 'CS-1045' ? 'High-value alternate-account request blocked.' : 'Two scoped prior refunds trigger enhanced review; history alone is not proof of fraud.');
      reply(c, 'The request needs enhanced human review. No refund has been initiated.');
    } else if (id === 'CS-1042') {
      c.status = 'NEEDS_APPROVAL'; c.risk_tier = 'AMBER'; c.evidence_refs = ['TXN-52A', 'TXN-52B', '0 prior refunds / 30 days'];
      approvals.push({ approval_id: 'APR-1042', case_id: id, action_id: 'ACT-1042-REFUND', proposed_action: 'initiate_mock_refund', source_transaction_ref: 'TXN-52B', amount_minor: 129900, currency: 'INR', reason: 'Two captured payments for one purchase; 0 prior refunds in 30 days.', evidence_refs: ['TXN-52A', 'TXN-52B'], decision: 'REQUESTED', expires_at: new Date(Date.now() + 15 * 60000).toISOString(), payload_hash: 'preview-only-exact-action' });
      event(c, 'approval_requested', 'Exact ₹1,299 refund requires supervisor approval.');
      reply(c, 'A proposed mock refund is awaiting supervisor review. No refund has been initiated.');
    } else if (id === 'CS-1044') {
      c.status = 'PENDING_EXTERNAL'; c.risk_tier = 'GREEN'; c.refund_ref = 'RF-1044'; c.refund_status = 'PROCESSING';
      event(c, 'get_refund_status', 'Preview refund status: PROCESSING.');
      reply(c, 'Your refund is processing. Bank credit has not been verified.');
    } else {
      c.risk_tier = 'GREEN';
      event(c, 'reconcile_order', 'Preview mock order changed to PAID.');
      if (timeout.includes(id)) {
        c.reflection_revisions = 1;
        event(c, 'reflection', 'Injected read-only timeout; one safe verification retry. No write repeated.');
        timeout = timeout.filter(x => x !== id);
      }
      event(c, 'verify_order', 'Preview independent read-back: PAID.');
      c.status = 'RESOLVED'; reply(c, 'Your mock payment is confirmed and your mock order is PAID.');
    }
    save(); return copy(c);
  }
  return {
    session: async () => ({ actor_id: 'preview-supervisor', tenant_id: 'preview-merchant', role: 'supervisor', mode: 'browser-ui-rehearsal', capabilities: ['run', 'messages', 'approvals', 'settle', 'inject_timeout', 'metrics'] }),
    cases: async () => { expire(); return copy(cases); }, detail: async id => { expire(); return copy(get(id)); },
    events: async id => copy(traces[id] ?? []), run, messages: async id => copy(chats[id] ?? []),
    send: async (id, text) => {
      const c = get(id);
      if (c.status !== 'NEEDS_CUSTOMER_INFO') throw new Error('This preview case is not waiting for a reply.');
      (chats[id] ??= []).push({ message_id: crypto.randomUUID(), sender: 'customer', text_redacted: text, timestamp: new Date().toISOString() });
      if (text.trim().toUpperCase() !== 'ORD-2046') {
        reply(c, 'Please share the order ID for this case. For this synthetic rehearsal, use ORD-2046.');
      } else {
        c.order_ref = 'ORD-2046'; c.status = 'RESOLVED'; c.risk_tier = 'GREEN';
        c.evidence_refs = ['TXN-46A: CAPTURED', 'TXN-46B: PENDING_AUTHORIZATION'];
        event(c, 'get_transaction', 'One CAPTURED payment and one PENDING_AUTHORIZATION.');
        event(c, 'verify_payment', 'Two successful charges are not confirmed; no refund requested.');
        reply(c, 'Only one completed charge is confirmed. The second is a pending authorization, so no refund was initiated. Track the pending authorization with your bank.');
      }
      save(); return copy(c);
    },
    approvals: async () => { expire(); return copy(approvals); },
    decide: async (proposal, decision, comment) => {
      expire();
      const a = approvals.find(a => a.approval_id === proposal.approval_id);
      if (!a || a.decision !== 'REQUESTED' || a.payload_hash !== proposal.payload_hash) throw new Error('Approval changed or expired. Refresh the queue.');
      if (!comment.trim()) throw new Error('A supervisor comment is required.');
      a.decision = decision; a.reviewer_ref = 'preview-supervisor'; a.reviewer_comment = comment.trim();
      const c = get(a.case_id);
      if (decision === 'APPROVED') {
        c.refund_ref = 'RF-1042'; c.refund_status = 'INITIATED';
        event(c, 'initiate_mock_refund', 'One preview refund initiated after simulated approval.');
        c.refund_status = 'PROCESSING'; event(c, 'process_mock_refund', 'Preview refund is processing.');
        c.status = 'RESOLVED'; c.refund_status = 'SUCCEEDED'; event(c, 'verify_refund', 'Preview refund completed successfully.');
      } else {
        c.status = 'ESCALATED'; event(c, 'approval_rejected', 'Supervisor rejected the proposal; no refund created.');
        reply(c, 'Refund proposal rejected. Human support will review this case.');
      }
      save();
    },
    metrics: async (): Promise<Metrics> => ({ total_cases: cases.length, resolved_cases: cases.filter(c => c.status === 'RESOLVED').length, pending_cases: cases.filter(c => c.status === 'PENDING_EXTERNAL').length, escalated_cases: cases.filter(c => c.status === 'ESCALATED').length, approval_cases: cases.filter(c => c.status === 'NEEDS_APPROVAL').length, synthetic: true }),
    evaluation: async () => null,
    settle: async (id, refund) => {
      const c = get(id); if (c.status !== 'PENDING_EXTERNAL' || c.refund_ref !== refund) throw new Error('No pending refund to simulate.');
      c.status = 'RESOLVED'; c.refund_status = 'SUCCEEDED';
      event(c, 'verify_refund', 'Simulated settlement event and read-back: SUCCEEDED.');
      reply(c, 'The synthetic refund is marked SUCCEEDED in this UI rehearsal. No real funds moved.'); save();
    },
    injectTimeout: async id => { if (get(id).status !== 'NEW' || id !== 'CS-1043') throw new Error('Use a new CS-1043 preview case.'); timeout = [...new Set([...timeout, id])]; save(); },
    reset: async () => { cases = seed(); traces = {}; chats = {}; approvals = []; timeout = []; save(); },
  };
}


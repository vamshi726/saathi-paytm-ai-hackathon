import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Approval, Case, Client, Evaluation, Event, Message, Metrics, Session } from './types';
import { savings } from './api';

const label = (value: string) => value.toLowerCase().replaceAll('_', ' ');
const money = (minor: number, currency = 'INR') => new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(minor / 100);
export function Badge({ value }: { value: string }) { return <span className={'badge ' + value.toLowerCase()}>{label(value)}</span>; }
function Impact({ evaluation, metrics, preview }: { evaluation: Evaluation | null; metrics: Metrics | null; preview: boolean }) {
  const [fraction, setFraction] = useState(.3);
  const scenario = savings(100000, fraction);
  return <div className="impact-grid">
    <section className="panel"><p className="eyebrow">MEASURED OUTCOMES</p><h2>Outcomes, not just answers.</h2>
      <p>{preview ? 'Browser rehearsal counts — not backend evidence.' : 'Synthetic backend records — not a merchant pilot.'}</p>
      <div className="stats"><div><strong>{metrics?.resolved_cases ?? '—'}</strong><span>Resolved / {metrics?.total_cases ?? '—'} cases</span></div><div><strong>{metrics?.pending_cases ?? '—'}</strong><span>Pending external state</span></div></div>
      <h3>40-case evaluation</h3>{evaluation ? <>
        <p>Run {evaluation.run_id} · {evaluation.mode} · {new Date(evaluation.completed_at).toLocaleString()}</p>
        {evaluation.executed !== 40 || evaluation.total !== 40 ? <p className="notice">Incomplete batch — do not report this as a completed 40-case evaluation.</p> : null}
        <dl><dt>Correct outcomes</dt><dd>{evaluation.correct} / {evaluation.total}</dd>
        <dt>Executed</dt><dd>{evaluation.executed} / {evaluation.total}</dd>
        <dt>Eligible autonomous resolutions</dt><dd>{evaluation.eligible_resolved_without_human} / {evaluation.eligible_total}</dd>
        <dt>Cases with a human touch</dt><dd>{evaluation.cases_with_human_touch} / {evaluation.total}</dd>
        <dt>Unauthorized / duplicate writes</dt><dd>{evaluation.unauthorized_writes} / {evaluation.duplicate_writes}</dd>
        <dt>False closures</dt><dd>{evaluation.false_closures}</dd>
        <dt>Median first verified action</dt><dd>{evaluation.median_first_action_seconds == null ? 'Not measured' : evaluation.median_first_action_seconds + ' seconds'}</dd></dl>
      </> : <div className="empty">Not yet measured. A completed backend batch report is required. Rehearsal activity is never used to fill these values.</div>}
    </section>
    <section className="panel scenario"><p className="eyebrow">ILLUSTRATIVE ASSUMPTIONS</p><h2>What could capacity look like?</h2>
      <p>100,000 tickets / month · ₹50 human handling · ₹10 automated handling · 6 human minutes per fully automated case.</p>
      <label htmlFor="automation">Assumed fully automated share</label>
      <select id="automation" value={fraction} onChange={e => setFraction(Number(e.target.value))}><option value={.3}>30%</option><option value={.45}>45%</option><option value={.6}>60%</option></select>
      <div className="scenario-result">{money(scenario.grossRupees * 100)}<span>gross monthly handling-cost difference</span></div>
      <h3>{scenario.grossHours.toLocaleString('en-IN')} illustrative human-hours freed</h3>
      <p>Tickets × assumed automation × (₹50 − ₹10). Hours = tickets × assumed automation × 6 ÷ 60.</p>
      <p className="fine">Assumptions, not pilot results or net savings. Excludes implementation, QA, oversight, cloud, integrations, escalations and reopened cases.</p>
    </section>
  </div>;
}
function ApprovalCard({ item, enabled, busy, onDecide }: { item: Approval; enabled: boolean; busy: boolean; onDecide: (a: Approval, d: 'APPROVED' | 'REJECTED') => void }) {
  const [confirming, setConfirming] = useState(false);
  const expired = Date.parse(item.expires_at) <= Date.now();
  return <article className="panel approval"><div className="row"><h3>{money(item.amount_minor, item.currency)} mock refund</h3><Badge value={expired && item.decision === 'REQUESTED' ? 'EXPIRED' : item.decision}/></div>
    <p>{item.reason}</p><dl><dt>Case / action</dt><dd>{item.case_id} / {item.action_id}</dd><dt>Source transaction</dt><dd>{item.source_transaction_ref}</dd><dt>Evidence</dt><dd>{item.evidence_refs.join(', ')}</dd><dt>Expires</dt><dd>{new Date(item.expires_at).toLocaleString()}</dd><dt>Reviewer</dt><dd>{item.reviewer_ref ?? 'Awaiting supervisor'}</dd></dl>
    {item.decision === 'REQUESTED' && !expired ? <>
      {!enabled && <p className="notice">A server-verified supervisor role is required to decide.</p>}
      {confirming ? <div className="notice"><p>Approve this exact transaction and amount? The backend must revalidate the approval before executing a mock refund.</p><button disabled={busy || !enabled} onClick={() => { setConfirming(false); onDecide(item, 'APPROVED'); }}>Confirm approval</button><button className="secondary" onClick={() => setConfirming(false)}>Cancel</button></div> :
      <div className="actions"><button disabled={busy || !enabled} onClick={() => setConfirming(true)}>Review approval</button><button className="secondary danger" disabled={busy || !enabled} onClick={() => onDecide(item, 'REJECTED')}>Reject proposal</button></div>}
    </> : null}
  </article>;
}
export function App({ client, preview, onExit }: { client: Client; preview: boolean; onExit: () => void }) {
  const [tab, setTab] = useState('inbox');
  const [session, setSession] = useState<Session | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Case | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('ALL');
  const [draft, setDraft] = useState('');
  const [notice, setNotice] = useState('');
  const generation = useRef(0);
  const lock = useRef(false);
  const errorText = (e: unknown) => e instanceof Error ? e.message : 'Could not load the workspace.';
  const refresh = useCallback(async () => {
    const identity = await client.session();
    const [list, counts, queue, report] = await Promise.all([
      client.cases(), identity.capabilities.includes('metrics') ? client.metrics() : Promise.resolve(null),
      identity.capabilities.includes('approvals') && identity.role === 'supervisor' ? client.approvals() : Promise.resolve([]),
      identity.capabilities.includes('evaluations') ? client.evaluation() : Promise.resolve(null),
    ]);
    setSession(identity); setCases(list); setMetrics(counts); setApprovals(queue); setEvaluation(report);
    setSelected(old => list.some(c => c.id === old) ? old : list[0]?.id ?? null);
    return identity;
  }, [client]);
  useEffect(() => {
    let active = true;
    refresh().catch(e => { if (active) setError(errorText(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; generation.current++; };
  }, [refresh]);
  const loadDetail = useCallback(async (id: string, identity: Session) => {
    const current = ++generation.current;
    setDetailLoading(true);
    try {
      const [c, trace, chat] = await Promise.all([client.detail(id), client.events(id), identity.capabilities.includes('messages') ? client.messages(id) : Promise.resolve([])]);
      if (current === generation.current) { setDetail(c); setEvents(trace); setMessages(chat); }
    } finally { if (current === generation.current) setDetailLoading(false); }
  }, [client]);
  useEffect(() => {
    setDetail(null); setEvents([]); setMessages([]); setDraft('');
    if (selected && session) loadDetail(selected, session).catch(e => setError(errorText(e)));
    return () => { generation.current++; };
  }, [selected, session, loadDetail]);
  async function act(action: () => Promise<unknown>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(''); setNotice('');
    try { await action(); await refresh(); }
    catch (e) { setError(errorText(e)); }
    finally { lock.current = false; setBusy(false); }
  }
  const visible = useMemo(() => cases.filter(c => (filter === 'ALL' || c.status === filter) && [c.id, c.message, c.order_ref, c.status, c.customer_ref].join(' ').toLowerCase().includes(query.toLowerCase())), [cases, filter, query]);
  const can = (cap: Session['capabilities'][number]) => !!session?.capabilities.includes(cap);
  const currentAgent = events.at(-1)?.stage ?? 'Waiting to start';
  return <div className="workspace">
    <aside className="sidebar"><a className="brand" href="#inbox" onClick={() => setTab('inbox')}><span className="brand-mark">s</span>saathi<span className="brand-dot">●</span></a>
      <p className="sidebar-label">MERCHANT WORKSPACE</p>
      <nav aria-label="Main navigation">{[['inbox', '◫', 'Case inbox'], ['approvals', '✓', 'Approvals'], ['impact', '↗', 'Business impact']].map(([key, icon, name]) => <button key={key} className={tab === key ? 'nav-item active' : 'nav-item'} onClick={() => setTab(key)} aria-current={tab === key ? 'page' : undefined}><span>{icon}</span>{name}{key === 'approvals' && approvals.filter(a => a.decision === 'REQUESTED').length > 0 && <b>{approvals.filter(a => a.decision === 'REQUESTED').length}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><span className="live-dot"/> Synthetic data only<p>No Paytm production connection.<br/>No real money movement.</p><button className="secondary" disabled={busy} onClick={onExit}>Disconnect</button></div>
    </aside>
    <main><header className="topbar"><span>Support operations <span className="muted">/ {tab === 'inbox' ? 'Case inbox' : tab === 'impact' ? 'Business impact' : 'Approvals'}</span></span><span className="identity">{session?.actor_id ?? 'Connecting'} · {session?.role ?? '—'}</span></header>
      <div className="content"><div className="page-heading"><div><p className="eyebrow">YOUR PAYMENT SUPPORT TEAMMATE</p><h1>{tab === 'inbox' ? 'Every case. A clear next step.' : tab === 'approvals' ? 'Human judgment, at the right moment.' : 'See what changed.'}</h1><p>Investigate with context. Act with permission. Verify the outcome.</p></div><button className="secondary" disabled={busy || loading} onClick={() => act(async () => {})}>↻ Refresh</button></div>
      <div className={preview ? 'mode-banner preview' : 'mode-banner'}>{preview ? 'UI REHEARSAL · Browser simulation; no backend calls, real agents or evaluation results. Synthetic preview state is saved in this tab.' : 'CONNECTED DEMO · Synthetic backend data. Workflow capabilities come from the server.'}</div>
      {error && <div className="error" role="alert">{error} <button className="secondary" disabled={busy} onClick={() => act(async () => {})}>Retry refresh</button></div>}
      {notice && <div className="notice" role="status">{notice}</div>}
      {loading ? <div className="empty" role="status">Loading your workspace…</div> : <>
      <div className="summary-grid">{[[metrics?.total_cases, 'Total cases'], [metrics?.resolved_cases, 'Verified / resolved'], [metrics?.pending_cases, 'Pending external'], [metrics?.escalated_cases, 'Human review']].map(([count, title]) => <div className="summary" key={title}><span>{title}</span><strong>{count ?? '—'}</strong></div>)}</div>
      {tab === 'impact' ? <Impact evaluation={evaluation} metrics={metrics} preview={preview}/> : tab === 'approvals' ? <div>
        <p className="section-note">Review the exact transaction, amount, evidence and expiry. An approval is not confirmation of settlement.</p>
        {!can('approvals') ? <div className="empty">The connected backend does not yet provide approvals. Switch to UI rehearsal to explore the planned experience.</div> : session?.role !== 'supervisor' ? <div className="empty">Supervisor access is required. Contact your administrator; roles are assigned by the backend.</div> : approvals.length === 0 ? <div className="empty">No approval requests. Run a duplicate-charge case to investigate the evidence first.</div> : approvals.map(a => <ApprovalCard key={a.approval_id + a.decision} item={a} enabled={session?.role === 'supervisor'} busy={busy} onDecide={(a, d) => act(() => client.decide(a, d))}/>)}
      </div> : <div className="case-layout">
        <section className="panel inbox"><div className="inbox-heading"><h2>Cases <span className="muted">{cases.length}</span></h2><label className="sr-only" htmlFor="search">Search cases</label><input id="search" placeholder="Search case, order or customer…" value={query} onChange={e => setQuery(e.target.value)}/><label className="sr-only" htmlFor="status-filter">Filter by status</label><select id="status-filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="ALL">All statuses</option>{Array.from(new Set(cases.map(c => c.status))).map(status => <option key={status}>{status}</option>)}</select></div>
          {visible.length === 0 ? <p className="empty">No matching cases.</p> : visible.map(c => <button disabled={busy} className={'case-card ' + (selected === c.id ? 'selected' : '')} key={c.id} onClick={() => setSelected(c.id)} aria-pressed={selected === c.id}><div className="row"><b>{c.id}</b><span className="case-arrow">↗</span></div><p>{c.message}</p><Badge value={c.status}/><small>{c.order_ref ?? 'Order ID needed'}</small></button>)}
        </section>
        <div className="case-detail">{detailLoading || !detail ? <div className="panel empty">{selected ? 'Loading case evidence…' : 'Select a case to begin.'}</div> : <>
          <section className="panel"><div className="row"><div><p className="eyebrow">CASE OVERVIEW</p><h2>{detail.id}</h2></div><Badge value={detail.status}/></div>
            <p>{detail.message}</p><div className="metadata"><span>Order <b>{detail.order_ref ?? 'Not provided'}</b></span><span>Risk <b>{detail.risk_tier ?? 'Not supplied'}</b></span><span>Revisions <b>{detail.reflection_revisions ?? 'Not supplied'} / 3</b></span></div>
            {detail.evidence_refs?.length ? <div className="evidence"><b>Risk & payment evidence</b><p>{detail.evidence_refs.join(' · ')}</p></div> : null}
            {detail.refund_status && <p>Refund: <Badge value={detail.refund_status}/> <span className="fine">Initiated / processing does not mean bank credit.</span></p>}
            {detail.outcome && <div className="outcome" role="status">{detail.outcome}</div>}
            <div className="actions"><button disabled={busy || !can('run') || detail.status !== 'NEW'} onClick={() => act(() => client.run(detail.id))}>{busy ? 'Working…' : 'Run investigation'} <span>↗</span></button>{detail.status === 'NEEDS_APPROVAL' && <button className="secondary" onClick={() => setTab('approvals')}>Review approval queue</button>}</div>
          </section>
          <section className="panel"><div className="row"><h2>Conversation</h2><span className="fine">Case-linked context</span></div><div className="chat" aria-live="polite"><div className="bubble customer"><small>Customer</small>{detail.message}</div>{messages.map(m => <div className={'bubble ' + m.sender} key={m.message_id}><small>{m.sender === 'customer' ? 'Customer' : 'Saathi'}</small>{m.text_redacted}</div>)}{!messages.length && detail.outcome && <div className="bubble assistant"><small>Saathi · saved outcome</small>{detail.outcome}</div>}</div>
            <form className="chat-form" onSubmit={e => { e.preventDefault(); const text = draft.trim(); if (text) void act(async () => { await client.send(detail.id, text); setDraft(''); }); }}><label className="sr-only" htmlFor="reply">Customer reply</label><input id="reply" value={draft} maxLength={2000} onChange={e => setDraft(e.target.value)} placeholder={can('messages') ? 'Reply with the requested details…' : 'Chat endpoint not yet available'} disabled={busy || !can('messages') || detail.status !== 'NEEDS_CUSTOMER_INFO'}/><button disabled={busy || !draft.trim() || !can('messages') || detail.status !== 'NEEDS_CUSTOMER_INFO'}>Send</button></form>
            <p className="fine">{detail.status === 'NEEDS_CUSTOMER_INFO' ? 'Waiting for customer context. No financial action should run before evidence is available.' : 'Replies open when the workflow asks for clarification.'}</p>
          </section>
          <section className="panel"><div className="row"><h2>Activity & evidence</h2><span className="fine">{preview ? 'Simulated trace' : 'Backend audit'}</span></div><p className="fine">Latest stage: {label(currentAgent)}. Agent identity is shown only when supplied by the backend.</p>
            {events.length ? <ol className="timeline">{events.map(event => <li key={event.sequence}><div className="row"><b>{label(event.stage)}</b><time>{new Date(event.created_at).toLocaleTimeString()}</time></div><p>{event.detail}</p><small>{event.actor_id}{event.action_id ? ' · ' + event.action_id : ''}</small></li>)}</ol> : <div className="empty">No recorded steps yet. Start the investigation to see the evidence.</div>}
          </section>
          {(can('settle') || can('inject_timeout')) && <details className="panel"><summary>Demo operator controls · simulation only</summary><p>No real funds move. These controls are separate from normal support actions.</p><div className="actions">
            {can('inject_timeout') && <button className="secondary" disabled={busy || detail.status !== 'NEW' || detail.id !== 'CS-1043'} onClick={() => act(async () => { await client.injectTimeout(detail.id); setNotice('One read-only timeout is armed for the next CS-1043 run.'); })}>Inject verification timeout</button>}
            {can('settle') && <button className="secondary" disabled={busy || detail.status !== 'PENDING_EXTERNAL' || !detail.refund_ref} onClick={() => act(() => client.settle(detail.id, detail.refund_ref!))}>Simulate refund settlement</button>}
          </div></details>}
        </>}</div>
      </div>}</>}
      <footer>Saathi / PromptPioneers <span>Built for accountable support.</span></footer>
    </div></main>
  </div>;
}



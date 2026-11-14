# Sai Teja — frontend handoff

## Delivered
React, TypeScript, Tailwind and Vite application in frontend:
- Responsive case inbox with search/status filter and API-backed detail.
- Saved outcome, audit timeline, evidence references, refund state and revision count.
- Clarification composer bound to the selected case and NEEDS_CUSTOMER_INFO.
- Supervisor approval queue with exact transaction/amount, evidence, expiry,
  reviewer, confirmation, rejection and stale-state errors.
- Loading, empty, denied, disconnected, pending and escalation states.
- Record counts, evaluation summary contract, and separately labeled economic assumptions.
- Optional Clerk sign-in and bearer session-token transport.
- Explicit browser-only rehearsal with five primary cases and RISK-HISTORY-02.
- Read-only /api/session and /api/metrics extensions to the existing backend.

No financial policy or workflow authorization was changed. Do not infer
backend completion from the browser rehearsal.

## Connected backend vs integration dependencies

The current backend seeds only CS-1043 and implements deterministic reconciliation.
The live UI connects this existing workflow end-to-end. It advertises only run
and metrics capabilities. Approval, message, refund controls and evaluation stay
unavailable until their backend contracts are implemented by the responsible owners.
Actual three-agent identity, reflection and history evidence must come from those
backend owners; the UI never fabricates these fields in connected mode.

Clerk frontend support is implemented, but the current API verifies only its
local demo token. Set VITE_CLERK_PUBLISHABLE_KEY in frontend/.env.local only when
testing Clerk sign-in. Clerk-authenticated API access remains blocked until
server-side JWT verification, tenant mapping and role checks are implemented.
Never infer supervisor permission from a browser selector or Clerk sign-in alone.
No real Clerk credentials were available for an end-to-end sign-in test.

## API integration contract

Existing Case and Event fields are preserved in src/types.ts.
GET /api/session returns actor_id, tenant_id, role, mode and capabilities.
The frontend trusts capabilities for presentation only; every backend endpoint
must independently enforce identity, role and tenant scope.

Future contracts (not implemented on the current backend):
- GET /api/cases/{id}/messages -> Message[] (message_id, sender,
  text_redacted, timestamp).
- POST /api/cases/{id}/messages with {text} -> updated Case; checkpoint-safe resume.
- GET /api/approvals -> Approval[] (see src/types.ts for exact fields).
- POST /api/approvals/{id}/decision with {decision: APPROVED|REJECTED,
  payload_hash} -> JSON or 204. Reviewer comes from authenticated server identity.
  Backend handles expiry, exact-action validation, RED blocks and idempotency.
- POST /api/mock/refunds/{refund_ref}/settle -> JSON or 204; demo operator only.
- POST /api/cases/{id}/demo/timeout -> JSON or 204; demo operator only.
- GET /api/evaluations/latest -> Evaluation or null (exact fields in src/types.ts).
  Return a completed run only. Keep failed/unscored cases in total denominator.

Optional Case fields: risk_tier, evidence_refs, reflection_revisions,
refund_ref, refund_status. order_ref may be null. Missing facts display as
not supplied. A pending refund is never counted as resolved by the frontend.

GET /api/metrics computes tenant-scoped case counts from persisted records.
These counts are not a 40-case batch evaluation, financial savings or agent accuracy.
The UI does not automatically retry writes, including timeout outcomes; refresh
saved state first. Production hosting needs same-origin /api routing; Vite's
local proxy is not a production API proxy.

## Rehearsal script

Select Open UI rehearsal on the connection screen. This is clearly labeled UI
simulation, not backend agent execution. Synthetic state is saved in this tab's
sessionStorage. Close the tab to reset. No credentials are stored there.

1. CS-1046: run; supply an unusable ID, then ORD-2046. Inspect the same-case
   conversation and captured-vs-pending evidence; no refund.
2. CS-1043: optionally arm Inject verification timeout, then run. Inspect one
   revision, one order update and verified resolution.
3. CS-1042: run; open approvals, inspect exact transaction/amount, review and
   confirm. Refund remains INITIATED / PENDING_EXTERNAL. Refresh preserves it.
4. CS-1044: run; status is PROCESSING. Expand demo controls and explicitly
   simulate settlement to observe SUCCEEDED and resolved.
5. CS-1045 and RISK-HISTORY-02: run; inspect RED reasons and escalation.
   Neither creates an ordinary approval or refund.
6. Business impact: evaluation remains not measured; use 30/45/60 percent
   assumptions to show ₹12/18/24 lakh gross differences, clearly illustrative.

Approval rejection escalates without a refund; preview approvals expire after
15 minutes and are reconciled when the view refreshes. The simulator is not a
security implementation or evidence of a passing backend safety test.

## Validation
npm test covers user clarification, failed API actions, confirmed approval,
pending status, expiry, repeat protection, rehearsal persistence and impact labels.
npm run build typechecks and builds the production bundle.
Backend tests cover authenticated, scoped session/metrics and preserve the
existing reconciliation safety suite.

## Remaining team work
Backend messages/checkpoint resume, durable approvals, refund/history policy,
40-case batch report, verified Clerk identity and real agent traces are integration
dependencies. A configured Clerk account and the missing backend workflows are needed
before declaring those end-to-end flows ready.


## Verified in this workspace
- Backend: 16 pytest tests passed; Ruff passed.
- Frontend: 9 Vitest tests passed; TypeScript + Vite production build passed.
- Chromium: 2 Playwright tests passed, including the real UI-to-FastAPI-to-SQLite
  reconciliation and mobile clarification/reload. Desktop and mobile screenshots
  reviewed in .runtime/saathi-connected.png and .runtime/saathi-mobile.png.
- npm audit: zero reported vulnerabilities after updating Vitest to 4.1.12.
- No live Clerk account was configured, and no 40-case backend evaluation was run.

Browser tests use a new ignored SQLite database and test-only token; they start
and stop their own API on port 8000 and frontend on 5179. Stop existing servers
on those ports first. They do not reset the normal demo database.

On this Windows checkout, Python .venv and portable Node are already installed.
To run the frontend from the repository root:

```powershell
$env:PATH = (Resolve-Path '.runtime/node-v22.23.5-win-x64').Path + ';' + $env:PATH
npm --prefix frontend run dev
```

For backend development without uv:

```powershell
$env:SAATHI_DEMO_TOKEN = 'choose-your-own-local-token'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

For repeatable browser checks after normal dependency installation:

```powershell
cd frontend
npx playwright install chromium
npm run test:e2e
```

The Playwright configuration uses the Windows .venv executable; on other
platforms adapt that path to .venv/bin/python.

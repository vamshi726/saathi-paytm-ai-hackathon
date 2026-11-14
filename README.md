# Saathi

Synthetic payment-support demo. The first feature is **CS-1043: captured payment /
unpaid order**. The API checks ownership, amount, currency and payment status,
reconciles the mock INR 899 order, and reads it back before resolving the case.
Conflicting or ineligible evidence escalates. No Paytm connection or money movement.

## Run locally

Install Python 3.12+ and [uv](https://docs.astral.sh/uv/). From this directory:

```powershell
uv sync --locked
$env:SAATHI_DEMO_TOKEN = 'your-local-demo-token'
uv run uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs and **Authorize** with your token, or use PowerShell:

```powershell
$headers = @{ Authorization = "Bearer $env:SAATHI_DEMO_TOKEN" }
Invoke-RestMethod http://127.0.0.1:8000/api/cases -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/api/cases/CS-1043/run -Method Post -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/api/cases/CS-1043/events -Headers $headers
```

Expect `RESOLVED`, with `reconcile_order`, `verify_order` and `resolved` events.
Repeated runs return the saved result without repeating the update. Search using
`GET /api/cases?q=unpaid`. API schemas are available at `/openapi.json`.

SQLite persists data at `.data/saathi.sqlite3`; startup does not reset records.
For a fresh demo, stop the server and set `SAATHI_DB_PATH` to a new file path.
`.env.example` documents variables; set them in your shell (no automatic loading).

## Validation

```powershell
uv run pytest -q
uv run ruff check .
```

Tests cover verified closure, invalid evidence, authorization, tenant isolation,
concurrent execution, restart persistence, failed verification and rollback.

## Current boundaries

- Deterministic workflow; LangGraph and OpenAI agents are not implemented yet.
- SQLite is a local bootstrap choice; PostgreSQL and graph checkpoints remain
  planned. Local mock updates and audit entries commit atomically. This rollback
  strategy must not be used for remote financial writes.
- A configured demo token maps to one server-defined support identity and tenant.
  This is local mock authentication, not Clerk or production authentication.
- Audit events contain fixed descriptions and synthetic references, not tokens.
- Only CS-1043 is seeded. Backend refunds, approvals, multi-turn chat, reflection,
  and the 40-case evaluation remain planned in [plan.md](plan.md).

## Sai Teja's frontend

React + TypeScript + Tailwind workspace is in `frontend`.
Install Node.js 22.12+ and run in a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Start the API with the instructions above and enter
your local demo token in the connection screen. Vite proxies /api to port 8000.
Tokens stay in memory, not localStorage, source files or VITE_ variables.
The connected workspace runs CS-1043, displays persisted audit events, searches
cases, and reports tenant-scoped counts. Refresh retrieves backend state.

**UI rehearsal** is a separately selected, browser-only simulator for five
primary cases and RISK-HISTORY-02. It exercises clarification (reply ORD-2046),
approval/rejection/expiry, pending refund, simulated settlement and a verification
timeout. It does not run agents or produce evaluation evidence. Its synthetic
state persists in sessionStorage for this tab; close the tab to start fresh.
No fallback to rehearsal occurs on an API failure.

```powershell
cd frontend
npm test
npm run build
```

See [frontend handoff](docs/frontend-handoff.md) for scenario walkthroughs,
backend contracts, Clerk configuration and remaining integration dependencies.

On this checkout, portable Node is available without a system install:

```powershell
# From the repository root
$env:PATH = (Resolve-Path '.runtime/node-v22.23.5-win-x64').Path + ';' + $env:PATH
npm --prefix frontend run dev
```

Validation completed: 16 backend tests, 9 frontend tests and 2 Chromium tests
passed; production build and backend lint passed. Browser checks cover actual
CS-1043 API reconciliation and mobile rehearsal/reload.

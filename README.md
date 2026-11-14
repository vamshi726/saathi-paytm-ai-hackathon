# Saathi

Synthetic payment-support workspace for the Paytm Build for India hackathon.
It ships five safe, persisted demo workflows: verified order reconciliation,
duplicate-payment approval, refund tracking, high-risk escalation and
multi-turn clarification, plus a refund-history risk variant. No Paytm
connection or real money movement exists in this project.

## Run locally

Install Python 3.12+ and [uv](https://docs.astral.sh/uv/). From this directory:

```powershell
uv sync --locked
uv run uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs, or use PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/cases
Invoke-RestMethod http://127.0.0.1:8000/api/cases/CS-1043/run -Method Post
Invoke-RestMethod http://127.0.0.1:8000/api/cases/CS-1043/events
```

For the full demo use a fresh database path if you previously ran the old
single-case build. `CS-1043` resolves only after independent read-back;
`CS-1042` creates an exact approval request and a supervisor may initiate one
mock refund; `CS-1046` requests `ORD-2046` as a follow-up. Repeated actions are
persisted and do not duplicate the reconciliation/refund. Search using
`GET /api/cases?q=unpaid`. API schemas are available at `/openapi.json`.

SQLite persists data at `.data/saathi.sqlite3`; startup does not reset records.
For a fresh demo, stop the server and set `DB_PATH` to a new SQLite file path.
`.env.example` documents variables; set them in your shell (no automatic loading).

Other Python modules can reuse the SQLite connection:

```python
from app.database import get_connection

with get_connection() as db:
    rows = db.execute("SELECT * FROM records").fetchall()
```

Use `Store.connect(write=True)` for application writes because it provides the
transaction and rollback boundary used by cases, approvals, messages and events.

## Validation

```powershell
uv run pytest -q
uv run ruff check .
```

Tests cover verified closure, invalid evidence, tenant isolation,
concurrent execution, restart persistence, failed verification and rollback.

## AI and safety boundaries

- The workflow is deterministic and auditable by default. Set
  `OPENAI_API_KEY` and optionally `OPENAI_MODEL=gpt-5-mini` to request a short
  GPT advisory triage note. It can never authorize or execute a payment action.
- This MVP models the three responsibilities (context, payment resolution and
  verification) as persisted workflow stages; it does not claim a production
  LangGraph deployment.
- SQLite is a local bootstrap choice; PostgreSQL and graph checkpoints remain
  future work. Local mock updates and audit entries commit atomically. This
  rollback strategy must not be used for remote financial writes.
- This is an open local demo with one fixed supervisor identity. It must not be
  deployed or connected to production data without real authentication.
- Audit events contain fixed descriptions and synthetic references.
- The 40-case batch evaluator is still not implemented; the impact screen does
  not invent results when no evaluated report exists.

## Sai Teja's frontend

React + TypeScript + Tailwind workspace is in `frontend`.
Install Node.js 22.12+ and run in a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173 and select **Open local workspace**. Vite proxies
`/api` to port 8000; no sign-in or bearer token is required for this local demo.
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
backend contracts and remaining integration dependencies.

On this checkout, portable Node is available without a system install:

```powershell
# From the repository root
$env:PATH = (Resolve-Path '.runtime/node-v22.23.5-win-x64').Path + ';' + $env:PATH
npm --prefix frontend run dev
```

Validation completed: 16 backend tests, 9 frontend tests and 2 Chromium tests
passed; production build and backend lint passed. Browser checks cover actual
CS-1043 API reconciliation and mobile rehearsal/reload.

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
- Only CS-1043 is seeded. Refunds, approvals, multi-turn chat, React, reflection,
  and the 40-case evaluation remain planned in [plan.md](plan.md).

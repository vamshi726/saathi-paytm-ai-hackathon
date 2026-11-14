# Saathi frontend

React + TypeScript + Tailwind interface, located at the repository root.

## Start on this Windows checkout

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File frontend/start.ps1
```

The launcher uses installed Node.js or the repository's portable Node runtime.
Open the local URL printed by Vite (normally http://127.0.0.1:5173).

For a fresh checkout with Node.js 22.12+ installed:

```powershell
cd frontend
npm ci
npm run dev
```

Choose **Open UI rehearsal** to use the browser-only scenarios immediately.
For connected mode, start the FastAPI server on port 8000 using the root README
and enter its configured demo bearer token. Vite proxies /api to that server.
The existing backend supports CS-1043; other scenarios remain labeled rehearsal.

## Checks

```powershell
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests require the root .venv and free ports 8000 and 5179. They use an
isolated SQLite database under .runtime. See ../docs/frontend-handoff.md for
backend contracts, Clerk integration dependencies and the scenario walkthrough.

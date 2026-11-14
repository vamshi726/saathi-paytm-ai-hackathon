import { defineConfig } from '@playwright/test';
import path from 'node:path';
export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0,
  use: { baseURL: 'http://127.0.0.1:5179', headless: true },
  webServer: [
    { command: '"' + path.resolve('../.venv/Scripts/python.exe') + '" -m uvicorn app.main:app --app-dir ../apps/api --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/health', reuseExistingServer: false,
      env: { DB_PATH: path.resolve('../.runtime/ui-smoke-' + Date.now() + '.sqlite3') } },
    { command: 'npm run dev -- --port 5179 --strictPort', url: 'http://127.0.0.1:5179', reuseExistingServer: false },
  ],
});


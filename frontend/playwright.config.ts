import { defineConfig } from '@playwright/test';

const frontend = 'http://127.0.0.1:5173';
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  use: {
    baseURL: frontend,
    channel: process.env.PLAYWRIGHT_CHANNEL,
    trace: 'retain-on-failure',
    viewport: { width: 1380, height: 940 },
  },
  webServer: [
    {
      command: './run_backend.sh',
      cwd: '..',
      url: 'http://127.0.0.1:8000/api/ready',
      timeout: 90_000,
      reuseExistingServer: false,
      env: { HF_HUB_OFFLINE: '1', GEMINI_API_KEY: '', GOOGLE_API_KEY: '' },
    },
    { command: 'npm run dev -- --host 127.0.0.1 --strictPort', url: frontend, reuseExistingServer: false },
  ],
});

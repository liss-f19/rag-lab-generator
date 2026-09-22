/**
 * Role:   Playwright configuration of the end-to-end QA suite.
 * Input:  A Vite dev server already running on PW_BASE_URL (default http://localhost:5181)
 *         and proxying /api to the FastAPI backend.
 * Output: A single chromium project writing screenshots, traces and the html report under
 *         web/tests/e2e/.
 * Flow:   Points baseURL at the dev server, keeps the suite serial so the shared backend is
 *         never hammered by parallel agent turns, and captures a trace and a screenshot for
 *         every failure so a regression can be read without re-running the suite.
 */
import { defineConfig, devices } from '@playwright/test'

const BASE_URL = process.env.PW_BASE_URL ?? 'http://localhost:5181'

export default defineConfig({
  testDir: './tests/e2e',
  // traces and failure shots land in a gitignored path so they never reach the lint gate
  outputDir: './playwright.local/artifacts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: [['list'], ['html', { outputFolder: './playwright.local/report', open: 'never' }]],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1280, height: 800 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})

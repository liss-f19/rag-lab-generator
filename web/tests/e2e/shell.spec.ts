/**
 * Role:   End-to-end checks of the application shell: routing, health badge and the eval page.
 * Input:  The running Vite dev server and the FastAPI backend behind its /api proxy.
 * Output: Assertions plus the shell screenshots used in the QA report.
 * Flow:   Loads the app, proves the redirect to /chat and the provider badges coming from
 *         /api/health, walks every navigation entry asserting each page renders and the tree
 *         survives the route change, and finally checks the eval table or empty state.
 */
import { expect, test } from '@playwright/test'

import { expectClean, shot, watchConsole, waitForBackend } from './helpers'

test('the app loads and redirects to the chat page', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/')
  await expect(page).toHaveURL(/\/chat$/)
  await expect(page.getByText('SOP Lab Assistant')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Chat', exact: true })).toBeVisible()
  await shot(page, '01-app-shell')
  expectClean(guard)
})

test('the health badge shows the provider names from the backend', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/status')
  await waitForBackend(page)
  // the badges mirror /api/health: fake providers are what the QA backend runs with
  await expect(page.getByText('llm:fake')).toBeVisible()
  await expect(page.getByText('emb:fake')).toBeVisible()
  await expect(page.getByText('rag:vector')).toBeVisible()
  await expect(page.getByText('db:up')).toBeVisible()
  await expect(page.getByText('corpus:ready')).toBeVisible()
  await expect(page.getByText('agent:ready')).toBeVisible()
  await shot(page, '02-status-health')
  expectClean(guard)
})

test('leaving the chat route keeps the application mounted', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/chat')
  await page.waitForTimeout(1500)
  await page.getByRole('link', { name: 'Corpus', exact: true }).click()
  await expect(page).toHaveURL(/\/corpus$/)
  // a crash in an effect cleanup unmounts the whole tree and leaves an empty #root
  await expect(page.locator('#root')).not.toBeEmpty()
  await expect(page.getByText('SOP Lab Assistant')).toBeVisible()
  expectClean(guard)
})

test('every navigation entry opens its page', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/corpus')
  await waitForBackend(page)
  for (const label of ['Retrieval Lab', 'Graph', 'Eval', 'Status', 'Corpus']) {
    await page.getByRole('link', { name: label, exact: true }).click()
    await expect(page.locator('main')).toBeVisible()
    await expect(page.locator('#root')).not.toBeEmpty()
    await page.waitForTimeout(600)
  }
  expectClean(guard)
})

test('the eval page shows either a run table or the empty state', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/eval')
  await waitForBackend(page)
  const table = page.locator('table')
  const empty = page.getByText('No evaluation runs yet')
  await expect(table.or(empty).first()).toBeVisible({ timeout: 30_000 })
  if (await table.count()) {
    await expect(page.getByText('Benchmark runs')).toBeVisible()
    expect(await page.locator('tbody tr').count()).toBeGreaterThan(0)
  }
  await shot(page, '08-eval')
  expectClean(guard)
})

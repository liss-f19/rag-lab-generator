/**
 * Role:   Shared helpers of the end-to-end suite: console guarding and screenshots.
 * Input:  A Playwright Page and the name a screenshot should get.
 * Output: A collector of browser-side problems, and png files under tests/e2e/screenshots.
 * Flow:   watchConsole() subscribes to console and pageerror and keeps every genuine problem,
 *         filtering the noise a dev server produces; shot() writes a small png next to the
 *         report; expectClean() fails the test with the collected messages.
 */
import { expect, type Page } from '@playwright/test'

export const SCREENSHOT_DIR = 'tests/e2e/screenshots'

// Messages a Vite dev server or a third-party lib emits that say nothing about the app.
const IGNORED = [
  /Download the React DevTools/i,
  /\[vite\]/i,
  /React Router Future Flag/i,
  /favicon\.ico/i,
  /Failed to load resource:.*favicon/i,
]

export interface ConsoleGuard {
  problems: string[]
}

export function watchConsole(page: Page): ConsoleGuard {
  const guard: ConsoleGuard = { problems: [] }
  const keep = (message: string) => {
    if (!IGNORED.some((pattern) => pattern.test(message))) guard.problems.push(message)
  }
  page.on('console', (message) => {
    if (message.type() === 'error') keep(`console.error: ${message.text()}`)
  })
  page.on('pageerror', (error) => keep(`pageerror: ${error.message}`))
  return guard
}

export function expectClean(guard: ConsoleGuard): void {
  expect(guard.problems, `browser reported problems:\n${guard.problems.join('\n')}`).toEqual([])
}

export async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: `${SCREENSHOT_DIR}/${name}.png`, scale: 'css' })
}

/** Wait until the health badge proves the backend answered, so no page races the first query. */
export async function waitForBackend(page: Page): Promise<void> {
  await expect(page.getByText(/^llm:/)).toBeVisible({ timeout: 30_000 })
}

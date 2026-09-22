/**
 * Role:   End-to-end checks of the corpus browser and the lab detail page.
 * Input:  /api/courses and /api/labs/sop1/l1_filesystem through the dev-server proxy.
 * Output: Assertions on the lab grid and on every tab of the lab page, plus screenshots.
 * Flow:   Counts the lab cards of both courses, opens sop1/l1_filesystem, and walks the
 *         Tutorial, Tasks, Files and Summary tabs asserting each renders real content; the
 *         Files tab additionally opens a .c attachment and proves the /files route served it.
 */
import { expect, test } from '@playwright/test'

import { expectClean, shot, watchConsole, waitForBackend } from './helpers'

const EXPECTED_LABS = 12

test('the corpus page lists both courses and twelve labs', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/corpus')
  await waitForBackend(page)
  // the panel heading reads "SOP1" plus the lab-count badge, so match on the heading role
  await expect(page.getByRole('heading', { name: /SOP1/ })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('heading', { name: /SOP2/ })).toBeVisible()
  const cards = page.locator('a[href^="/corpus/sop"]')
  await expect(cards.first()).toBeVisible()
  expect(await cards.count()).toBe(EXPECTED_LABS)
  await expect(page.getByText('Filesystem').first()).toBeVisible()
  await shot(page, '03-corpus-list')
  expectClean(guard)
})

test('a lab opens with its tutorial, tasks, files and summary', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/corpus/sop1/l1_filesystem')
  await waitForBackend(page)

  // tutorial is the default tab
  await expect(page.getByRole('button', { name: /^Tutorial$/ })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('article').first()).toBeVisible()
  expect(await page.locator('article').count()).toBeGreaterThan(3)
  await expect(page.getByText('readdir').first()).toBeVisible()
  await shot(page, '04-lab-tutorial')

  // tasks
  await page.getByRole('button', { name: /^Tasks \(\d+\)$/ }).click()
  await expect(page.locator('article').first()).toBeVisible()
  expect(await page.locator('article').count()).toBeGreaterThan(0)
  await expect(page.getByText('example1').first()).toBeVisible()
  // stage numbers of a task are rendered as an ordered list
  await expect(page.locator('ol li').first()).toBeVisible()
  await shot(page, '05-lab-tasks')

  // files: open a .c attachment and prove the preview points at the /files route
  await page.getByRole('button', { name: /^Files \(\d+\)$/ }).click()
  const cFile = page.getByRole('button', { name: /\.c$/ }).first()
  await expect(cFile).toBeVisible()
  const name = (await cFile.textContent())?.trim() ?? ''
  await cFile.click()
  const frame = page.locator('iframe').first()
  await expect(frame).toBeVisible()
  const src = await frame.getAttribute('src')
  expect(src).toContain('/api/labs/sop1/l1_filesystem/files/')
  expect(src).toContain(name.split('/').pop() ?? '')
  const served = await page.request.get(src ?? '')
  expect(served.status()).toBe(200)
  expect(await served.text()).toContain('#include')
  await shot(page, '06-lab-files')

  // summary
  await page.getByRole('button', { name: /^Summary$/ }).click()
  await expect(page.locator('main')).toContainText(/\w{20,}/)
  expectClean(guard)
})

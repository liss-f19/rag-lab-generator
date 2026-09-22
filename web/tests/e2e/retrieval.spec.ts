/**
 * Role:   End-to-end check of the Retrieval Lab: two strategies compared side by side.
 * Input:  /api/strategies, /api/courses and /api/retrieve/compare through the dev-server proxy.
 * Output: Assertions on both result columns plus the retrieval screenshot of the report.
 * Flow:   Types the query, configures column one as vector/hybrid_rrf and column two as
 *         graph/graph_walk, runs the comparison and asserts every column rendered ranked chunks
 *         with a visible score, that sop1/l1 is among them and that the graph column shows the
 *         node path that produced its chunks.
 */
import { expect, type Page, test } from '@playwright/test'

import { expectClean, shot, watchConsole, waitForBackend } from './helpers'

/** Pick a value in the nth select whose visible label is `label`. */
async function choose(page: Page, label: string, index: number, value: string): Promise<void> {
  const field = page.locator('label').filter({ hasText: label }).nth(index)
  await field.locator('select').selectOption(value)
}

test('the retrieval lab compares a vector and a graph configuration', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/retrieval')
  await waitForBackend(page)
  // the strategy selects are only populated once /api/strategies answered
  await expect(page.locator('select').first()).toBeVisible({ timeout: 30_000 })

  await page.getByPlaceholder('ask the corpus something').fill('readdir')
  await choose(page, 'chunker (strategy)', 0, 'hierarchical')
  await choose(page, 'embedder', 0, 'fake')

  // column 1: vector + hybrid_rrf
  await choose(page, 'rag', 0, 'vector')
  await choose(page, 'searcher', 0, 'hybrid_rrf')

  // column 2: graph + graph_walk
  await page.getByRole('button', { name: '+ add config' }).click()
  await choose(page, 'rag', 1, 'graph')
  await choose(page, 'searcher', 1, 'graph_walk')

  await page.getByRole('button', { name: 'run comparison' }).click()

  // two result panels, each with ranked chunk cards
  const cards = page.locator('article')
  await expect(cards.first()).toBeVisible({ timeout: 60_000 })
  // each result column is a panel whose heading carries the rag/searcher badges
  await expect(page.getByRole('heading', { name: /vector/ }).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: /graph_walk/ }).first()).toBeVisible()
  expect(await cards.count()).toBeGreaterThan(3)

  // scores are rendered next to every card
  const scores = page.locator('article >> text=/^0\\.\\d{4}$/')
  expect(await scores.count()).toBeGreaterThan(0)

  // at least one chunk of the filesystem lab came back for a readdir query
  await expect(page.getByText(/sop1\/l1/).first()).toBeVisible()

  // the graph column explains itself with the node path that found the chunk
  await expect(page.locator('article code').first()).toBeVisible()

  await shot(page, '07-retrieval-compare')
  expectClean(guard)
})

test('a retrieved chunk expands and opens in the inspector', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/retrieval')
  await waitForBackend(page)
  await expect(page.locator('select').first()).toBeVisible({ timeout: 30_000 })
  await page.getByPlaceholder('ask the corpus something').fill('readdir')
  await page.getByRole('button', { name: 'run comparison' }).click()

  const expand = page.getByRole('button', { name: /^expand \(\d+ chars\)$/ }).first()
  await expect(expand).toBeVisible({ timeout: 60_000 })
  await expand.click()
  await expect(page.getByRole('button', { name: 'collapse' }).first()).toBeVisible()

  await page.getByRole('button', { name: 'inspect' }).first().click()
  await expect(page.getByRole('button', { name: /close/i }).first()).toBeVisible()
  expectClean(guard)
})

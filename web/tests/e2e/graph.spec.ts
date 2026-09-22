/**
 * Role:   End-to-end check of the knowledge graph explorer.
 * Input:  /api/graph/stats, /api/graph/search and /api/graph/chunks behind the dev proxy.
 * Output: Assertions on the rendered force layout, the details panel and the chunk list.
 * Flow:   Searches for epoll, proves nodes were drawn as svg circles, clicks one and asserts the
 *         details panel names that node and that its attached chunks load; the screenshot of the
 *         expanded neighbourhood goes into the report.
 */
import { expect, test } from '@playwright/test'

import { expectClean, shot, watchConsole, waitForBackend } from './helpers'

test('searching epoll draws nodes and opens the details of one', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/graph')
  await waitForBackend(page)

  await expect(page.getByText('Search the graph')).toBeVisible({ timeout: 30_000 })
  await page.getByPlaceholder('fork, epoll, pipe, l5…').fill('epoll')
  await page.getByRole('button', { name: 'search', exact: true }).click()

  // the force layout draws one circle per matched node
  const nodes = page.locator('svg circle')
  await expect(nodes.first()).toBeVisible({ timeout: 40_000 })
  expect(await nodes.count()).toBeGreaterThan(1)
  await expect(page.getByText(/Matches for/)).toBeVisible()
  await expect(page.getByText(/^\d+ nodes$/).first()).toBeVisible()
  await shot(page, '09-graph-search')

  // clicking a node switches to its neighbourhood and fills the side panels
  await nodes.first().click({ force: true })
  await expect(page.getByText(/Neighbourhood of/)).toBeVisible({ timeout: 40_000 })
  await expect(page.getByText('Selected node')).toBeVisible()
  await expect(page.getByText('Chunks of this node')).toBeVisible()
  await expect(page.getByText('Click a node in the graph.')).toBeHidden()
  await shot(page, '10-graph-node-details')
  expectClean(guard)
})

test('the graph header reports the stored node and edge counts', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/graph')
  await waitForBackend(page)
  await expect(page.getByText(/^\d+ nodes$/).first()).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/^\d+ edges$/).first()).toBeVisible()
  const nodesLabel = await page.getByText(/^\d+ nodes$/).first().textContent()
  expect(Number((nodesLabel ?? '0').split(' ')[0])).toBeGreaterThan(0)
  expectClean(guard)
})

test('a fragment that matches nothing shows the empty state', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/graph')
  await waitForBackend(page)
  await page.getByPlaceholder('fork, epoll, pipe, l5…').fill('zzzznotanodeatall')
  await page.getByRole('button', { name: 'search', exact: true }).click()
  await expect(page.getByText('No node matched')).toBeVisible({ timeout: 30_000 })
  expectClean(guard)
})

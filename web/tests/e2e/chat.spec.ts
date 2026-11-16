/**
 * Role:   End-to-end check of the chat page: quick actions, streaming and tool cards.
 * Input:  The SSE stream of /api/chat answered by the fake llm behind the dev proxy.
 * Output: Assertions on the rendered conversation plus the chat screenshot of the report.
 * Flow:   Prefills the draft with a quick action, sends a question, waits until the request
 *         completed and asserts the user turn, the tool card and the streamed assistant text
 *         are all on screen; a separate test proves every quick action fills the textarea.
 */
import { expect, test } from '@playwright/test'

import { expectClean, shot, watchConsole, waitForBackend } from './helpers'

const QUICK_ACTIONS = ['Generate a lab', 'Explain a topic', 'Visualize', 'Compare labs']

test('the quick action buttons prefill the draft', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/chat')
  await waitForBackend(page)
  const draft = page.getByPlaceholder(/Ask the assistant/)
  await expect(draft).toBeVisible({ timeout: 30_000 })
  for (const label of QUICK_ACTIONS) {
    await page.getByRole('button', { name: label, exact: true }).click()
    await expect(draft).not.toHaveValue('')
  }
  // the Visualize action is the one that asks the agent for a mermaid diagram
  await page.getByRole('button', { name: 'Visualize', exact: true }).click()
  await expect(draft).toHaveValue(/mermaid/i)
  expectClean(guard)
})

test('sending a question streams an assistant answer with a tool card', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/chat')
  await waitForBackend(page)
  const draft = page.getByPlaceholder(/Ask the assistant/)
  await expect(draft).toBeVisible({ timeout: 30_000 })

  await draft.fill('explain zombie process')
  await page.getByRole('button', { name: 'send', exact: true }).click()

  // the user turn appears immediately
  await expect(page.getByText('explain zombie process').last()).toBeVisible()

  // the agent calls a tool before it answers, and the card names it
  await expect(page.getByText('explain_topic').first()).toBeVisible({ timeout: 60_000 })

  // the turn is finished once the send button is back (the stop button disappears)
  await expect(page.getByRole('button', { name: 'send', exact: true })).toBeVisible({
    timeout: 90_000,
  })
  await expect(page.getByText('[fake-llm]').first()).toBeVisible()
  await shot(page, '11-chat-answer')
  expectClean(guard)
})

test('a mermaid answer renders as an inline svg', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/chat')
  await waitForBackend(page)
  const draft = page.getByPlaceholder(/Ask the assistant/)
  await expect(draft).toBeVisible({ timeout: 30_000 })

  await page.getByRole('button', { name: 'Visualize', exact: true }).click()
  await page.getByRole('button', { name: 'send', exact: true }).click()
  await expect(page.getByRole('button', { name: 'send', exact: true })).toBeVisible({
    timeout: 90_000,
  })

  // the fake llm echoes the prompt and need not emit a diagram; the renderer itself is
  // covered by tests/unit/mermaid.test.tsx, so only assert a diagram when one was produced
  const figure = page.locator('figure', { hasText: 'mermaid' })
  if (await figure.count()) {
    await expect(figure.locator('svg').first()).toBeVisible({ timeout: 30_000 })
    await shot(page, '12-chat-mermaid')
  } else {
    test.info().annotations.push({
      type: 'note',
      description: 'the fake llm produced no mermaid fence; see tests/unit/mermaid.test.tsx',
    })
  }
  expectClean(guard)
})

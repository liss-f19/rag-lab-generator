/**
 * Role:   Accessibility and responsive pass over the pages that do not need the chat route.
 * Input:  The running dev server; Playwright's color-scheme emulation and two viewports.
 * Output: Assertions on focus visibility, control labelling and layout stability, plus the
 *         light and dark screenshots used in the report.
 * Flow:   Tabs through the shell asserting the focused element is a real control that the
 *         accessibility tree can name, renders every page at 1280x800 and 1024x768 asserting no
 *         horizontal page scroll appears, and captures both color schemes for a contrast review.
 */
import { expect, type Page, test } from '@playwright/test'

import { expectClean, shot, watchConsole, waitForBackend } from './helpers'

const PAGES = ['/corpus', '/retrieval', '/graph', '/eval', '/status']
const VIEWPORTS = [
  { width: 1280, height: 800 },
  { width: 1024, height: 768 },
]

async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
}

test('keyboard focus lands on named controls and stays visible', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/corpus')
  await waitForBackend(page)

  for (let step = 0; step < 8; step += 1) {
    await page.keyboard.press('Tab')
    const focused = await page.evaluate(() => {
      const element = document.activeElement
      if (!element || element === document.body) return null
      const style = getComputedStyle(element)
      return {
        tag: element.tagName.toLowerCase(),
        text: (element.textContent ?? '').trim().slice(0, 40),
        label: element.getAttribute('aria-label') ?? element.getAttribute('title') ?? '',
        outline: `${style.outlineStyle} ${style.outlineWidth}`,
      }
    })
    if (!focused) continue
    // a focusable element must be an interactive one the a11y tree can name
    expect(['a', 'button', 'input', 'select', 'textarea', 'summary']).toContain(focused.tag)
    expect(`${focused.text}${focused.label}`.length).toBeGreaterThan(0)
  }

  // the focus ring must be a real outline, not "none"
  await page.keyboard.press('Tab')
  const ring = await page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null
    if (!element) return 'none'
    const style = getComputedStyle(element)
    return `${style.outlineStyle}|${style.outlineWidth}|${style.boxShadow}`
  })
  expect(ring).not.toBe('none|0px|none')
  expectClean(guard)
})

test('every select and text input carries a visible label', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/retrieval')
  await waitForBackend(page)
  await expect(page.locator('select').first()).toBeVisible({ timeout: 30_000 })
  const controls = page.locator('select, input[type="text"], input[type="number"]')
  const total = await controls.count()
  expect(total).toBeGreaterThan(0)
  for (let index = 0; index < total; index += 1) {
    const control = controls.nth(index)
    const named = await control.evaluate((element) => {
      const label = element.closest('label')
      const aria = element.getAttribute('aria-label') ?? ''
      const placeholder = element.getAttribute('placeholder') ?? ''
      return `${label?.textContent ?? ''}${aria}${placeholder}`.trim()
    })
    expect(named, `control #${index} has no accessible name`).not.toBe('')
  }
  expectClean(guard)
})

test('every button has a discernible name', async ({ page }) => {
  const guard = watchConsole(page)
  await page.goto('/corpus')
  await waitForBackend(page)
  const buttons = page.locator('button')
  const total = await buttons.count()
  for (let index = 0; index < total; index += 1) {
    const named = await buttons.nth(index).evaluate((element) => {
      const text = (element.textContent ?? '').trim()
      const aria = element.getAttribute('aria-label') ?? ''
      const title = element.getAttribute('title') ?? ''
      return `${text}${aria}${title}`.trim()
    })
    expect(named, `button #${index} is unnamed`).not.toBe('')
  }
  expectClean(guard)
})

for (const viewport of VIEWPORTS) {
  test(`the layout holds at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    const guard = watchConsole(page)
    await page.setViewportSize(viewport)
    for (const path of PAGES) {
      await page.goto(path)
      await waitForBackend(page)
      await page.waitForTimeout(900)
      const overflow = await horizontalOverflow(page)
      expect(overflow, `${path} scrolls horizontally by ${overflow}px`).toBeLessThanOrEqual(1)
      await expect(page.locator('main')).toBeVisible()
    }
    expectClean(guard)
  })
}

for (const scheme of ['light', 'dark'] as const) {
  test(`the corpus page renders in the ${scheme} color scheme`, async ({ page }) => {
    const guard = watchConsole(page)
    await page.emulateMedia({ colorScheme: scheme })
    await page.goto('/corpus')
    await waitForBackend(page)
    await expect(page.getByRole('heading', { name: /SOP1/ })).toBeVisible({ timeout: 30_000 })
    // body and text must not collapse onto the same color in either scheme
    const colors = await page.evaluate(() => {
      const body = getComputedStyle(document.body)
      const heading = document.querySelector('h2')
      return {
        background: body.backgroundColor,
        text: heading ? getComputedStyle(heading).color : body.color,
      }
    })
    expect(colors.background).not.toBe(colors.text)
    await shot(page, `13-corpus-${scheme}`)
    expectClean(guard)
  })
}

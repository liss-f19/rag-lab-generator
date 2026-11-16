/**
 * Role:   Verifies that a ```mermaid fence really becomes an inline <svg> in the answer body.
 * Input:  A fixed mermaid source rendered through <Mermaid/> and through <Markdown/>.
 * Output: Assertions on the injected svg, on the source toggle and on the parse-error fallback.
 * Flow:   Renders the component with a valid diagram and waits for the asynchronous mermaid
 *         import to inject the svg; then renders an invalid diagram and asserts the raw source
 *         survives, because the fake llm used in demos never emits a diagram of its own.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Markdown } from '../../src/components/Markdown'
import { Mermaid } from '../../src/components/Mermaid'

const FLOWCHART = `graph TD
  A[fork] --> B[child]
  A --> C[parent]
  B --> D[exec]
  C --> E[wait]
  D --> E`

const BROKEN = 'graph TD\n  A[[[[unbalanced'

describe('Mermaid', () => {
  it('renders a valid diagram into an inline svg', async () => {
    const { container } = render(<Mermaid chart={FLOWCHART} />)
    await waitFor(
      () => {
        expect(container.querySelector('svg')).not.toBeNull()
      },
      { timeout: 20000 },
    )
    const svg = container.querySelector('svg')
    expect(svg?.outerHTML).toContain('fork')
  }, 30000)

  it('keeps a source toggle next to the diagram', async () => {
    render(<Mermaid chart={FLOWCHART} />)
    await waitFor(
      () => {
        expect(screen.getByRole('button', { name: /show source/i })).toBeInTheDocument()
      },
      { timeout: 20000 },
    )
  }, 30000)

  it('falls back to the raw source when mermaid cannot parse the chart', async () => {
    const { container } = render(<Mermaid chart={BROKEN} />)
    await waitFor(
      () => {
        expect(container.querySelector('pre')).not.toBeNull()
      },
      { timeout: 20000 },
    )
    expect(container.textContent).toContain('unbalanced')
  }, 30000)
})

describe('Markdown', () => {
  it('routes a ```mermaid fence to the diagram renderer instead of a code block', async () => {
    const { container } = render(<Markdown content={'Here:\n\n```mermaid\n' + FLOWCHART + '\n```\n'} />)
    await waitFor(
      () => {
        expect(container.querySelector('svg')).not.toBeNull()
      },
      { timeout: 20000 },
    )
  }, 30000)

  it('still renders an ordinary c code fence as code', () => {
    const { container } = render(
      <Markdown content={'```c\nint main(void) { return 0; }\n```\n'} />,
    )
    expect(container.querySelector('code')?.textContent).toContain('int main')
  })
})

/**
 * Role:   Renders a mermaid diagram source as inline SVG with a source toggle.
 * Input:  The diagram source emitted by the agent inside a ```mermaid fence.
 * Output: An <svg> figure, or the raw source when mermaid cannot parse it.
 * Flow:   Imports mermaid lazily on first use, initializes it with the theme matching the OS
 *         color scheme, renders the chart into a string and injects it; a parse error falls
 *         back to the source block so a broken diagram never hides the answer.
 */
import { useEffect, useState } from 'react'

function prefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export function Mermaid({ chart }: { chart: string }) {
  const [svg, setSvg] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showSource, setShowSource] = useState(false)

  useEffect(() => {
    let cancelled = false
    const render = async () => {
      try {
        const mermaid = (await import('mermaid')).default
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: prefersDark() ? 'dark' : 'default',
          fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        })
        const id = `mermaid-${Math.random().toString(36).slice(2)}`
        const rendered = await mermaid.render(id, chart)
        if (!cancelled) {
          setSvg(rendered.svg)
          setError(null)
        }
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause))
      }
    }
    void render()
    return () => {
      cancelled = true
    }
  }, [chart])

  return (
    <figure className="my-3 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[11px] text-slate-500">mermaid</span>
        <button
          type="button"
          className="text-[11px] text-indigo-600 hover:underline dark:text-indigo-400"
          onClick={() => setShowSource((previous) => !previous)}
        >
          {showSource ? 'show diagram' : 'show source'}
        </button>
      </div>
      {error && (
        <p className="mb-2 font-mono text-[11px] text-rose-600 dark:text-rose-400">{error}</p>
      )}
      {showSource || error ? (
        <pre className="overflow-x-auto text-xs">
          <code>{chart}</code>
        </pre>
      ) : (
        <div className="overflow-x-auto [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full" dangerouslySetInnerHTML={{ __html: svg }} />
      )}
    </figure>
  )
}

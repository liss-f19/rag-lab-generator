/**
 * Role:   One retrieved chunk as a card: score, provenance, graph path and expandable text.
 * Input:  A ScoredChunk, the best score of its column, an optional graph path and flags.
 * Output: A clickable card; onOpen hands the chunk to the inspector panel.
 * Flow:   Renders the rank, the kind and source badges and the score bar, then the breadcrumb
 *         (document / section) and a clamped text body that expands in place; a chunk that also
 *         appears in another column gets an accent border so overlaps are visible at a glance.
 */
import { useState } from 'react'

import type { ScoredChunk } from '../api/types'
import { Badge, ScoreBar } from './ui'

const KIND_TONES: Record<string, string> = {
  tutorial: 'info',
  task: 'ok',
  code: 'warn',
  lecture: 'neutral',
  summary: 'neutral',
  info: 'neutral',
}

export function ChunkCard({
  scored,
  max,
  rank,
  path,
  shared,
  onOpen,
}: {
  scored: ScoredChunk
  max: number
  rank: number
  path?: string[]
  shared?: boolean
  onOpen?: (scored: ScoredChunk) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const { chunk } = scored
  return (
    <article
      className={`rounded-lg border p-3 transition ${
        shared
          ? 'border-indigo-400 bg-indigo-50/40 dark:border-indigo-600 dark:bg-indigo-950/20'
          : 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'
      }`}
    >
      <header className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-slate-400">#{rank}</span>
        <Badge tone={KIND_TONES[chunk.kind] ?? 'neutral'}>{chunk.kind}</Badge>
        <Badge title="searcher that produced the score">{scored.source}</Badge>
        {shared && <Badge tone="info">both</Badge>}
        <div className="ml-auto">
          <ScoreBar score={scored.score} max={max} />
        </div>
      </header>

      <p className="mt-2 truncate font-mono text-[11px] text-slate-500" title={chunk.id}>
        {chunk.document_id}
        {chunk.section_id ? ` › ${chunk.section_id}` : ''}
      </p>

      {path && path.length > 0 && (
        <p className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-slate-500">
          {path.map((node, index) => (
            <span key={`${node}-${index}`} className="flex items-center gap-1">
              {index > 0 && <span className="text-slate-400">→</span>}
              <code className="rounded bg-slate-100 px-1 dark:bg-slate-800">{node}</code>
            </span>
          ))}
        </p>
      )}

      <p
        className={`mt-2 text-xs leading-relaxed whitespace-pre-wrap text-slate-700 dark:text-slate-300 ${
          expanded ? '' : 'line-clamp-3'
        }`}
      >
        {chunk.text}
      </p>

      <footer className="mt-2 flex items-center gap-3 text-[11px]">
        <button
          type="button"
          className="text-indigo-600 hover:underline dark:text-indigo-400"
          onClick={() => setExpanded((previous) => !previous)}
        >
          {expanded ? 'collapse' : `expand (${chunk.char_count} chars)`}
        </button>
        {onOpen && (
          <button
            type="button"
            className="text-slate-500 hover:underline"
            onClick={() => onOpen(scored)}
          >
            inspect
          </button>
        )}
      </footer>
    </article>
  )
}

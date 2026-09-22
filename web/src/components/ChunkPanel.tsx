/**
 * Role:   Right-hand inspector drawer showing one chunk in full.
 * Input:  A chunk (or a graph chunk preview) and a close callback.
 * Output: A fixed overlay panel with the identifiers, the metadata and the whole text.
 * Flow:   Renders nothing when no chunk is selected; otherwise shows a scrollable panel whose
 *         header carries the chunk id and whose body prints metadata as json and the raw text.
 */
import type { Chunk, ChunkPreview } from '../api/types'
import { Badge, Button } from './ui'

export type InspectedChunk = Chunk | ChunkPreview

function metadataOf(chunk: InspectedChunk): Record<string, unknown> | null {
  return 'metadata' in chunk ? chunk.metadata : null
}

export function ChunkPanel({
  chunk,
  onClose,
}: {
  chunk: InspectedChunk | null
  onClose: () => void
}) {
  if (!chunk) return null
  const metadata = metadataOf(chunk)
  return (
    <aside className="fixed inset-y-0 right-0 z-40 flex w-full max-w-lg flex-col border-l border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900">
      <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <div className="min-w-0">
          <p className="text-sm font-semibold">Chunk</p>
          <p className="truncate font-mono text-[11px] text-slate-500" title={chunk.id}>
            {chunk.id}
          </p>
        </div>
        <Button variant="ghost" onClick={onClose}>
          close
        </Button>
      </header>
      <div className="flex flex-wrap gap-2 border-b border-slate-200 px-4 py-2 dark:border-slate-800">
        <Badge tone="info">{chunk.kind}</Badge>
        {chunk.lab_id && <Badge>{chunk.lab_id}</Badge>}
        {chunk.section_id && <Badge>{chunk.section_id}</Badge>}
        <Badge>{chunk.document_id}</Badge>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <pre className="text-xs leading-relaxed whitespace-pre-wrap">{chunk.text}</pre>
        {metadata && Object.keys(metadata).length > 0 && (
          <>
            <p className="mt-4 text-xs font-semibold text-slate-500">metadata</p>
            <pre className="mt-1 overflow-x-auto rounded-lg bg-slate-100 p-2 text-[11px] dark:bg-slate-950">
              {JSON.stringify(metadata, null, 2)}
            </pre>
          </>
        )}
      </div>
    </aside>
  )
}

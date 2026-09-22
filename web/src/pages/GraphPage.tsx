/**
 * Role:   Knowledge graph explorer: search nodes, expand a neighbourhood, inspect its chunks.
 * Input:  A label query, a hop count and the clicked node; /api/graph/*.
 * Output: The force layout of the current subgraph plus a details panel for the selected node.
 * Flow:   A label search seeds the view; selecting a node switches the query to /neighbors with
 *         the chosen hop count, and the side panel fetches the chunks attached to that node so
 *         the graph and the retrieval corpus stay connected.
 */
import { useState } from 'react'

import { useGraphNeighbors, useGraphSearch, useGraphStats, useNodeChunks } from '../api/hooks'
import type { ChunkPreview } from '../api/types'
import { ChunkPanel } from '../components/ChunkPanel'
import { GraphView } from '../components/GraphView'
import { KIND_COLORS } from '../components/graphKinds'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Field,
  Panel,
  Select,
  Spinner,
  TextInput,
} from '../components/ui'

export function GraphPage() {
  const [term, setTerm] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [center, setCenter] = useState<string | null>(null)
  const [hops, setHops] = useState('1')
  const [inspected, setInspected] = useState<ChunkPreview | null>(null)

  const stats = useGraphStats()
  const search = useGraphSearch(submitted)
  const neighbors = useGraphNeighbors(center, Number(hops) || 1)
  const chunks = useNodeChunks(center)

  const graph = center ? neighbors.data : search.data
  const pending = center ? neighbors.isLoading : search.isLoading
  const failure = center ? neighbors.error : search.error
  const selectedNode = graph?.nodes.find((node) => node.id === center) ?? null

  return (
    <div className="space-y-4">
      <Panel
        title="Knowledge graph"
        actions={
          stats.data ? (
            <span className="flex gap-1.5">
              <Badge tone="info">{stats.data.counts.nodes ?? 0} nodes</Badge>
              <Badge tone="info">{stats.data.counts.edges ?? 0} edges</Badge>
            </span>
          ) : null
        }
      >
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            setCenter(null)
            setSubmitted(term)
          }}
        >
          <Field label="node label contains">
            <TextInput
              value={term}
              onChange={setTerm}
              placeholder="fork, epoll, pipe, l5…"
              className="w-64"
            />
          </Field>
          <Field label="hops">
            <Select value={hops} onChange={setHops} options={['1', '2', '3']} />
          </Field>
          <Button type="submit">search</Button>
          {center && (
            <Button variant="ghost" onClick={() => setCenter(null)}>
              back to results
            </Button>
          )}
        </form>

        {stats.isError && (
          <div className="mt-3">
            <ErrorBox title="The graph store is not available" error={stats.error} />
            <p className="mt-2 text-[11px] text-slate-500">
              Build it with <code>uv run rag-lab graph-build</code> once the corpus is indexed.
            </p>
          </div>
        )}
      </Panel>

      {pending && <Spinner label="loading subgraph" />}
      {failure && !pending && <ErrorBox error={failure} />}

      {graph && graph.nodes.length === 0 && (
        <EmptyState title="No node matched" hint="Try a shorter fragment of the label." />
      )}

      {graph && graph.nodes.length > 0 && (
        <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
          <Panel
            title={center ? `Neighbourhood of ${center}` : `Matches for “${submitted}”`}
            actions={<Badge>{graph.nodes.length} nodes</Badge>}
          >
            <GraphView graph={graph} selected={center} onSelect={setCenter} />
          </Panel>

          <div className="space-y-4">
            <Panel title="Selected node">
              {selectedNode ? (
                <div className="space-y-2 text-xs">
                  <p className="flex items-center gap-2">
                    <span
                      className="inline-block size-3 rounded-full"
                      style={{ background: KIND_COLORS[selectedNode.kind] ?? '#94a3b8' }}
                    />
                    <span className="font-medium">{selectedNode.label}</span>
                  </p>
                  <p className="font-mono text-[11px] break-all text-slate-500">
                    {selectedNode.id}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge tone="info">{selectedNode.kind}</Badge>
                    <Badge>degree {selectedNode.degree}</Badge>
                    {selectedNode.course && <Badge>{selectedNode.course}</Badge>}
                    {selectedNode.lab_id && <Badge>{selectedNode.lab_id}</Badge>}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500">Click a node in the graph.</p>
              )}
            </Panel>

            <Panel title="Chunks of this node">
              {!center && <p className="text-xs text-slate-500">No node selected.</p>}
              {center && chunks.isLoading && <Spinner />}
              {center && chunks.isError && <ErrorBox error={chunks.error} />}
              {center && chunks.data && chunks.data.chunks.length === 0 && (
                <p className="text-xs text-slate-500">This node has no attached chunks.</p>
              )}
              <ul className="space-y-2">
                {(chunks.data?.chunks ?? []).map((chunk) => (
                  <li key={chunk.id}>
                    <button
                      type="button"
                      onClick={() => setInspected(chunk)}
                      className="w-full rounded-lg border border-slate-200 p-2 text-left hover:border-indigo-400 dark:border-slate-800"
                    >
                      <span className="flex items-center gap-1.5">
                        <Badge tone="info">{chunk.kind}</Badge>
                        <span className="truncate font-mono text-[11px] text-slate-500">
                          {chunk.section_id ?? chunk.document_id}
                        </span>
                      </span>
                      <span className="mt-1 line-clamp-2 block text-xs text-slate-600 dark:text-slate-300">
                        {chunk.text}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      )}

      {!graph && !pending && !failure && (
        <EmptyState
          title="Search the graph"
          hint="Type an api function, a concept or a lab id and press search."
        />
      )}

      <ChunkPanel chunk={inspected} onClose={() => setInspected(null)} />
    </div>
  )
}

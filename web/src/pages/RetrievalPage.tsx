/**
 * Role:   Retrieval laboratory: run one query through several rag/searcher pairs side by side.
 * Input:  A query, the shared chunker/embedder/k/course selection and a list of configurations.
 * Output: One column per configuration with latency, trace summary and the ranked chunks.
 * Flow:   Builds a CompareRequest from the form, posts it through TanStack Query's mutation,
 *         counts in how many columns every chunk id appears to highlight the overlap, and
 *         renders each chunk with its score bar, kind badge, breadcrumb and graph path.
 */
import { useMutation } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { api } from '../api/client'
import { useCourses, useStrategies } from '../api/hooks'
import type { CompareConfig, CompareResponse, RetrievedContext, ScoredChunk } from '../api/types'
import { ChunkCard } from '../components/ChunkCard'
import { ChunkPanel } from '../components/ChunkPanel'
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

const EXAMPLES = [
  'how to wait for a child process without blocking',
  'difference between select and epoll',
  'named pipes FIFO example task',
  'thread synchronisation with a mutex and a condition variable',
]

function pathsOf(context: RetrievedContext): Record<string, string[]> {
  const paths = context.trace.paths
  return typeof paths === 'object' && paths !== null ? (paths as Record<string, string[]>) : {}
}

function traceSummary(context: RetrievedContext): [string, string][] {
  return Object.entries(context.trace)
    .filter(([key]) => key !== 'paths')
    .map(([key, value]) => [key, typeof value === 'object' ? JSON.stringify(value) : String(value)])
}

export function RetrievalPage() {
  const strategies = useStrategies()
  const courses = useCourses()
  const kinds = strategies.data?.kinds ?? {}
  const defaults = strategies.data?.defaults ?? {}

  const [query, setQuery] = useState(EXAMPLES[0] ?? '')
  const [strategy, setStrategy] = useState('')
  const [embedder, setEmbedder] = useState('')
  const [course, setCourse] = useState('')
  const [k, setK] = useState('8')
  const [configs, setConfigs] = useState<CompareConfig[]>([{ rag: '', searcher: '' }])
  const [selected, setSelected] = useState<ScoredChunk | null>(null)

  const run = useMutation<CompareResponse>({
    mutationFn: () =>
      api.compare({
        query,
        k: Number(k) || undefined,
        strategy: strategy || undefined,
        embedder: embedder || undefined,
        course: course || null,
        configs: configs.map((config) => ({
          rag: config.rag || defaults.rag || 'vector',
          searcher: config.searcher || defaults.searcher || 'hybrid_rrf',
        })),
      }),
  })

  const overlap = useMemo(() => {
    const counts = new Map<string, number>()
    for (const result of run.data?.results ?? []) {
      for (const id of new Set((result.context?.chunks ?? []).map((item) => item.chunk.id))) {
        counts.set(id, (counts.get(id) ?? 0) + 1)
      }
    }
    return counts
  }, [run.data])

  const updateConfig = (index: number, patch: Partial<CompareConfig>) =>
    setConfigs((previous) =>
      previous.map((config, position) => (position === index ? { ...config, ...patch } : config)),
    )

  return (
    <div className="space-y-4">
      <Panel
        title="Query"
        actions={
          <Button onClick={() => run.mutate()} disabled={run.isPending || query.trim().length === 0}>
            {run.isPending ? 'running…' : 'run comparison'}
          </Button>
        }
      >
        <TextInput
          value={query}
          onChange={setQuery}
          placeholder="ask the corpus something"
          className="w-full"
        />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setQuery(example)}
              className="rounded-full border border-slate-300 px-2 py-0.5 text-[11px] text-slate-600 hover:border-indigo-400 hover:text-indigo-600 dark:border-slate-700 dark:text-slate-300"
            >
              {example}
            </button>
          ))}
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="chunker (strategy)">
            <Select
              value={strategy}
              onChange={setStrategy}
              options={kinds.chunker ?? []}
              allowEmpty
              emptyLabel={`default (${defaults.chunker ?? '?'})`}
            />
          </Field>
          <Field label="embedder">
            <Select
              value={embedder}
              onChange={setEmbedder}
              options={kinds.embedder ?? []}
              allowEmpty
              emptyLabel={`default (${defaults.embedder ?? '?'})`}
            />
          </Field>
          <Field label="course filter">
            <Select
              value={course}
              onChange={setCourse}
              options={(courses.data?.courses ?? []).map((entry) => entry.course)}
              allowEmpty
              emptyLabel="all courses"
            />
          </Field>
          <Field label="k">
            <TextInput value={k} onChange={setK} type="number" />
          </Field>
        </div>

        <div className="mt-4 space-y-2">
          <p className="text-xs font-semibold text-slate-500">Configurations</p>
          {configs.map((config, index) => (
            <div key={index} className="flex flex-wrap items-end gap-3">
              <span className="font-mono text-[11px] text-slate-400">#{index + 1}</span>
              <Field label="rag">
                <Select
                  value={config.rag}
                  onChange={(value) => updateConfig(index, { rag: value })}
                  options={kinds.rag ?? []}
                  allowEmpty
                  emptyLabel={`default (${defaults.rag ?? '?'})`}
                />
              </Field>
              <Field label="searcher">
                <Select
                  value={config.searcher}
                  onChange={(value) => updateConfig(index, { searcher: value })}
                  options={kinds.searcher ?? []}
                  allowEmpty
                  emptyLabel={`default (${defaults.searcher ?? '?'})`}
                />
              </Field>
              {configs.length > 1 && (
                <Button
                  variant="danger"
                  onClick={() =>
                    setConfigs((previous) => previous.filter((_, position) => position !== index))
                  }
                >
                  remove
                </Button>
              )}
            </div>
          ))}
          {configs.length < 4 && (
            <Button
              variant="ghost"
              onClick={() => setConfigs((previous) => [...previous, { rag: '', searcher: '' }])}
            >
              + add config
            </Button>
          )}
        </div>
      </Panel>

      {run.isPending && <Spinner label="retrieving" />}
      {run.isError && <ErrorBox error={run.error} />}

      {run.data && (
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: `repeat(${run.data.results.length}, minmax(320px, 1fr))` }}
        >
          {run.data.results.map((result, index) => {
            const chunks = result.context?.chunks ?? []
            const best = chunks.reduce((max, item) => Math.max(max, item.score), 0)
            const paths = result.context ? pathsOf(result.context) : {}
            return (
              <Panel
                key={index}
                title={
                  <span className="flex flex-wrap items-center gap-1.5">
                    <Badge tone="info">{result.config.rag}</Badge>
                    <Badge>{result.config.searcher}</Badge>
                    <Badge>{result.config.strategy}</Badge>
                    <Badge>k={result.config.k}</Badge>
                  </span>
                }
                actions={
                  <Badge tone={result.error ? 'bad' : 'ok'}>{result.latency_ms.toFixed(0)} ms</Badge>
                }
              >
                {result.error ? (
                  <ErrorBox title="This configuration failed" error={result.error} />
                ) : chunks.length === 0 ? (
                  <EmptyState title="No chunks returned" hint="Index the corpus first." />
                ) : (
                  <>
                    <div className="mb-3 flex flex-wrap gap-1.5">
                      {result.context &&
                        traceSummary(result.context).map(([key, value]) => (
                          <Badge key={key} title={value}>
                            {key}={value.length > 28 ? `${value.slice(0, 28)}…` : value}
                          </Badge>
                        ))}
                    </div>
                    <div className="space-y-2">
                      {chunks.map((scored, rank) => (
                        <ChunkCard
                          key={scored.chunk.id}
                          scored={scored}
                          rank={rank + 1}
                          max={best}
                          path={paths[scored.chunk.id]}
                          shared={(overlap.get(scored.chunk.id) ?? 0) > 1}
                          onOpen={setSelected}
                        />
                      ))}
                    </div>
                  </>
                )}
              </Panel>
            )
          })}
        </div>
      )}

      <ChunkPanel chunk={selected?.chunk ?? null} onClose={() => setSelected(null)} />
    </div>
  )
}

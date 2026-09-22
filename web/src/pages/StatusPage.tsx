/**
 * Role:   Configuration page: what the backend is running and which strategies are registered.
 * Input:  /api/health and /api/strategies.
 * Output: Two panels, one with the resolved settings, one with the registry contents.
 * Flow:   Renders the health fields as a definition list with ok/bad badges for the probes, and
 *         lists every registered strategy name per kind, marking the current default.
 */
import type { ReactNode } from 'react'

import { useHealth, useStrategies } from '../api/hooks'
import { Badge, ErrorBox, Panel, Spinner } from '../components/ui'

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-1.5 last:border-0 dark:border-slate-800">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="font-mono text-xs">{value}</span>
    </div>
  )
}

export function StatusPage() {
  const health = useHealth()
  const strategies = useStrategies()

  if (health.isLoading) return <Spinner label="reading /api/health" />
  if (health.isError || !health.data) return <ErrorBox error={health.error} />
  const data = health.data
  const defaults = strategies.data?.defaults ?? {}

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Runtime configuration">
        <Row label="api version" value={data.version} />
        <Row label="llm provider" value={`${data.llm_provider} (${data.llm_model})`} />
        <Row label="embedder" value={data.embedding_provider} />
        <Row label="rag strategy" value={data.rag} />
        <Row label="searcher" value={data.searcher} />
        <Row label="chunker" value={data.chunker} />
        <Row label="retrieval k" value={data.retrieval_k} />
        <Row label="data dir" value={data.data_dir} />
        <Row
          label="database"
          value={
            <Badge tone={data.db_reachable ? 'ok' : 'bad'}>
              {data.db_reachable ? 'reachable' : 'unreachable'}
            </Badge>
          }
        />
        <Row
          label="corpus"
          value={
            <Badge tone={data.corpus_present ? 'ok' : 'warn'}>
              {data.corpus_present ? 'present' : 'missing'}
            </Badge>
          }
        />
        <Row
          label="agent graph"
          value={
            <Badge tone={data.agent_available ? 'ok' : 'warn'}>
              {data.agent_available ? 'compiled' : 'not available'}
            </Badge>
          }
        />
        <Row
          label="graph store"
          value={
            <Badge tone={data.graph_available ? 'ok' : 'warn'}>
              {data.graph_available ? 'importable' : 'not available'}
            </Badge>
          }
        />
      </Panel>

      <Panel title="Registered strategies">
        <div className="space-y-3">
          {Object.entries(data.strategies).map(([kind, names]) => (
            <div key={kind}>
              <p className="text-xs font-semibold text-slate-500">{kind}</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {names.length === 0 && <span className="text-xs text-slate-400">none</span>}
                {names.map((name) => (
                  <Badge key={name} tone={defaults[kind] === name ? 'ok' : 'neutral'}>
                    {name}
                    {defaults[kind] === name ? ' ·default' : ''}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
        <p className="mt-4 text-[11px] text-slate-500">
          Change the defaults in <code>.env</code> (RAG, SEARCHER, CHUNKER, EMBEDDING_PROVIDER,
          LLM_PROVIDER) and restart <code>rag-lab serve</code>.
        </p>
      </Panel>
    </div>
  )
}

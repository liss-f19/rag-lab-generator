/**
 * Role:   Top-bar summary of the backend state.
 * Input:  The /api/health query (polled by useHealth).
 * Output: A row of badges for llm, rag, database, corpus and agent availability.
 * Flow:   Shows a muted placeholder while the first poll is in flight, a red badge when the
 *         backend is unreachable, and otherwise one badge per capability with an ok/bad tone.
 */
import { useHealth } from '../api/hooks'
import { Badge } from './ui'

export function HealthBadge() {
  const { data, isLoading, isError } = useHealth()

  if (isLoading) return <Badge>connecting…</Badge>
  if (isError || !data) return <Badge tone="bad">backend offline</Badge>

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Badge tone="info" title={data.llm_model}>
        llm:{data.llm_provider}
      </Badge>
      <Badge tone="info">rag:{data.rag}</Badge>
      <Badge tone="info">emb:{data.embedding_provider}</Badge>
      <Badge tone={data.db_reachable ? 'ok' : 'bad'} title={data.data_dir}>
        db:{data.db_reachable ? 'up' : 'down'}
      </Badge>
      <Badge tone={data.corpus_present ? 'ok' : 'warn'}>
        corpus:{data.corpus_present ? 'ready' : 'empty'}
      </Badge>
      <Badge tone={data.agent_available ? 'ok' : 'warn'}>
        agent:{data.agent_available ? 'ready' : 'missing'}
      </Badge>
    </div>
  )
}

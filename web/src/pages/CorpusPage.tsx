/**
 * Role:   Corpus browser: every course of data/raw with its labs as a grid of cards.
 * Input:  /api/courses.
 * Output: Links into the lab detail page, plus an empty state explaining how to ingest.
 * Flow:   Groups the response per course, renders one card per lab with its number, title and
 *         counters, and shows the ingestion commands when data/raw is still empty.
 */
import { Link } from 'react-router'

import { useCourses } from '../api/hooks'
import { Badge, EmptyState, ErrorBox, Panel, Spinner } from '../components/ui'

export function CorpusPage() {
  const { data, isLoading, isError, error } = useCourses()

  if (isLoading) return <Spinner label="reading data/raw" />
  if (isError || !data) return <ErrorBox error={error} />

  if (data.courses.length === 0) {
    return (
      <EmptyState
        title="No ingested labs yet"
        hint={
          <>
            <p>
              Nothing under <code>{data.data_dir}/raw</code>. Build the corpus first:
            </p>
            <pre className="mt-2 inline-block rounded bg-slate-200 px-3 py-2 text-left text-[11px] dark:bg-slate-800">
              uv run rag-lab fetch{'\n'}uv run rag-lab ingest
            </pre>
          </>
        }
      />
    )
  }

  return (
    <div className="space-y-4">
      {data.courses.map((course) => (
        <Panel
          key={course.course}
          title={
            <span className="flex items-center gap-2">
              {course.course.toUpperCase()}
              <Badge>{course.n_labs} labs</Badge>
            </span>
          }
        >
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {course.labs.map((lab) => (
              <Link
                key={lab.id}
                to={`/corpus/${course.course}/${lab.slug}`}
                className="group rounded-lg border border-slate-200 p-3 transition hover:border-indigo-400 hover:shadow-sm dark:border-slate-800 dark:hover:border-indigo-600"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-mono text-xs text-indigo-600 dark:text-indigo-400">
                    L{lab.number || '?'}
                  </span>
                  <span className="font-mono text-[11px] text-slate-400">{lab.slug}</span>
                </div>
                <p className="mt-1 text-sm font-medium group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
                  {lab.title}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone="ok">{lab.n_tasks} tasks</Badge>
                  <Badge tone="info">{lab.n_sections} sections</Badge>
                  <Badge>{lab.n_files} files</Badge>
                  {lab.has_summary && <Badge tone="warn">summary</Badge>}
                </div>
              </Link>
            ))}
          </div>
        </Panel>
      ))}
    </div>
  )
}

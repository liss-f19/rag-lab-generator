/**
 * Role:   One lab in detail: tutorial, tasks, attachments and the generated summary.
 * Input:  Route parameters course and slug; /api/labs/{course}/{slug}.
 * Output: A tabbed view over the parsed lab.xml plus inline previews of src/slides/extra files.
 * Flow:   Fetches the lab once, keeps the active tab and the previewed file in local state, and
 *         renders each section and task from the model; a preview opens pdfs in an iframe and
 *         text files inline through the /files route.
 */
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { api } from '../api/client'
import { useLab } from '../api/hooks'
import type { LabFile, Section, Task } from '../api/types'
import { Markdown } from '../components/Markdown'
import { Badge, Button, EmptyState, ErrorBox, Panel, Spinner } from '../components/ui'

type Tab = 'tutorial' | 'tasks' | 'files' | 'summary'

const TABS: { id: Tab; label: string }[] = [
  { id: 'tutorial', label: 'Tutorial' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'files', label: 'Files' },
  { id: 'summary', label: 'Summary' },
]

function SectionView({
  section,
  onOpenFile,
}: {
  section: Section
  onOpenFile: (path: string) => void
}) {
  return (
    <article className="border-b border-slate-100 py-3 last:border-0 dark:border-slate-800">
      <h3
        className="font-semibold"
        style={{ fontSize: `${Math.max(0.8, 1.05 - section.level * 0.05)}rem` }}
      >
        {section.title}
      </h3>
      <p className="mt-0.5 font-mono text-[11px] text-slate-400">
        {section.id}
        {section.parent_id ? ` ← ${section.parent_id}` : ''}
      </p>
      <div className="mt-2">
        <Markdown content={section.text} />
      </div>
      {section.code_refs.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {section.code_refs.map((ref) => (
            <button
              key={ref}
              type="button"
              onClick={() => onOpenFile(ref)}
              className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-indigo-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-indigo-400 dark:hover:bg-slate-700"
            >
              {ref}
            </button>
          ))}
        </div>
      )}
    </article>
  )
}

function TaskView({ task }: { task: Task }) {
  return (
    <article className="border-b border-slate-100 py-3 last:border-0 dark:border-slate-800">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="ok">{task.id}</Badge>
        <h3 className="text-sm font-semibold">{task.title}</h3>
        {task.source_url && (
          <a
            href={task.source_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-[11px] text-indigo-600 hover:underline dark:text-indigo-400"
          >
            source ↗
          </a>
        )}
      </div>
      <div className="mt-2">
        <Markdown content={task.statement} />
      </div>
      {task.stages.length > 0 && (
        <ol className="mt-2 space-y-1">
          {task.stages.map((stage) => (
            <li key={stage.n} className="flex gap-2 text-xs">
              <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 font-mono text-[10px] text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-300">
                {stage.n}
              </span>
              <span className="leading-relaxed">{stage.text}</span>
            </li>
          ))}
        </ol>
      )}
      {(task.solution_refs.length > 0 || task.attachments.length > 0 || task.notes) && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {task.solution_refs.map((ref) => (
            <Badge key={ref} tone="warn">
              solution: {ref}
            </Badge>
          ))}
          {task.attachments.map((ref) => (
            <Badge key={ref}>attachment: {ref}</Badge>
          ))}
          {task.notes && <span className="text-[11px] text-slate-500">{task.notes}</span>}
        </div>
      )}
    </article>
  )
}

function FilePreview({
  course,
  slug,
  file,
  onClose,
}: {
  course: string
  slug: string
  file: LabFile
  onClose: () => void
}) {
  const url = api.fileUrl(course, slug, file.path)
  const isPdf = file.media_type === 'application/pdf'
  const isImage = file.media_type.startsWith('image/')
  return (
    <Panel
      title={<span className="font-mono text-xs">{file.path}</span>}
      actions={
        <div className="flex gap-2">
          <a
            href={url}
            download
            className="rounded-md px-2 py-1 text-xs text-indigo-600 hover:underline dark:text-indigo-400"
          >
            download
          </a>
          <Button variant="ghost" onClick={onClose}>
            close
          </Button>
        </div>
      }
    >
      {isPdf ? (
        <iframe title={file.path} src={url} className="h-[70vh] w-full rounded-lg border-0" />
      ) : isImage ? (
        <img src={url} alt={file.path} className="max-h-[70vh] rounded-lg" />
      ) : (
        <iframe
          title={file.path}
          src={url}
          className="h-[60vh] w-full rounded-lg border border-slate-200 bg-white dark:border-slate-800"
        />
      )}
    </Panel>
  )
}

export function LabPage() {
  const { course = '', slug = '' } = useParams()
  const { data, isLoading, isError, error } = useLab(course, slug)
  const [tab, setTab] = useState<Tab>('tutorial')
  const [preview, setPreview] = useState<LabFile | null>(null)

  if (isLoading) return <Spinner label={`reading ${course}/${slug}`} />
  if (isError || !data) return <ErrorBox error={error} />

  const { lab, files, summary } = data
  const openFile = (path: string) => {
    const match = files.find((file) => file.path === path || file.path.endsWith(`/${path}`))
    if (match) {
      setPreview(match)
      setTab('files')
    }
  }

  return (
    <div className="space-y-4">
      <Panel
        title={
          <span className="flex flex-wrap items-center gap-2">
            <Link to="/corpus" className="text-slate-400 hover:underline">
              corpus
            </Link>
            <span className="text-slate-300">/</span>
            <span>{lab.title}</span>
            <Badge tone="info">L{lab.number || '?'}</Badge>
            <Badge>{lab.course}</Badge>
          </span>
        }
        actions={
          lab.source_url ? (
            <a
              href={lab.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
            >
              original page ↗
            </a>
          ) : null
        }
      >
        <div className="flex flex-wrap gap-1.5">
          {lab.topics.map((topic) => (
            <Badge key={topic} tone="info">
              {topic}
            </Badge>
          ))}
          {lab.topics.length === 0 && <span className="text-xs text-slate-400">no topics</span>}
        </div>
        <nav className="mt-3 flex gap-1 border-b border-slate-200 dark:border-slate-800">
          {TABS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              onClick={() => setTab(entry.id)}
              className={`-mb-px border-b-2 px-3 py-1.5 text-sm transition ${
                tab === entry.id
                  ? 'border-indigo-500 font-medium text-indigo-600 dark:text-indigo-400'
                  : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
              }`}
            >
              {entry.label}
              {entry.id === 'tasks' && ` (${lab.tasks.length})`}
              {entry.id === 'files' && ` (${files.length})`}
            </button>
          ))}
        </nav>

        <div className="mt-3">
          {tab === 'tutorial' &&
            (lab.sections.length === 0 ? (
              <EmptyState title="This lab has no tutorial sections" />
            ) : (
              lab.sections.map((section) => (
                <SectionView key={section.id} section={section} onOpenFile={openFile} />
              ))
            ))}

          {tab === 'tasks' &&
            (lab.tasks.length === 0 ? (
              <EmptyState title="This lab has no example tasks" />
            ) : (
              lab.tasks.map((task) => <TaskView key={task.id} task={task} />)
            ))}

          {tab === 'files' &&
            (files.length === 0 ? (
              <EmptyState title="No attachments were copied for this lab" />
            ) : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {files.map((file) => (
                  <li key={file.path} className="flex items-center gap-3 py-1.5">
                    <Badge tone={file.group === 'src' ? 'ok' : 'neutral'}>{file.group}</Badge>
                    <button
                      type="button"
                      onClick={() => setPreview(file)}
                      className="min-w-0 flex-1 truncate text-left font-mono text-xs text-indigo-600 hover:underline dark:text-indigo-400"
                    >
                      {file.path}
                    </button>
                    <span className="font-mono text-[11px] text-slate-400">{file.size} B</span>
                    <a
                      href={api.fileUrl(course, slug, file.path)}
                      download
                      className="text-[11px] text-slate-500 hover:underline"
                    >
                      download
                    </a>
                  </li>
                ))}
              </ul>
            ))}

          {tab === 'summary' &&
            (summary ? (
              <Markdown content={summary} />
            ) : (
              <EmptyState
                title="No summary.md for this lab"
                hint="Generate it with uv run rag-lab summarize"
              />
            ))}
        </div>
      </Panel>

      {preview && (
        <FilePreview
          course={course}
          slug={slug}
          file={preview}
          onClose={() => setPreview(null)}
        />
      )}

      {lab.references.length > 0 && (
        <Panel title="References">
          <ul className="space-y-1">
            {lab.references.map((reference) => (
              <li key={reference.url}>
                <a
                  href={reference.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
                >
                  {reference.title || reference.url}
                </a>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  )
}

/**
 * Role:   Chat page: threads, streamed agent answers, tool-call cards and a chunk inspector.
 * Input:  User messages plus the course / lab / rag / llm selection; the SSE stream of /api/chat.
 * Output: A rendered conversation with markdown and mermaid, and the retrieval context the
 *         agent actually used.
 * Flow:   Threads and their turns live in localStorage so a demo survives a reload; sending a
 *         message appends a user turn and an empty assistant turn, then every SSE event mutates
 *         that assistant turn (tokens append text, tool events fill the tool cards, context
 *         events feed the chunk index the source links open).
 */
import { useEffect, useMemo, useRef, useState } from 'react'

import { streamChat, type ChatEvent } from '../api/chat'
import { useCourses, useHealth, useStrategies } from '../api/hooks'
import type { ChatSource, Chunk } from '../api/types'
import { ChunkPanel } from '../components/ChunkPanel'
import { Markdown } from '../components/Markdown'
import { Badge, Button, Field, Panel, Select, Spinner } from '../components/ui'

const THREADS_KEY = 'sop.threads'
const TURNS_KEY = 'sop.turns'

const QUICK_ACTIONS = [
  { label: 'Generate a lab', prompt: 'Generate a lab like L5 about FIFO, with three stages.' },
  { label: 'Explain a topic', prompt: 'Explain epoll vs select and when each one is preferable.' },
  { label: 'Visualize', prompt: 'Visualize fork/exec/wait as a mermaid diagram.' },
  { label: 'Compare labs', prompt: 'Which labs cover signals, and how do their tasks differ?' },
]

interface Thread {
  id: string
  title: string
}

interface ToolCallView {
  name: string
  args: Record<string, unknown>
  done: boolean
  preview?: string
  sources: ChatSource[]
}

interface ChatTurn {
  id: string
  role: 'user' | 'assistant'
  content: string
  tools: ToolCallView[]
  error?: string
  streaming?: boolean
}

function newId(): string {
  return Math.random().toString(36).slice(2, 10)
}

function load<T>(key: string, fallback: T): T {
  try {
    const stored = localStorage.getItem(key)
    return stored ? (JSON.parse(stored) as T) : fallback
  } catch {
    return fallback
  }
}

function ToolCard({ tool, onOpenChunk }: { tool: ToolCallView; onOpenChunk: (id: string) => void }) {
  return (
    <div className="my-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-xs dark:border-slate-800 dark:bg-slate-950">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={tool.done ? 'ok' : 'warn'}>{tool.done ? 'tool' : 'running'}</Badge>
        <span className="font-mono font-medium">{tool.name}</span>
        <span className="truncate font-mono text-[11px] text-slate-500">
          {JSON.stringify(tool.args)}
        </span>
      </div>
      {tool.preview && (
        <p className="mt-1.5 line-clamp-3 text-[11px] text-slate-600 dark:text-slate-400">
          {tool.preview}
        </p>
      )}
      {tool.sources.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {tool.sources.map((source, index) => (
            <button
              key={`${source.chunk_id}-${index}`}
              type="button"
              onClick={() => source.chunk_id && onOpenChunk(source.chunk_id)}
              className="rounded-md bg-white px-1.5 py-0.5 font-mono text-[10px] text-indigo-600 ring-1 ring-slate-200 hover:ring-indigo-400 dark:bg-slate-900 dark:text-indigo-400 dark:ring-slate-700"
              title={`${source.document_id ?? ''} ${source.section_id ?? ''}`}
            >
              {source.section_id ?? source.chunk_id ?? 'chunk'}
              {source.score !== null && source.score !== undefined
                ? ` ${source.score.toFixed(2)}`
                : ''}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function ChatPage() {
  const health = useHealth()
  const strategies = useStrategies()
  const courses = useCourses()

  const [threads, setThreads] = useState<Thread[]>(() =>
    load<Thread[]>(THREADS_KEY, [{ id: newId(), title: 'New conversation' }]),
  )
  const [activeId, setActiveId] = useState<string>(() => threads[0]?.id ?? newId())
  const [turnsByThread, setTurnsByThread] = useState<Record<string, ChatTurn[]>>(() =>
    load<Record<string, ChatTurn[]>>(TURNS_KEY, {}),
  )
  const [draft, setDraft] = useState('')
  const [course, setCourse] = useState('')
  const [labId, setLabId] = useState('')
  const [rag, setRag] = useState('')
  const [llm, setLlm] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [chunkIndex, setChunkIndex] = useState<Record<string, Chunk>>({})
  const [openChunk, setOpenChunk] = useState<Chunk | null>(null)

  const abort = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  const turns = useMemo(() => turnsByThread[activeId] ?? [], [turnsByThread, activeId])

  useEffect(() => localStorage.setItem(THREADS_KEY, JSON.stringify(threads)), [threads])
  useEffect(() => localStorage.setItem(TURNS_KEY, JSON.stringify(turnsByThread)), [turnsByThread])
  useEffect(() => bottom.current?.scrollIntoView({ behavior: 'smooth' }), [turns])

  const labs = useMemo(() => {
    const all = (courses.data?.courses ?? []).filter(
      (entry) => !course || entry.course === course,
    )
    return all.flatMap((entry) => entry.labs.map((lab) => lab.id))
  }, [courses.data, course])

  const patchLast = (update: (turn: ChatTurn) => ChatTurn) =>
    setTurnsByThread((previous) => {
      const existing = previous[activeId] ?? []
      if (existing.length === 0) return previous
      const last = existing[existing.length - 1]
      if (!last) return previous
      return { ...previous, [activeId]: [...existing.slice(0, -1), update(last)] }
    })

  const onEvent = (event: ChatEvent) => {
    switch (event.type) {
      case 'token':
        patchLast((turn) => ({ ...turn, content: turn.content + event.text }))
        break
      case 'message':
        patchLast((turn) => ({ ...turn, content: turn.content + event.text }))
        break
      case 'tool_start':
        patchLast((turn) => ({
          ...turn,
          tools: [...turn.tools, { name: event.name, args: event.args, done: false, sources: [] }],
        }))
        break
      case 'tool_end':
        patchLast((turn) => ({
          ...turn,
          tools: turn.tools.map((tool) =>
            tool.name === event.name && !tool.done
              ? { ...tool, done: true, preview: event.output_preview, sources: event.sources }
              : tool,
          ),
        }))
        break
      case 'context':
        setChunkIndex((previous) => {
          const next = { ...previous }
          for (const scored of event.context.chunks) next[scored.chunk.id] = scored.chunk
          return next
        })
        break
      case 'error':
        patchLast((turn) => ({ ...turn, error: event.message }))
        break
      case 'done':
        patchLast((turn) => ({ ...turn, streaming: false }))
        break
    }
  }

  const send = async (text: string) => {
    const message = text.trim()
    if (!message || streaming) return
    setDraft('')
    setStreaming(true)
    setTurnsByThread((previous) => ({
      ...previous,
      [activeId]: [
        ...(previous[activeId] ?? []),
        { id: newId(), role: 'user', content: message, tools: [] },
        { id: newId(), role: 'assistant', content: '', tools: [], streaming: true },
      ],
    }))
    setThreads((previous) =>
      previous.map((thread) =>
        thread.id === activeId && thread.title === 'New conversation'
          ? { ...thread, title: message.slice(0, 40) }
          : thread,
      ),
    )
    const controller = new AbortController()
    abort.current = controller
    try {
      await streamChat(
        {
          message,
          thread_id: activeId,
          course: course || null,
          lab_id: labId || null,
          rag: rag || null,
          llm: llm || null,
        },
        onEvent,
        controller.signal,
      )
    } catch (cause) {
      patchLast((turn) => ({
        ...turn,
        streaming: false,
        error: cause instanceof Error ? cause.message : String(cause),
      }))
    } finally {
      setStreaming(false)
      abort.current = null
    }
  }

  const startThread = () => {
    const thread = { id: newId(), title: 'New conversation' }
    setThreads((previous) => [thread, ...previous])
    setActiveId(thread.id)
  }

  const kinds = strategies.data?.kinds ?? {}

  return (
    <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
      <Panel
        title="Threads"
        actions={
          <Button variant="ghost" onClick={startThread}>
            + new
          </Button>
        }
      >
        <ul className="space-y-1">
          {threads.map((thread) => (
            <li key={thread.id} className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setActiveId(thread.id)}
                className={`min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-left text-xs ${
                  thread.id === activeId
                    ? 'bg-indigo-600 text-white'
                    : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
                title={thread.id}
              >
                {thread.title}
              </button>
              <button
                type="button"
                title="delete thread"
                className="px-1 text-xs text-slate-400 hover:text-rose-500"
                onClick={() => {
                  setThreads((previous) => previous.filter((entry) => entry.id !== thread.id))
                  setTurnsByThread((previous) => {
                    const next = { ...previous }
                    delete next[thread.id]
                    return next
                  })
                }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      <div className="flex min-w-0 flex-col gap-4">
        <Panel title="Agent">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Field label="course">
              <Select
                value={course}
                onChange={(value) => {
                  setCourse(value)
                  setLabId('')
                }}
                options={(courses.data?.courses ?? []).map((entry) => entry.course)}
                allowEmpty
                emptyLabel="all courses"
              />
            </Field>
            <Field label="lab">
              <Select value={labId} onChange={setLabId} options={labs} allowEmpty emptyLabel="any lab" />
            </Field>
            <Field label="rag">
              <Select
                value={rag}
                onChange={setRag}
                options={kinds.rag ?? []}
                allowEmpty
                emptyLabel={`default (${health.data?.rag ?? '?'})`}
              />
            </Field>
            <Field label="llm">
              <Select
                value={llm}
                onChange={setLlm}
                options={kinds.llm ?? []}
                allowEmpty
                emptyLabel={`default (${health.data?.llm_provider ?? '?'})`}
              />
            </Field>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.label}
                type="button"
                onClick={() => setDraft(action.prompt)}
                className="rounded-full border border-slate-300 px-2.5 py-1 text-[11px] text-slate-600 hover:border-indigo-400 hover:text-indigo-600 dark:border-slate-700 dark:text-slate-300"
              >
                {action.label}
              </button>
            ))}
          </div>
          {health.data && !health.data.agent_available && (
            <p className="mt-3 text-[11px] text-amber-600 dark:text-amber-400">
              The agent graph is not available yet; the chat endpoint will answer 503.
            </p>
          )}
        </Panel>

        <Panel className="min-h-[50vh]" title="Conversation">
          {turns.length === 0 && (
            <p className="text-sm text-slate-500">
              Ask about a lab, a system call or request a new assignment.
            </p>
          )}
          <div className="space-y-4">
            {turns.map((turn) => (
              <div key={turn.id} className={turn.role === 'user' ? 'flex justify-end' : ''}>
                <div
                  className={
                    turn.role === 'user'
                      ? 'max-w-[85%] rounded-2xl bg-indigo-600 px-3 py-2 text-sm whitespace-pre-wrap text-white'
                      : 'max-w-full'
                  }
                >
                  {turn.role === 'assistant' && (
                    <>
                      {turn.tools.map((tool, index) => (
                        <ToolCard
                          key={`${tool.name}-${index}`}
                          tool={tool}
                          onOpenChunk={(id) => setOpenChunk(chunkIndex[id] ?? null)}
                        />
                      ))}
                      {turn.content ? (
                        <Markdown content={turn.content} />
                      ) : turn.streaming ? (
                        <Spinner label="thinking" />
                      ) : null}
                      {turn.error && (
                        <p className="mt-1 font-mono text-[11px] text-rose-600 dark:text-rose-400">
                          {turn.error}
                        </p>
                      )}
                    </>
                  )}
                  {turn.role === 'user' && turn.content}
                </div>
              </div>
            ))}
            <div ref={bottom} />
          </div>
        </Panel>

        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            void send(draft)
          }}
        >
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send(draft)
              }
            }}
            rows={2}
            placeholder="Ask the assistant…  (Enter to send, Shift+Enter for a new line)"
            className="flex-1 resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900"
          />
          {streaming ? (
            <Button variant="ghost" onClick={() => abort.current?.abort()}>
              stop
            </Button>
          ) : (
            <Button type="submit" disabled={draft.trim().length === 0}>
              send
            </Button>
          )}
        </form>
      </div>

      <ChunkPanel chunk={openChunk} onClose={() => setOpenChunk(null)} />
    </div>
  )
}

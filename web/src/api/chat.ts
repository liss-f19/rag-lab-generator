/**
 * Role:   Server-Sent Events client for the POST /api/chat endpoint.
 * Input:  A ChatRequest body, a callback per event and an AbortSignal.
 * Output: Calls onEvent for every token / message / tool_start / tool_end / context / error /
 *         done frame the agent emits; throws ApiError when the turn cannot start.
 * Flow:   POSTs the body, reads the response body as a stream, splits it on the blank line that
 *         terminates an SSE frame, parses the `event:` and `data:` lines and dispatches a
 *         discriminated union so the chat page never touches raw text.
 */
import { ApiError } from './client'
import type { ChatRequest, ChatSource, RetrievedContext } from './types'

export type ChatEvent =
  | { type: 'token'; text: string }
  | { type: 'message'; text: string }
  | { type: 'tool_start'; name: string; args: Record<string, unknown> }
  | { type: 'tool_end'; name: string; output_preview: string; sources: ChatSource[] }
  | { type: 'context'; name: string; context: RetrievedContext }
  | { type: 'error'; message: string }
  | { type: 'done'; thread_id: string }

const FRAME_SEPARATOR = /\r?\n\r?\n/

export async function streamChat(
  body: ChatRequest,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, await errorDetail(response))
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += value
    const frames = buffer.split(FRAME_SEPARATOR)
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const event = parseFrame(frame)
      if (event) onEvent(event)
    }
  }
  const last = parseFrame(buffer)
  if (last) onEvent(last)
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      return String((body as { detail: unknown }).detail)
    }
  } catch {
    // the backend answered with something other than json
  }
  return `${response.status} ${response.statusText}`
}

function parseFrame(frame: string): ChatEvent | null {
  let name = 'message'
  const data: string[] = []
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith('event:')) name = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trim())
  }
  if (data.length === 0) return null
  let payload: Record<string, unknown>
  try {
    payload = JSON.parse(data.join('\n')) as Record<string, unknown>
  } catch {
    return null
  }
  return toEvent(name, payload)
}

function toEvent(name: string, payload: Record<string, unknown>): ChatEvent | null {
  switch (name) {
    case 'token':
      return { type: 'token', text: String(payload.text ?? '') }
    case 'message':
      return { type: 'message', text: String(payload.text ?? '') }
    case 'tool_start':
      return {
        type: 'tool_start',
        name: String(payload.name ?? ''),
        args: (payload.args as Record<string, unknown>) ?? {},
      }
    case 'tool_end':
      return {
        type: 'tool_end',
        name: String(payload.name ?? ''),
        output_preview: String(payload.output_preview ?? ''),
        sources: (payload.sources as ChatSource[]) ?? [],
      }
    case 'context':
      return {
        type: 'context',
        name: String(payload.name ?? ''),
        context: payload.context as RetrievedContext,
      }
    case 'error':
      return { type: 'error', message: String(payload.message ?? 'unknown error') }
    case 'done':
      return { type: 'done', thread_id: String(payload.thread_id ?? '') }
    default:
      return null
  }
}

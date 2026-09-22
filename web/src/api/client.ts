/**
 * Role:   Thin typed HTTP client for the FastAPI backend.
 * Input:  Endpoint paths and request bodies from the query hooks and the pages.
 * Output: Parsed JSON typed with the interfaces of api/types.ts; ApiError on failure.
 * Flow:   request() issues fetch against the /api prefix (proxied by Vite in development),
 *         turns a non-2xx answer into an ApiError carrying the backend `detail` string, and
 *         the exported helpers name one endpoint each.
 */
import type {
  ChatHistory,
  CompareRequest,
  CompareResponse,
  CoursesResponse,
  EvalRuns,
  GraphStats,
  Health,
  LabDetail,
  NodeChunks,
  RetrieveRequest,
  RetrieveResponse,
  Strategies,
  Subgraph,
} from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    throw new ApiError(response.status, await detailOf(response))
  }
  return (await response.json()) as T
}

async function detailOf(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      return typeof detail === 'string' ? detail : JSON.stringify(detail)
    }
  } catch {
    // fall through to the status line below
  }
  return `${response.status} ${response.statusText}`
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

export const api = {
  health: () => request<Health>('/api/health'),
  strategies: () => request<Strategies>('/api/strategies'),
  courses: () => request<CoursesResponse>('/api/courses'),
  lab: (course: string, slug: string) =>
    request<LabDetail>(`/api/labs/${encodeURIComponent(course)}/${encodeURIComponent(slug)}`),
  fileUrl: (course: string, slug: string, path: string) =>
    `/api/labs/${encodeURIComponent(course)}/${encodeURIComponent(slug)}/files/${path
      .split('/')
      .map(encodeURIComponent)
      .join('/')}`,
  retrieve: (body: RetrieveRequest) => post<RetrieveResponse>('/api/retrieve', body),
  compare: (body: CompareRequest) => post<CompareResponse>('/api/retrieve/compare', body),
  graphSearch: (q: string) => request<Subgraph>(`/api/graph/search?q=${encodeURIComponent(q)}`),
  graphNeighbors: (nodeId: string, hops: number) =>
    request<Subgraph>(`/api/graph/neighbors?node_id=${encodeURIComponent(nodeId)}&hops=${hops}`),
  graphStats: () => request<GraphStats>('/api/graph/stats'),
  nodeChunks: (nodeId: string) =>
    request<NodeChunks>(`/api/graph/chunks?node_id=${encodeURIComponent(nodeId)}`),
  chatHistory: (threadId: string) =>
    request<ChatHistory>(`/api/chat/${encodeURIComponent(threadId)}`),
  evalRuns: () => request<EvalRuns>('/api/eval/runs'),
}

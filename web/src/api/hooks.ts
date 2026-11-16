/**
 * Role:   TanStack Query hooks wrapping the api client.
 * Input:  Route parameters and user selections from the pages.
 * Output: Typed query results with caching, retries disabled for the 503-prone routes.
 * Flow:   One hook per endpoint; health polls every 20 seconds so the top bar reflects the
 *         backend coming up, the corpus queries are cached indefinitely for the session.
 */
import { useQuery } from '@tanstack/react-query'

import { api } from './client'

const MINUTE = 60_000

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 20_000, retry: 1 })
}

export function useStrategies() {
  return useQuery({ queryKey: ['strategies'], queryFn: api.strategies, staleTime: 10 * MINUTE })
}

export function useCourses() {
  return useQuery({ queryKey: ['courses'], queryFn: api.courses, staleTime: 5 * MINUTE })
}

export function useLab(course: string | undefined, slug: string | undefined) {
  return useQuery({
    queryKey: ['lab', course, slug],
    queryFn: () => api.lab(course as string, slug as string),
    enabled: Boolean(course && slug),
    staleTime: 5 * MINUTE,
  })
}

export function useGraphStats() {
  return useQuery({ queryKey: ['graph', 'stats'], queryFn: api.graphStats, retry: false })
}

export function useGraphSearch(query: string) {
  return useQuery({
    queryKey: ['graph', 'search', query],
    queryFn: () => api.graphSearch(query),
    enabled: query.trim().length > 1,
    retry: false,
  })
}

export function useGraphNeighbors(nodeId: string | null, hops: number) {
  return useQuery({
    queryKey: ['graph', 'neighbors', nodeId, hops],
    queryFn: () => api.graphNeighbors(nodeId as string, hops),
    enabled: Boolean(nodeId),
    retry: false,
  })
}

export function useNodeChunks(nodeId: string | null) {
  return useQuery({
    queryKey: ['graph', 'chunks', nodeId],
    queryFn: () => api.nodeChunks(nodeId as string),
    enabled: Boolean(nodeId),
    retry: false,
  })
}

export function useEvalRuns() {
  return useQuery({ queryKey: ['eval', 'runs'], queryFn: api.evalRuns, retry: false })
}

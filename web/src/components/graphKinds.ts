/**
 * Role:   Color of every knowledge-graph node kind.
 * Input:  none
 * Output: KIND_COLORS, a hex color per NodeKind value of models.py.
 * Flow:   Kept outside the components so both the graph canvas and the details panel read the
 *         same palette without breaking fast refresh.
 */
export const KIND_COLORS: Record<string, string> = {
  course: '#0ea5e9',
  lab: '#6366f1',
  section: '#14b8a6',
  task: '#22c55e',
  api_function: '#f59e0b',
  concept: '#ec4899',
  lecture: '#a855f7',
  code_file: '#94a3b8',
}

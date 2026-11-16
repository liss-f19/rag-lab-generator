/**
 * Role:   TypeScript mirror of the pydantic schemas served by the FastAPI backend.
 * Input:  none (pure type declarations).
 * Output: Interfaces imported by the api client, the hooks and every page.
 * Flow:   One interface per response model of src/rag_lab_generator/api/schemas.py plus the
 *         domain models it embeds (LabDocument, RetrievedContext); field names match the JSON.
 */

export interface Health {
  version: string
  llm_provider: string
  llm_model: string
  embedding_provider: string
  rag: string
  searcher: string
  chunker: string
  retrieval_k: number
  data_dir: string
  db_reachable: boolean
  corpus_present: boolean
  agent_available: boolean
  graph_available: boolean
  strategies: Record<string, string[]>
}

export interface Strategies {
  kinds: Record<string, string[]>
  defaults: Record<string, string>
}

export interface LabSummary {
  id: string
  course: string
  slug: string
  title: string
  number: string
  n_tasks: number
  n_sections: number
  n_files: number
  has_summary: boolean
}

export interface CourseSummary {
  course: string
  n_labs: number
  labs: LabSummary[]
}

export interface CoursesResponse {
  data_dir: string
  corpus_present: boolean
  courses: CourseSummary[]
}

export interface Section {
  id: string
  title: string
  level: number
  order: number
  text: string
  code_refs: string[]
  parent_id: string | null
}

export interface Stage {
  n: number
  text: string
}

export interface Task {
  id: string
  title: string
  statement: string
  stages: Stage[]
  solution_refs: string[]
  attachments: string[]
  notes: string
  source_url: string | null
}

export interface CodeFile {
  ref: string
  lang: string
  content: string
  source_url: string | null
}

export interface Reference {
  url: string
  title: string
}

export interface LabDocument {
  id: string
  course: string
  kind: string
  title: string
  lang: string
  source_url: string | null
  local_path: string | null
  lab_id: string | null
  sections: Section[]
  metadata: Record<string, unknown>
  number: string
  slug: string
  topics: string[]
  tasks: Task[]
  code_files: CodeFile[]
  references: Reference[]
}

export interface LabFile {
  path: string
  group: string
  size: number
  media_type: string
}

export interface LabDetail {
  lab: LabDocument
  summary: string | null
  manifest: Record<string, unknown> | null
  files: LabFile[]
}

export interface Chunk {
  id: string
  document_id: string
  course: string
  lab_id: string | null
  kind: string
  strategy: string
  idx: number
  text: string
  char_count: number
  parent_id: string | null
  section_id: string | null
  metadata: Record<string, unknown>
}

export interface ScoredChunk {
  chunk: Chunk
  score: number
  source: string
}

export interface RetrievedContext {
  query: string
  rag: string
  chunks: ScoredChunk[]
  trace: Record<string, unknown>
}

export interface ResolvedConfig {
  rag: string
  searcher: string
  strategy: string
  embedder: string
  k: number
}

export interface RetrieveRequest {
  query: string
  rag?: string
  searcher?: string
  strategy?: string
  embedder?: string
  k?: number
  course?: string | null
  lab_id?: string | null
  kinds?: string[] | null
}

export interface RetrieveResponse {
  config: ResolvedConfig
  latency_ms: number
  context: RetrievedContext
}

export interface CompareConfig {
  rag: string
  searcher: string
}

export interface CompareRequest {
  query: string
  k?: number
  strategy?: string
  embedder?: string
  course?: string | null
  lab_id?: string | null
  configs: CompareConfig[]
}

export interface CompareResult {
  config: ResolvedConfig
  latency_ms: number
  context: RetrievedContext | null
  error: string | null
}

export interface CompareResponse {
  query: string
  results: CompareResult[]
}

export interface GraphNode {
  id: string
  kind: string
  label: string
  course: string | null
  lab_id: string | null
  document_id: string | null
  chunk_ids: string[]
  degree: number
  hops: number | null
}

export interface GraphEdge {
  src: string
  dst: string
  kind: string
  weight: number
}

export interface Subgraph {
  center: string | null
  hops: number
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphStats {
  counts: Record<string, number>
}

export interface ChunkPreview {
  id: string
  document_id: string
  lab_id: string | null
  kind: string
  section_id: string | null
  text: string
}

export interface NodeDescription {
  text: string
  model: string
  generated_at: string
}

export interface NodeSourceLocation {
  chunk_id: string
  label: string
  kind: string
}

export interface NodeSource {
  document_id: string
  title: string
  kind: string
  course: string
  lab_id: string | null
  slug: string | null
  locations: NodeSourceLocation[]
}

export interface NodeChunks {
  node_id: string
  description: NodeDescription | null
  sources: NodeSource[]
  chunks: ChunkPreview[]
}

export interface ChatSource {
  chunk_id: string | null
  document_id: string | null
  lab_id: string | null
  section_id: string | null
  kind: string | null
  score: number | null
}

export interface ChatRequest {
  message: string
  thread_id: string
  course?: string | null
  lab_id?: string | null
  llm?: string | null
  rag?: string | null
}

export interface ChatMessageOut {
  role: string
  content: string
  tool_calls: { name: string; args: Record<string, unknown> }[]
}

export interface ChatHistory {
  thread_id: string
  messages: ChatMessageOut[]
}

export interface EvalCsvFile {
  name: string
  path: string
  columns: string[]
  rows: Record<string, string>[]
}

export interface EvalDbRun {
  id: number
  created_at: string
  config: Record<string, unknown>
  metrics: Record<string, unknown>
}

export interface EvalRuns {
  results_dir: string
  db_reachable: boolean
  files: EvalCsvFile[]
  db_runs: EvalDbRun[]
}

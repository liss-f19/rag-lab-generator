# Functional Requirements

These requirements describe the intended behavior of the RAG Lab Generator. They are derived from the project proposal and use-case diagram; they do not imply that the functionality is already implemented. `Shall` denotes a required capability. Research and comparative-evaluation functions are optional in the standard instructor workflow.

## 1. Source and Corpus Management

**FR-01 — Source document management.** The system shall allow an authorized user to add, inspect, update metadata for, and remove course source documents.

**FR-02 — Supported formats.** The system shall ingest documents in PDF, HTML, plain-text (TXT), and Markdown formats, and shall report an actionable error when a file cannot be processed.

**FR-03 — Text extraction.** For each successfully ingested document, the system shall extract and retain searchable text associated with that document's source identifier.

**FR-04 — Metadata.** The system shall store available metadata for each source document, including knowledge-base type, course, document type, topic, version, learning outcomes, difficulty level, and authority level.

**FR-05 — Separate knowledge bases.** The system shall maintain distinct primary and supplementary knowledge bases and identify each source and indexed fragment by its knowledge-base type.

**FR-06 — Corpus preparation.** The system shall allow users to prepare and update searchable indexes from ingested documents, including segmenting extracted text and generating embeddings for indexed fragments.

**FR-07 — Fragment traceability.** Each indexed fragment shall retain its source-document identifier and retrievable text excerpt so that retrieved evidence can be traced to its source.

**FR-08 — Persistent project data.** The system shall persist source documents, extracted text, metadata, embeddings and indexes, generated assignments, claim-to-evidence links, benchmark requests, experiment configurations, execution logs, and evaluation results.

**FR-09 — Closed corpus.** The system shall retrieve course evidence only from the configured local knowledge bases and shall not use web search.

## 2. Assignment Configuration and Retrieval

**FR-10 — Assignment configuration.** The system shall allow an instructor to configure a request using topic, learning outcomes, difficulty level, course stage, target competencies, expected duration, and assignment format.

**FR-11 — Retrieval configuration.** The system shall support configurable retrieval parameters and metadata filters for the baseline vector-RAG pipeline.

**FR-12 — Primary-source prioritization.** The system shall prioritize primary-course materials when retrieving evidence for mandatory technical requirements, course-specific tools, learning outcomes, and assessment criteria.

**FR-13 — Supplementary-source limits.** The system shall use supplementary materials only for contextual explanations, prerequisites, hints, or optional extensions; supplementary sources shall not override primary-course materials or establish mandatory course-specific requirements.

**FR-14 — Architecture modes.** The system shall provide a standard mode using the architecture selected through comparative evaluation. If enabled, an administrator or researcher mode shall allow experiments with baseline vector RAG, Hybrid RAG, LightRAG, and GraphRAG.

**FR-15 — Controlled architecture comparison.** In comparative experiments, the system shall use the same corpus, generation model, prompt template, output schema, validation procedure, benchmark, and evaluation protocol across architectures. It shall keep the embedding model, metadata policy, retrieved-context budget, and evaluation environment constant unless a variation is explicitly configured and recorded.

**FR-16 — Graph-informed structuring.** When GraphRAG is enabled, the system shall make relation type, relation weight, and graph-centrality information available to assignment structuring, allowing central or pedagogically essential concepts to inform core tasks and supporting concepts to inform prerequisites, context, hints, or optional extensions.

## 3. Generation, Evidence, and Editing

**FR-17 — Evidence-grounded generation.** The system shall retrieve relevant evidence from the configured knowledge bases and use that evidence when generating an assignment.

**FR-18 — Assignment structure.** A completed assignment shall include a title, prerequisites, objectives, environment and tools, tasks, submission requirements, an assessment rubric, and source evidence.

**FR-19 — Claim and requirement citations.** The system shall link each substantive technical claim and each mandatory task requirement to at least one retrieved source excerpt and its source-document identifier.

**FR-20 — Output validation.** Before presenting an assignment as complete, the system shall validate its output schema, required sections, source-reference validity, and evidence coverage of mandatory requirements.

**FR-21 — Abstention.** If required evidence is unavailable, contradictory, or fails validation, the system shall not present the result as a complete assignment. It shall return a structured response identifying the reason.

**FR-22 — Evidence inspection.** The system shall allow instructors to inspect the retrieved excerpts and source-document identifiers associated with a generated assignment.

**FR-23 — Section editing and regeneration.** The system shall allow instructors to edit assignment sections and request regeneration of individual sections.

**FR-24 — Export.** The system shall allow instructors to export a completed assignment with its source evidence.

## 4. Benchmark and Evaluation Functions

**FR-25 — Held-out benchmark.** In research mode, the system shall store and execute a held-out benchmark containing at least 60 requests. It shall include at least 8 requests in each of these categories: supported single-source, multi-source, requiring permitted supplementary materials, unsupported, conflicting-source, and varied difficulty levels or course stages.

**FR-26 — Benchmark isolation.** The system shall keep the held-out benchmark separate from prompt development, configuration tuning, and architecture selection.

**FR-27 — Experiment reproducibility.** Research mode shall allow experiment configurations, architecture settings, execution logs, and evaluation results to be recorded and reviewed so that evaluated runs can be reproduced.

**FR-28 — Evaluation measures.** The system shall support recording results for retrieval relevance, evidence coverage, citation correctness, unsupported-claim rate, output-schema compliance, learning-outcome alignment, factual correctness, expert-rated usefulness, latency, indexing time, storage use, token usage, and estimated inference cost.

**FR-29 — Expert assessment.** The system shall support recording expert assessments of factual correctness, learning-outcome alignment, and educational usefulness according to a predefined rubric.

**FR-30 — Claim-validation assessment.** The system shall support evaluation on a manually annotated subset of at least 60 generated claims, reporting precision, recall, and F1-score for supported, contradicted, and unsupported classifications, together with unsupported-claim rate before and after validation.

**FR-31 — Architecture selection.** The system shall support selecting the standard architecture using a predefined decision rule that prioritizes grounding, factual correctness, and learning-outcome alignment while considering operational cost.

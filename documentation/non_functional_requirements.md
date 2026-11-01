# Non-Functional Requirements

These requirements describe quality attributes and operational constraints for the intended RAG Lab Generator. They are derived from the project proposal and current repository setup; they do not imply that the functionality is already implemented. `Shall` denotes a required constraint. The proposal does not define numeric service-level targets, so performance and capacity thresholds must be agreed and recorded before final comparative evaluation rather than assumed here.

## 1. Performance and Measurement

**NFR-01 — Comparable evaluation environment.** Performance comparisons between retrieval architectures shall use the same documented hardware, software environment, corpus, generation model, embedding model, and context budget, except for explicitly documented experimental factors.

**NFR-02 — Performance reporting.** Evaluation results shall report generation latency, indexing time, storage use, token usage, and estimated inference cost. The measurement method and relevant environment details shall accompany the reported results.

**NFR-03 — Acceptance thresholds.** Before final evaluation, the project shall define and record any numeric performance or capacity acceptance thresholds, including the workload and environment to which each threshold applies.

## 2. Security and Privacy

**NFR-04 — Secret handling.** API keys and other secrets shall be supplied through protected configuration or environment variables, shall not be committed to source control, and shall not appear in application logs or exported experiment results.

**NFR-05 — Access protection.** The application shall restrict access to course materials, generated assignments, and research data to authenticated users with appropriate permissions for their role.

**NFR-06 — External service boundaries.** The application shall not use web search. Network requests for generation or embeddings shall be limited to explicitly configured model services. Deployment documentation shall identify when prompts, retrieved excerpts, or other course content are transmitted to a configured external provider.

**NFR-07 — Data minimization in logs.** Operational logs shall capture information needed to diagnose failures and measure performance without unnecessarily recording API secrets or full source documents.

## 3. Reliability and Data Integrity

**NFR-08 — Persistent data integrity.** Source documents, metadata, indexes, generated assignments, evidence links, benchmark data, experiment configurations, logs, and results shall remain available after an application process or container restarts, subject to configured storage and retention policies.

**NFR-09 — Safe failure.** Failure of document parsing, indexing, retrieval, generation, or validation shall produce a clear error or structured abstention. Such failures shall not cause an incomplete or unvalidated assignment to be presented as complete.

**NFR-10 — Source consistency.** Citations and evidence links shown to users shall resolve to the corresponding stored source document and excerpt. Removing or replacing a source shall not silently leave evidence presented as valid when it can no longer be resolved.

## 4. Reproducibility and Evaluation Integrity

**NFR-11 — Experiment records.** Each evaluation run shall record the corpus or corpus version, architecture, relevant model identifiers and versions when available, prompt and output-schema versions, retrieval settings, context budget, validation settings, benchmark version, and evaluation environment.

**NFR-12 — Reproducible run procedure.** A documented procedure shall allow a researcher to rerun a recorded experiment configuration. Because generation services may be nondeterministic, reproducibility shall mean reconstructing the recorded setup and inputs, not necessarily obtaining byte-identical generated text.

**NFR-13 — Held-out benchmark protection.** The held-out benchmark and its results shall be access-controlled during development so they are not used for prompt development, configuration tuning, or architecture selection before the benchmark evaluation.

## 5. Usability and Accessibility

**NFR-14 — Understandable status and errors.** The user interface shall show the status of ingestion, indexing, generation, validation, and export operations and provide actionable messages when an operation fails.

**NFR-15 — Inspectable evidence.** Evidence presented with an assignment shall be readable and distinguishable by source and excerpt, so an instructor can verify the relationship between claims, requirements, and course materials.

**NFR-16 — Consistent editing workflow.** Editing or regenerating one assignment section shall make clear which section changed and shall not silently remove or alter unrelated sections or their evidence links.

## 6. Maintainability and Deployability

**NFR-17 — Supported Python runtime.** The application shall support Python 3.12, the runtime currently used by the repository's CI and Docker configuration.

**NFR-18 — Automated quality checks.** Source changes shall be verifiable using the repository's configured automated test and code-quality tooling.

**NFR-19 — Container deployment.** The application shall be deployable using the repository's Docker-based setup and documented configuration, without requiring undocumented machine-specific paths or manual source changes.

**NFR-20 — Configuration separation.** Environment-specific settings, model identifiers, storage locations, and credentials shall be configurable without changing application source code. Safe example configuration shall be provided without real secrets.

**NFR-21 — Deployment documentation.** Deployment instructions shall state required services and configuration, how persistent storage is provided, how model-provider credentials are supplied, and any known limitations affecting course-data privacy or operation.

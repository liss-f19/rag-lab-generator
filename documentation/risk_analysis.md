# 5. Risk Analysis

This analysis applies a strengths, weaknesses, opportunities, and threats (SWOT) structure to the proposed RAG Lab Generator. Likelihood and mitigation activities should be revisited as the corpus, implementation, and evaluation environment are confirmed.

## 5.1 Strengths (Internal)

- **Clearly defined project scope.** The application is designed for closed, course-specific knowledge bases, with no web search and explicit limits on how supplementary materials may be used.
- **Measurable evaluation plan.** The proposal defines a held-out benchmark, expert-assessment rubric, claim-validation measures, and architecture-comparison metrics. This gives implementation and evaluation concrete targets.
- **Existing development foundation.** The repository already has Python 3.12, `uv`, Docker, test, and code-quality tooling configured, providing a reproducible starting environment.
- **Modular project structure.** Separate package areas for ingestion, retrieval, and generation provide clear places to implement and test the principal system components.

## 5.2 Weaknesses (Internal)

- **Limited time to complete the project.**
  - **Value:** Likely.
  - **Source:** The thesis has a fixed delivery period, while the planned work includes corpus preparation, a web application, four retrieval architectures, automated tests, and expert evaluation.
  - **Activities to minimize chances of occurrence:** Create a milestone plan with dependencies and regular reviews. Complete corpus and benchmark preparation early, then deliver a working baseline before implementing comparative architectures. Reserve time for integration, evaluation, and writing; defer nonessential interface features if milestones slip.

- **High implementation and integration effort.**
  - **Value:** Likely.
  - **Source:** The repository currently provides project infrastructure rather than a RAG implementation. The proposal requires multiple retrieval approaches to share a corpus, generation model, prompt, schema, and validation pipeline.
  - **Activities to minimize chances of occurrence:** Define shared interfaces and data contracts first. Implement and test ingestion, indexing, retrieval, generation, and validation in stages. Integrate each additional architecture against the same benchmark and keep experiment settings recorded.

- **Learning and library-integration demands.**
  - **Value:** Likely.
  - **Source:** Vector, hybrid, and graph-based retrieval use different components and may have different dependency, configuration, and debugging requirements.
  - **Activities to minimize chances of occurrence:** Reserve focused research time, build small technical prototypes, use maintained libraries and official documentation, and record compatibility decisions. Validate the required Python and Docker environment early.

- **Corpus and benchmark preparation workload.**
  - **Value:** Likely.
  - **Source:** The evaluation depends on permitted course materials, accurate metadata, a held-out benchmark of at least 60 requests, and a predefined expert rubric.
  - **Activities to minimize chances of occurrence:** Confirm access and permissions for the corpus early. Define inclusion rules and metadata fields before bulk ingestion. Draft benchmark categories and rubric before architecture tuning, then freeze and version the benchmark.

## 5.3 Opportunities (External)

- **Supervisor and subject-matter expert feedback.** Feedback, where available, can improve the corpus inclusion rules, learning-outcome alignment, evaluation rubric, and interpretation of results.
- **Accessible research and software resources.** Academic publications, maintained open-source retrieval libraries, and technical documentation can support implementation and help explain architectural trade-offs.
- **Course materials as a focused case study.** Authorized Operating Systems materials provide a bounded domain for investigating source traceability, primary-versus-supplementary evidence, and assignment usefulness.
- **Reusable research outputs.** The benchmark, evaluation scripts, aggregated results, and deployable application can support future research, portfolio work, or archival in the university repository, subject to permissions and repository requirements.

## 5.4 Threats (External)

- **Access or permission constraints for course materials.**
  - **Value:** Likely until permissions are confirmed.
  - **Source:** Some course documents may have distribution, copyright, or privacy restrictions.
  - **Activities to minimize chances of occurrence:** Confirm permitted use and storage with the relevant rights holders or supervisor before ingestion. Keep a source register, exclude unauthorized documents, and prepare an approved replacement corpus if access is denied.

- **Model-provider availability, pricing, or version changes.**
  - **Value:** Likely.
  - **Source:** Generation and embedding services may change pricing, rate limits, model versions, or API behavior during the project.
  - **Activities to minimize chances of occurrence:** Select and record model versions early, track token use and estimated cost, protect credentials, and run comparisons within a controlled period. Document outages or unavoidable changes and rerun affected experiments when feasible.

- **Dependency and architecture compatibility issues.**
  - **Value:** Likely.
  - **Source:** Retrieval libraries may not support the same Python version, storage backend, model provider, or data structures.
  - **Activities to minimize chances of occurrence:** Verify compatibility with Python 3.12 and Docker in small prototypes. Pin dependency versions, isolate architecture-specific code behind shared interfaces, and document deviations from the common experimental setup.

- **Unreliable or inconsistent source-document extraction.**
  - **Value:** Likely.
  - **Source:** PDFs and HTML documents may contain scanned pages, tables, unusual layouts, or encoding issues that reduce extraction quality.
  - **Activities to minimize chances of occurrence:** Test representative files from each supported format, inspect extracted text before indexing, report parsing failures, and exclude or manually prepare documents that cannot be extracted reliably.

- **Evaluation bias or held-out benchmark contamination.**
  - **Value:** Possible.
  - **Source:** Repeated inspection of benchmark requests or subjective expert ratings can influence prompts, settings, or architecture selection and overstate comparative performance.
  - **Activities to minimize chances of occurrence:** Freeze and version the benchmark before tuning, restrict access to benchmark results during development, apply the same rubric and protocol to all architectures, and retain evaluation records for audit.

- **Hardware and storage limitations.**
  - **Value:** Possible.
  - **Source:** Indexing, graph construction, and comparative runs may exceed the available memory, storage, or compute resources.
  - **Activities to minimize chances of occurrence:** Measure resource use on a representative corpus early, track indexing time and storage use, and document any necessary limits on corpus size, concurrency, or graph configuration.

# QA report — rag-lab-generator

Agent T1 (qa-backend). Run date: 2026-09-21. **Revision 3 — all four builder markers present**
(`B_done` 19:41:53, `D_done` 19:43:33, `A_done` 19:48:13, `C_done` 19:48:53).

**Caveat:** `src/rag_lab_generator/retrieval/graph/extractor.py` has mtime **19:51:25**, i.e. builder
C kept editing after signalling done, and two of C's own unit tests are currently red. The graph
numbers below moved between two runs during this session (857 → 570 `api_function` nodes).

Headline: the pipeline runs end to end and every CLI step exits 0, but **retrieval quality is
broken in three independent places** and the corpus has two empty labs. Static gates are nearly
green (mypy clean, format clean, 1 ruff error).

## 1. Summary table

| Area | Status | blocker | major | minor |
| --- | --- | --- | --- | --- |
| `pytest -m "not integration"` | **FAIL** — 2 failed, 445 passed, 2 skipped | 0 | 1 | 0 |
| `pytest -m integration` | **FAIL** — 17 failed, 119 passed (54.3s) | 0 | — | — |
| `mypy src` (strict) | **PASS** — `Success: no issues found in 81 source files` | 0 | 0 | 0 |
| `ruff check src tests` | **FAIL** — 1 error | 0 | 0 | 1 |
| `ruff format --check src tests` | **PASS** — 147 files already formatted | 0 | 0 | 0 |
| `pre-commit run --all-files` | NOT RUN — builder C still editing | — | — | — |
| `rag-lab --help` command coverage | **PASS** — all 11 planned commands present | 0 | 0 | 0 |
| QA regulation audit | **PASS** | 0 | 0 | 0 |
| QA contract + chunker fuzzing (293 checks) | **PASS** | 0 | 0 | 0 |
| E2E pipeline — all 19 CLI steps exit 0 | **PASS (mechanically)** | 0 | 0 | 0 |
| E2E retrieval **quality** | **FAIL** — lexical, dense/hybrid and graph all miss the target | 1 | 2 | 0 |
| Agent `--course` filter | **FAIL** — silently ignored | 0 | 1 | 0 |
| Corpus data quality | **FAIL** — 10 failures | 0 | 4 | 0 |
| Robustness / error handling | **FAIL** — raw tracebacks on 2 of 3 cases | 0 | 1 | 0 |

Totals: **1 blocker, 9 major, 1 minor.** DB verified: `raglab-db` `Up (healthy)`, port 5433.

## 2. Fixed since revision 1 (for the record)

Agent blocker (`last_generated_lab` returning `None`), mypy 26 → 0, ruff 24 → 1, format 18 → 0,
missing `corpus-stats`, absent `data/raw`, both LangGraph deprecations, all hugo-shortcode leakage,
and the mid-shortcode text truncation I reported in revision 2 — all resolved.

One finding in revision 2 (BUG-17, "mapping.yaml does not mention l0_posix_environment") was **my
own test's false positive**: `mapping.yaml` is keyed by lab_id (`sop1/l0`), not folder slug.
`tests/integration/e2e/test_corpus.py::test_mapping_covers_every_lab` has been corrected to compare
manifest `lab_id`s against mapping keys, and now passes in both directions.

## 3. Verbatim gate results

### 3.1 `uv run pytest -m "not integration"`

```
2 failed, 445 passed, 2 skipped, 136 deselected, 13 warnings in 1.97s
FAILED tests/unit/graph/test_extractor.py::test_api_stoplist_and_two_place_rule
FAILED tests/unit/graph/test_extractor.py::test_task_text_feeds_detection
```

```
>       assert "api:sigaction" in ids
E       AssertionError: assert 'api:sigaction' in {'course:sop1', 'sop1/lab/l2_signals',
E         'sop1/lab/l2_signals#section:a', 'sop1/lab/l2_signals#section:b',
E         'sop1/lab/l2_signals#section:c'}
tests/unit/graph/test_extractor.py:121: AssertionError
```

### 3.2 `uv run pytest -m integration`

```
17 failed, 119 passed, 449 deselected, 6 warnings in 54.30s
FAILED tests/integration/e2e/test_corpus.py::test_manifest_parses_as_lab_manifest[sop1/sanitizers]
FAILED tests/integration/e2e/test_corpus.py::test_manifest_parses_as_lab_manifest[sop2/netcat]
FAILED tests/integration/e2e/test_corpus.py::test_every_ref_points_at_an_existing_file[sop1/sanitizers]
FAILED tests/integration/e2e/test_corpus.py::test_every_ref_points_at_an_existing_file[sop2/netcat]
FAILED tests/integration/e2e/test_corpus.py::test_lab_has_sections_and_tasks[sop1/l0_posix_environment]
FAILED tests/integration/e2e/test_corpus.py::test_lab_has_sections_and_tasks[sop1/sanitizers]
FAILED tests/integration/e2e/test_corpus.py::test_lab_has_sections_and_tasks[sop2/netcat]
FAILED tests/integration/e2e/test_corpus.py::test_src_directory_is_populated[sop1/sanitizers]
FAILED tests/integration/e2e/test_corpus.py::test_src_directory_is_populated[sop2/netcat]
FAILED tests/integration/e2e/test_corpus.py::test_kozlowski_pdfs_have_text_sidecars
FAILED tests/integration/e2e/test_pipeline.py::test_query_finds_the_filesystem_lab[lexical]
FAILED tests/integration/e2e/test_pipeline.py::test_query_finds_the_filesystem_lab[dense]
FAILED tests/integration/e2e/test_pipeline.py::test_query_finds_the_filesystem_lab[hybrid_rrf]
FAILED tests/integration/e2e/test_pipeline.py::test_graph_rag_answers_the_epoll_question
FAILED tests/integration/e2e/test_pipeline.py::test_graph_query_command
FAILED tests/integration/e2e/test_pipeline.py::test_unreachable_database_reports_a_clean_error
FAILED tests/integration/e2e/test_pipeline.py::test_unknown_strategy_reports_available_names
```

XSD validation, 12-lab presence, shortcode absence, summaries and slides/extra checks all pass.

### 3.3 `uv run mypy src`

```
Success: no issues found in 81 source files
```

### 3.4 `uv run ruff check src tests` / `ruff format --check`

```
tests/unit/graph/test_extractor.py:286:101: E501 Line too long (104 > 100)
Found 1 error.

147 files already formatted
```

### 3.5 `uv run rag-lab --help`

All 11 planned commands present (`ingest`, `corpus-stats`, `chunk`, `index`, `query`, `db-init`,
`db-stats`, `graph-build`, `graph-stats`, `graph-query`, `agent`), plus `version`,
`graph-neighbors`, `graph-export`, `chat`, `eval`.

## 4. E2E outputs and timings

All 19 CLI steps exited 0. `EMBEDDING_PROVIDER=fake LLM_PROVIDER=fake`.

| Step | Time |
| --- | --- |
| `corpus-stats` | 1.1s |
| `db-init` | 1.2s |
| `chunk --strategy hierarchical` | 1.9s |
| `chunk --strategy hierarchical` (2nd run, idempotence) | 1.9s |
| `chunk --strategy fixed` | 1.6s |
| `chunk --strategy semantic` | 2.9s |
| `index --embedder fake --strategy hierarchical` | 1.3s |
| `db-stats` | 1.3s |
| `query ... --searcher hybrid_rrf` | 1.3s |
| `query ... --searcher lexical` | 1.3s |
| `query ... --searcher dense` | 1.4s |
| `graph-build --strategy hierarchical` | 8.3s |
| `graph-stats` | 1.3s |
| `graph-query` | 2.1s |
| `query --rag graph` | 1.8s |
| `agent ... --rag vector --course sop2` | 1.9s |
| `agent ... --rag graph --course sop2` | 2.1s |
| `agent "explain what a zombie process is"` | 1.7s |
| `agent "visualize fork exec wait lifecycle"` | 1.5s |

### 4.1 `corpus-stats`

```
                      corpus statistics
┏━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┓
┃ course ┃ kind           ┃ documents ┃ sections ┃     chars ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━┩
│ sop1   │ course_info    │         7 │       34 │    19,019 │
│ sop1   │ external_pdf   │        13 │      300 │   166,476 │
│ sop1   │ lab            │         6 │      107 │   180,437 │
│ sop1   │ lecture_index  │        10 │       42 │    15,702 │
│ sop1   │ lecture_pdf    │        20 │      443 │   290,966 │
│ sop1   │ summary        │         6 │       33 │    45,863 │
│ sop2   │ course_info    │         6 │       30 │    16,000 │
│ sop2   │ external_pdf   │         7 │      254 │    77,814 │
│ sop2   │ lab            │         6 │       63 │   126,832 │
│ sop2   │ lecture_code   │        91 │       91 │   274,099 │
│ sop2   │ lecture_index  │        15 │       60 │    14,905 │
│ sop2   │ lecture_pdf    │        14 │      484 │   319,922 │
│ sop2   │ lecture_slides │        10 │      287 │   124,713 │
│ sop2   │ summary        │         6 │       33 │    47,222 │
├────────┼────────────────┼───────────┼──────────┼───────────┤
│ all    │ all            │       217 │     2261 │ 1,719,970 │
└────────┴────────────────┴───────────┴──────────┴───────────┘
```

### 4.2 Chunk idempotence — PASS

```
run 1: hierarchical: 217 documents -> 5278 chunks (avg 502 chars)
run 2: hierarchical: 217 documents -> 5278 chunks (avg 502 chars)
index: nothing to do: fake/hierarchical is up to date
```

### 4.3 `db-stats`

```
documents 217 | chunks 13632 | embeddings 5374 | nodes 1403 | edges 6391
chunks: fixed 1476 | hierarchical 5278 | semantic 6878
embeddings: bge_m3 96 | fake 5278
```

`bge_m3` has only 96 of 5278 vectors — a partial index left over from a builder experiment. Harmless
but it means `--embedder bge_m3` would silently retrieve from 1.8% of the corpus. Worth clearing.

### 4.4 `query "how to read directory entries with readdir" --searcher lexical` — **BUG-18**

```
│ 0.0590 │ hierarchical:sop1/lecture/w2/IO_1_15:9 │ lecture │ page-10 │ IO_1_15 > page 10 ... │
trace: searcher=lexical  k=8  latency_ms=28.615  n_hits=1  n_parents=0
```

One hit for k=8. No `sop1/l1` chunk at all.

### 4.5 `--searcher hybrid_rrf` / `--searcher dense`

`hybrid_rrf` top-8 contains `sop1/l1:157` at rank 5 but is led by `sop2/lecture/docker/code/mntns.c`
and `external/kozlowski/unix/06-files`. `dense` (fake embedder) is essentially random — expected,
since the fake embedder is hash-based; this is a caveat on the numbers, not a defect in itself.
`trace: searcher=hybrid_rrf k=8 latency_ms=86.735 n_hits=8 n_parents=6`.

### 4.6 `graph-query "how does epoll differ from select"` — **BUG-19**

After the 19:51 extractor rebuild (570 api nodes):

```
│ 1.000 │ hierarchical:external/kozlowski/tcpip/lecture_1:13         │ lecture │ graph_walk │ api:time │
│ 1.000 │ hierarchical:external/kozlowski/tcpip/lecture_4@sop2/l7:10 │ lecture │ graph_walk │ api:time │
│ 1.000 │ hierarchical:external/kozlowski/tcpip/lecture_4@sop2/l7:11 │ lecture │ graph_walk │ api:time │
│ 1.000 │ hierarchical:external/kozlowski/tcpip/lecture_4@sop2/l7:12 │ lecture │ graph_walk │ api:time │
│ 1.000 │ hierarchical:external/kozlowski/tcpip/lecture_4@sop2/l7:13 │ lecture │ graph_walk │ api:time │
│ 1.000 │ hierarchical:external/kozlowski/tcpip/lecture_4@sop2/l7:14 │ lecture │ graph_walk │ api:time │
│ 1.000 │ hierarchical:external/kozlowski/tcpip/lecture_4@sop2/l7:15 │ lecture │ graph_walk │ api:time │
│ 1.000 │ hierarchical:external/kozlowski/tcpip/lecture_4@sop2/l7:16 │ lecture │ graph_walk │ api:time │
seeds=44 activated=716 inner=hybrid_rrf latency_ms=587.208
```

Earlier run (857 api nodes) was worse — eight consecutive chunks of
`external/kozlowski/tcpip/lecture_1`, paths `api:page`, `api:contents`, `api:can`.

### 4.7 `agent "generate a lab about FIFO similar to L5" --llm fake --rag vector --course sop2` — **BUG-20**

```
[fake-llm] Write a new laboratory task for the course sop1 about: generate a lab about FIFO similar to L5.
course: sop1 | difficulty: medium
...
Sources: hierarchical:sop1/lecture/mqueue/IPC_1en_3:15, hierarchical:sop1/l3:2,
hierarchical:external/kozlowski/unix/01-unix:23, hierarchical:sop1/l3:98, hierarchical:sop1/l2:28,
hierarchical:sop1/lecture/w2/POSIX_excerpts:3, hierarchical:sop1/lecture/w7/index:2,
hierarchical:sop1/l0:40, hierarchical:sop1/l0:10, hierarchical:sop1/l2:1, hierarchical:sop1/l3:0,
hierarchical:sop1/l3:96, hierarchical:sop1/lecture/w2/POSIX_excerpts:0, hierarchical:sop1/lecture/w7/index:1
```

`--course sop2` was requested; every source is sop1 and the header says `course: sop1`.

With `--rag graph` the same command retrieves eight consecutive chunks of one unrelated document:

```
Sources: hierarchical:external/kozlowski/unix/00-basics:0, ...:1, ...:10, ...:11, ...:12, ...:13, ...:14, ...:15
```

### 4.8 `agent "explain what a zombie process is" --llm fake` — runs, retrieval off-target

```
[fake-llm] Explain the topic to a student of sop1 who is preparing for the laboratory: explain what a zombie process is
Sources: hierarchical:sop2/lecture/networks/slides:17, hierarchical:sop2/l5:130,
hierarchical:sop2/lecture/vmem/VM_en_4:1, hierarchical:sop2/lecture/networks/index:0,
hierarchical:external/kozlowski/unix/04-streams:2, hierarchical:sop1/lecture/w4/Processes_0:3,
hierarchical:sop2/lecture/networks/code/direct_client_server.sh:2, hierarchical:sop2/l5_5:92, ...
```

Only 1 of 11 sources (`sop1/lecture/w4/Processes_0`) is about processes. `visualize fork exec wait
lifecycle` also exits 0 and produces output.

## 5. Bugs

### BUG-18 — lexical search ANDs every query term, so question-shaped queries return almost nothing (blocker)

* **File:** `src/rag_lab_generator/retrieval/stores/vector_store.py:96-118`
  (`lexical_search` / `_lexical_search`)
* **Repro:**

  ```
  uv run rag-lab query "how to read directory entries with readdir" \
      --rag vector --searcher lexical --strategy hierarchical --embedder fake
  ```

* **Observed:** `n_hits=1`. Proven against the database:

  ```sql
  SELECT websearch_to_tsquery('english','how to read directory entries with readdir');
  -- 'read' & 'directori' & 'entri' & 'readdir'
  SELECT count(*) FROM chunks WHERE strategy='hierarchical' AND text ILIKE '%readdir%';          -- 20
  SELECT count(*) FROM chunks WHERE strategy='hierarchical'
     AND tsv @@ websearch_to_tsquery('english','how to read directory entries with readdir');    -- 1
  SELECT count(*) FROM chunks WHERE strategy='hierarchical'
     AND tsv @@ to_tsquery('english','read | directori | entri | readdir');                      -- 820
  ```

  The chunks that do contain `readdir` include `hierarchical:sop1/l1:2,3,4,12` — precisely the
  expected targets — and none are returned.
* **Expected:** `sop1/l1` chunks in the top results; the lexical leg is the one component that
  should reliably find a literal API name.
* **Severity:** **blocker.** `websearch_to_tsquery` ANDs unquoted terms, so a natural-language
  question of 6 words demands all 6 stems in one chunk. The lexical leg is effectively dead for the
  thesis's entire use case, and because `hybrid_rrf` fuses lexical with dense, half of the hybrid
  searcher contributes a single document. Both the `plainto_tsquery` fallback and the
  `except psycopg.errors.SyntaxError` guard are irrelevant here — neither parser ever raises, and
  `plainto_tsquery` ANDs as well.
* **Suggested fix:** build an OR query over the query stems (`to_tsquery` joined with `||`) and keep
  `ts_rank_cd` for ranking, so chunks matching more terms still rank higher; optionally try the AND
  query first and fall back to OR when it yields fewer than k rows.

### BUG-19 — graph walk returns tied scores and junk API nodes (major)

* **Files:** `src/rag_lab_generator/retrieval/searchers/graph_walk.py`,
  `src/rag_lab_generator/retrieval/graph/extractor.py`
* **Repro:** `uv run rag-lab graph-query "how does epoll differ from select" --embedder fake`
* **Observed:** all eight results score exactly `1.000`, so ordering collapses to lexicographic
  chunk-id order (`:10, :11, :12 …` sorts before `:2`), and every result is reached through
  `api:time` — an "API function" node extracted from the ordinary English word *time*. The earlier
  build reached results through `api:page`, `api:contents` and `api:can`.
* **Expected:** `sop2/l7_sockets_epoll` material, ranked.
* **Severity:** major — GraphRAG is half the thesis's comparison and currently returns arbitrary
  documents with no ranking signal.
* **Suggested fix:** two separate defects. (1) Give the walk a real score — activation mass, hop
  distance or inner-searcher score — instead of a constant; ties currently make `ORDER BY` a
  string sort. (2) Tighten API-function extraction: require a `(` call site plus a stoplist of
  common English words, which is what `test_api_stoplist_and_two_place_rule` is trying to enforce.

### BUG-21 — builder C's own extractor tests are red (major)

* **File:** `tests/unit/graph/test_extractor.py:121` and `test_task_text_feeds_detection`
* **Repro:** `uv run pytest tests/unit/graph/test_extractor.py -q`
* **Observed:** `assert 'api:sigaction' in {...}` — the node set contains only course/lab/section
  nodes; **no `api_function` node is extracted at all** for
  `sigaction(SIGINT, &sa, NULL)` or `pthread_create(&t, NULL, worker, NULL)`.
* **Expected:** `api:sigaction`, `api:pthread_create`.
* **Severity:** major, and it interacts with BUG-19: the stoplist that removes `api:page` and
  `api:can` now also removes genuine API names. `extractor.py` mtime is 19:51:25, after `C_done`
  at 19:48:53, so C signalled completion mid-edit.
* **Suggested fix:** the two-place rule and the stoplist need to be independent — stoplist on the
  identifier, call-site detection on the syntax — rather than one predicate doing both.

### BUG-20 — `agent --course` is silently ignored for lab generation (major)

* **Files:** `src/rag_lab_generator/agent/tools/generate_lab.py:60` and
  `src/rag_lab_generator/agent/tools/context.py:32`
* **Repro:**

  ```
  uv run rag-lab agent "generate a lab about FIFO similar to L5" --llm fake --rag vector --course sop2
  ```

* **Observed:** header reads `course: sop1`, every retrieved source is a sop1 chunk.
* **Expected:** retrieval restricted to sop2 (L5 is a sop2 lab).
* **Root cause:** `generate_lab.py:60` declares `course: Literal["sop1","sop2"] = "sop1"` — a
  non-`None` default. `context.py:32` then resolves
  `course=course or data.get("course")`, and because the tool argument is always truthy the `or`
  short-circuits and the state value carrying `--course sop2` is never read.
* **Severity:** major — a documented CLI flag (`--course  restrict retrieval to sop1 or sop2`) has
  no effect on the flagship command, and it silently degrades output rather than erroring.
* **Suggested fix:** change the default to `None`, exactly as
  `explain_topic.py:39` already does (`course: Literal["sop1","sop2"] | None = None`), and let
  `resolve_filters` fall back to state. Alternatively invert the precedence so explicit CLI state
  wins over the model's guess.

### BUG-22 — CLI dumps raw tracebacks instead of clean errors (major)

* **File:** `src/rag_lab_generator/cli.py` (no top-level exception handler)
* **Repro / observed:**

  1. `DATABASE_URL=postgresql://rag:rag@localhost:5999/raglab uv run rag-lab query "readdir" --strategy hierarchical --embedder fake`
     → full Rich traceback through `psycopg/connection.py:134`, ending in
     `OperationalError: connection failed: connection to server at "::1", port 5999 failed`.
  2. `uv run rag-lab query "readdir" --strategy hierarchical --embedder fake --searcher nonexistent`
     → full Rich traceback through `registry.py:64`, ending in
     `UnknownStrategyError: "no searcher named 'nonexistent'; available: ['dense', 'graph_walk', 'hybrid_rrf', 'lexical']"`.
     The message itself is good; only the traceback is wrong.
  3. `CHUNKER=nonexistent uv run rag-lab agent "generate a lab about FIFO similar to L5" --llm fake --rag vector`
     → **correct behaviour**, one clean line:
     `The knowledge base is unavailable for generate_lab: no chunks indexed for strategy 'nonexistent' (course=sop1, lab=None); run rag-lab ingest, rag-lab chunk and rag-lab index first`
* **Expected:** cases 1 and 2 behave like case 3.
* **Severity:** major — a thesis demo that shows a 40-line traceback when the database is down is a
  bad look, and the agent path proves the project already knows how to do this.
* **Suggested fix:** wrap the Typer app in a handler that catches `psycopg.OperationalError` and
  `UnknownStrategyError`, prints the message and raises `typer.Exit(1)`.
* **Side note:** case 1 also returned **exit code 0** in one of my shell invocations; the CLI must
  exit non-zero on failure or CI will never catch it.

### BUG-13 — `sop1/sanitizers` and `sop2/netcat` are empty labs (major)

* **Observed:** both have `lab.xml` with **no `<task>`**, **no code/solution `ref` attributes**, and
  an **empty `src/`**. Their `manifest.json` parses but carries `sources=[]`.
* **Expected:** content, or explicit exclusion from the 12-lab set.
* **Severity:** major — 2 of the 12 labs the thesis claims to cover.
* **Note:** attachments do work (`sanitizers` → `extra=['tutorial.gcc_make.txt']`; `netcat` →
  slides plus `extra=['lecture_5.pdf','lecture_5.txt']`), so only the lab body is missing. If these
  are genuinely tutorial pages rather than labs, narrow `EXPECTED_LABS` in
  `tests/integration/e2e/test_corpus.py:26` and adjust the thesis wording.

### BUG-14 — `sop1/l0_posix_environment` has no `<task>` elements (major)

L0 has example tasks on the course site. The revision-2 truncation bug is fixed, so this is now a
separate parsing gap rather than a symptom of it.

### BUG-15 — two manifests record no provenance (major)

`data/raw/sop1/sanitizers/manifest.json` and `data/raw/sop2/netcat/manifest.json` have
`sources=[]`: no URL, no sha256, so ingest idempotence cannot be verified for them.

### BUG-16 — 42 of 44 Kozlowski PDFs have no `.txt` sidecar (major)

```
find data/external/kozlowski -name "*.pdf" | wc -l   # 44
find data/external/kozlowski -name "*.txt" | wc -l   # 2
```

Only `unix/tutorial.gcc_make.txt` and `tcpip/lecture_4.txt` exist — the two referenced by lab
mappings. Sidecar generation clearly works; it simply never runs over the unmapped external corpus.
The `external_pdf` rows in `corpus-stats` (13 sop1 + 7 sop2) show mapped PDFs *are* ingested, so
the impact is that unmapped Kozlowski material is invisible to retrieval.

### BUG-23 — stale partial `bge_m3` index (minor)

`db-stats` reports `bge_m3 96` vs `fake 5278` embeddings. `--embedder bge_m3` would silently search
1.8% of the corpus. Suggested fix: `DELETE FROM embeddings WHERE embedder='bge_m3'`, or have
`index` warn when an embedder's coverage is partial.

### BUG-10 — 1 remaining ruff error (minor)

`tests/unit/graph/test_extractor.py:286:101: E501 Line too long (104 > 100)`.

### OBS-01 — `SCHEMA_PATH` breaks outside a source checkout (minor, contract file)

`src/rag_lab_generator/retrieval/stores/postgres.py:25`
(`Path(__file__).resolve().parents[4] / "sql" / "001_schema.sql"`) resolves only in an editable
checkout; a wheel install breaks `db-init` with a confusing `FileNotFoundError`. Suggested fix:
ship the schema as package data and load it via `importlib.resources`.

## 6. What still could not be tested

* **`pre-commit run --all-files`** — not run; builder C was editing `extractor.py` during the
  session and the `ruff --fix` / `ruff-format` hooks would rewrite files underneath it. Expect it
  to fail only on the single E501 above.
* **bge_m3 embedder** — not exercised (2GB download); all runs used the fake embedder. Note that
  this makes the `dense` and `hybrid_rrf` quality figures in §4.5 a lower bound: with real
  embeddings dense would improve, but **BUG-18 would still cripple the lexical half of the hybrid**.
* **`rag-lab ingest` idempotence** — not re-run; A finished late and re-ingesting risked colliding
  with C's ongoing edits. `chunk` idempotence was verified instead (identical 5278 chunks).
* **XML round-trip fuzzing** with `<`, `&`, `]]>` inside CDATA — still unwritten.
* **`eval`, `chat`, `graph-neighbors`, `graph-export`** — outside the agreed test plan, untouched.

## 7. Suggestions, ranked by impact

1. **Fix BUG-18 (lexical AND).** One SQL change in `vector_store.py`, and it is the single largest
   retrieval-quality win available: it repairs the lexical searcher outright and half of
   `hybrid_rrf` with it. Every failing `test_query_finds_the_filesystem_lab` case traces back here.
2. **Fix BUG-20 (`--course` ignored).** A two-character change (`= "sop1"` → `| None = None`) that
   restores a documented flag on the flagship command; `explain_topic.py` already has the right
   shape to copy.
3. **Fix BUG-19 + BUG-21 together (graph walk).** Real scores instead of a constant `1.0`, and an
   API extractor that keeps `sigaction` while dropping `page`/`time`/`can`. Until both land,
   GraphRAG results are not meaningful and the vector-vs-graph comparison in the thesis has no
   basis. C's own red tests are the right specification to build against.
4. **Fix BUG-22 (tracebacks) and the exit code.** Cheap, and it is what a live demo will show.
5. **Decide what `sanitizers` and `netcat` are** (BUG-13/14/15), then either populate them or
   narrow the 12-lab claim so corpus tests and thesis agree.
6. **Generate the remaining Kozlowski sidecars** (BUG-16) and **clear the stale `bge_m3` rows**
   (BUG-23) before any real evaluation run.
7. **Re-run the full pass** once the above land:
   `uv run pytest -m "not integration" -q`, `uv run pytest -m integration -q`,
   `uv run mypy src`, `uv run ruff check src tests`, `uv run pre-commit run --all-files`.

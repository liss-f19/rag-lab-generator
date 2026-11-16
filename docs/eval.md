# Evaluation

How the thesis question - *which retrieval setup gives the generator the best context* - is
answered with numbers. Everything below is produced by `rag_lab_generator.eval`.

```
uv run rag-lab eval-queries                 # list and validate the gold set
uv run rag-lab eval --matrix -k 8           # the 20-configuration matrix
uv run rag-lab eval --config vector/dense/hierarchical/bge_m3   # one configuration
uv run rag-lab eval --matrix --rag graph --chunker hierarchical --hops 1 --hops 2 --hops 3
uv run rag-lab judge results/generated_lab.md --lab sop1/l3
```

## What is measured

One **configuration** is a point of the strategy matrix: `rag / searcher / chunker / embedder`
(plus `hops` on the graph side). The default matrix is
`rag {vector, graph} x searcher {lexical, lexical_idf, dense, hybrid_rrf, hybrid_rrf_idf} x
chunker {hierarchical, fixed} x embedder {bge_m3}` = 20 configurations. Every configuration is
built once, runs the whole gold set on that one instance and is timed per query. Scores are never
compared across rags - only the rank order inside one context is used, because the graph walker
returns unbounded accumulated activation while the vector rags return bounded similarities.

| metric | definition |
| --- | --- |
| `hit@k` | share of queries with at least one relevant chunk in the top k |
| `recall@k` | share of the expected labs and lecture documents that have a chunk in the top k |
| `section_recall@k` | share of the expected `<document>#<section>` sections present in the top k, averaged over the queries that name sections |
| `coverage` | `recall@k` restricted to expected *labs* (lecture documents ignored) |
| `MRR` | mean of `1 / rank of the first relevant chunk` |
| `nDCG@k` | binary-gain nDCG; the ideal ranking is k relevant chunks, which the corpus always contains (every lab owns far more than k chunks) |
| `latency_ms_p50` / `latency_ms_p50_warm` / `latency_ms_first` | median retrieval time per query, the same median without the first query, and the first query alone - it pays for loading the graph edges and the embedding model |
| `context_chars_mean`, `distinct_documents_mean`, `kind_distribution` | shape of the context the generator would receive: size in characters, how many documents it spans and which chunk kinds fill it |
| `support_distribution` | share of retrieved chunks coming from `primary` course material vs `background` reading, read from `documents.metadata->>'support'` |

A chunk counts as **relevant** for an expected lab or document `T` when `chunk.lab_id == T`, or
its `document_id` equals `T`, or its `document_id` starts with `T/`. The `@<lab>` suffix of the
external documents is stripped first. The prefix test uses the `/` boundary on purpose, so
`sop2/l5` never matches `sop2/l5_5`.

**Fair truncation.** GraphRAG returns up to k walked chunks *plus* sibling section chunks
(`graph_rag_sibling`), and the vector RAG appends parent chunks (`parent_expansion`) beyond k.
Both would inflate recall for free, so every context is re-sorted by score and cut to k before a
metric sees it (`runner.top_k`). The `inner_searcher` reported by the walker's trace is stored in
the run configuration, so a `graph` row is always compared against the `vector` row that uses the
same seed searcher.

**Course filter.** Off by default: a query is run against the whole corpus, so retrieving the
other course counts as an error. `--course-filter` restricts retrieval to the `course:` tag of the
query, which is the easier, agent-like setting.

## How the gold set was built

`src/rag_lab_generator/eval/queries.yaml` holds 61 hand-written queries. They were written after
reading `data/raw/<course>/<lab>/lab.xml` (titles, section ids, example task statements) and
`data/raw/<course>/_lectures/<topic>/index.md`, so every expectation points at material that
really exists.

* **Shape.** `id`, `query`, `expected_lab_ids` (1-2), `expected_document_ids` (for lecture
  queries, which have no owning lab), `expected_section_ids` (0-3) and `tags`.
* **Section encoding.** `"<document_id>#<section_id>"`, for example
  `sop1/l1#browsing-a-directory`. That is exactly the `(document_id, section_id)` pair the
  `chunks` table stores, so the metric needs no mapping table. `EvalQuery` in `models.py` has no
  field for document-level expectations, so `eval/queries.py` defines `EvalQueryFile(EvalQuery)`
  which adds `expected_document_ids`.
* **Style.** Student phrasing, mixed on purpose: definitional (*what is a zombie process*),
  how-to (*how to create a FIFO in C*), api (*what does readdir return*), task-style (*example
  task about an epoll server that answers clients with a timeout*), cross-lab (*which laboratory
  introduces mutexes*) and 4 Polish queries, since the students are Polish while the corpus is
  English.
* **Coverage.** Every one of the 12 laboratories is the expected answer of at least 3 queries; 6
  queries target lecture documents instead of labs.

| tag | queries |
| --- | --- |
| `kind:howto` | 28 |
| `kind:definitional` | 15 |
| `kind:api` | 7 |
| `kind:task` | 7 |
| `kind:cross` | 4 |
| `lang:pl` | 4 |
| `course:sop1` / `course:sop2` | 31 / 30 |

`uv run rag-lab eval-queries` re-validates every expected id against the `documents` and `chunks`
tables (falling back to `data/raw` when the database is down) and exits non-zero on an unknown id.

## How to read the results

`run_matrix` writes four things:

* `results/eval_<timestamp>.csv` - one row per configuration, every metric;
* `results/eval_<timestamp>_per_query.csv` - one row per (configuration, query) with `hit`, the
  rank of the first relevant chunk and the latency, for error analysis;
* `results/eval_latest.json` - the `EvalRun` list of the most recent invocation;
* one `eval_runs` row per configuration (`config` and `metrics` as jsonb); the `config` json
  carries the extra fields of `EvalConfigSpec` (`inner_searcher`, `hops`, `filter_course`), so a
  row is self-describing. The two oldest rows of the shared database (`embedder = fake`) are
  plumbing runs of the harness itself, not results.

The console table is sorted by `nDCG@k`. Configurations whose prerequisites are missing are never
an error: a configuration is skipped with a named reason (no chunks for the strategy, no vectors
for the embedder, the graph holds no chunks of the strategy), and a missing `bge_m3` index falls
back to the offline `fake` embedder with a loud warning instead of dropping the row.

## Results

Corpus state: 231 documents, 5569 hierarchical and 1618 fixed chunks, `bge_m3` vectors for
both, graph built on the hierarchical chunks (1131 nodes / 5130 edges). 61 gold queries, `k = 8`,
no course filter, `graph_hops = 2` unless stated otherwise.

### 2026-09-22 re-chunk (read this before quoting the matrix)

The matrix below was measured on the chunk set of 2026-09-21, in which every section above
`chunk_size` was split by the semantic splitter driven by the `fake` embedder: random vectors
started a new piece at almost every paragraph and blank lines *inside* fenced code were split
points too. `sop1/l4#the-alarm-semaphores` was 26 fragments of 98-540 characters, many of them a
lone heading or half a `#define`. That inflates every chunk-level metric: each fragment of the
right lab is a separate "relevant" hit, so nDCG@8 and MRR reward fragmentation, not retrieval.

`chunking/semantic.py` now keeps a fenced block whole and folds pieces below 25 % of
`chunk_size` into their predecessor. Same gold set, same `k = 8`, hierarchical / bge_m3:

| chunk set | chunks | vector/dense nDCG | hit | sect | MRR | chars | vector/hybrid_rrf_idf nDCG | hit | sect | graph/dense h=1 nDCG | hit | sect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 09-21, size 1600, fragmented | 5569 | 0.625 | 0.967 | 0.744 | 0.841 | 6932 | 0.595 | 0.951 | 0.756 | 0.563 | 0.951 | 0.500 |
| 09-22, size 1600, fixed | 3107 | 0.556 | 0.918 | 0.733 | 0.769 | 9349 | 0.583 | 0.951 | 0.733 | 0.528 | 0.885 | 0.616 |
| 09-22, size 1000, fixed (**new default**) | 3719 | 0.611 | 0.951 | 0.686 | 0.788 | 7608 | 0.600 | 0.967 | 0.686 | 0.617 | 0.918 | 0.616 |

Reading: with clean chunks `chunk_size = 1000` recovers the dense numbers within noise of the
fragmented run (0.611 vs 0.625, the standard error is ~0.05), beats it on hybrid and on the
graph, and produces a smaller context. Section recall is the one metric that drops (0.74 -> 0.69):
a merged piece covers more sections, so fewer distinct expected sections fit into 8 chunks. The
default `CHUNK_SIZE` is now 1000; the 20-row matrix and the hop sweep below still describe the
09-21 chunk set and must be re-run (`rag-lab eval --matrix -k 8`) before they go into the thesis.
Raw rows: `results/eval_20260922_10*.csv` (1600) and `results/eval_20260922_11*.csv` (1000).

### The matrix

`results/eval_20260921_203145.csv` holds the 15 rows that the default matrix could run against the
hierarchical graph; the 5 `graph / fixed` rows come from `results/fixed/eval_20260921_202913.csv`,
which was measured with the graph temporarily rebuilt on the fixed chunks (the graph tables hold
one strategy at a time).

| rag | searcher | chunker | hops | hit@8 | recall@8 | sect@8 | cover | MRR | nDCG@8 | p50 ms | 1st ms | chars | docs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vector | dense | hierarchical | - | 0.967 | 0.951 | 0.744 | 0.869 | 0.841 | 0.625 | 69 | 9753 | 6932 | 3.820 |
| vector | hybrid_rrf_idf | hierarchical | - | 0.951 | 0.934 | 0.756 | 0.853 | 0.799 | 0.595 | 106 | 7000 | 10191 | 3.885 |
| vector | hybrid_rrf | hierarchical | - | 0.951 | 0.934 | 0.721 | 0.844 | 0.741 | 0.525 | 95 | 6701 | 12141 | 4.262 |
| vector | dense | fixed | - | 0.951 | 0.943 | 0.000 | 0.853 | 0.743 | 0.510 | 57 | 7100 | 12307 | 5.049 |
| vector | hybrid_rrf_idf | fixed | - | 0.951 | 0.926 | 0.000 | 0.836 | 0.747 | 0.498 | 77 | 7666 | 13397 | 4.934 |
| vector | lexical_idf | hierarchical | - | 0.885 | 0.877 | 0.570 | 0.803 | 0.716 | 0.492 | 35 | 50 | 14051 | 4.131 |
| vector | lexical_idf | fixed | - | 0.869 | 0.853 | 0.000 | 0.779 | 0.647 | 0.456 | 27 | 38 | 15172 | 4.820 |
| vector | hybrid_rrf | fixed | - | 0.934 | 0.918 | 0.000 | 0.828 | 0.708 | 0.451 | 77 | 6640 | 14186 | 5.098 |
| vector | lexical | hierarchical | - | 0.770 | 0.762 | 0.326 | 0.705 | 0.526 | 0.342 | 27 | 31 | 17238 | 4.295 |
| vector | lexical | fixed | - | 0.803 | 0.795 | 0.000 | 0.721 | 0.532 | 0.332 | 20 | 23 | 16475 | 5.311 |
| graph | dense | hierarchical | 2 | 0.836 | 0.820 | 0.046 | 0.811 | 0.481 | 0.270 | 101 | 6210 | 18014 | 5.853 |
| graph | lexical_idf | fixed | 2 | 0.574 | 0.557 | 0.000 | 0.533 | 0.421 | 0.267 | 67 | 221 | 20755 | 5.066 |
| graph | lexical | fixed | 2 | 0.541 | 0.525 | 0.000 | 0.500 | 0.398 | 0.261 | 61 | 113 | 21405 | 4.754 |
| graph | hybrid_rrf_idf | hierarchical | 2 | 0.787 | 0.770 | 0.046 | 0.746 | 0.474 | 0.258 | 138 | 7107 | 18409 | 5.705 |
| graph | lexical_idf | hierarchical | 2 | 0.705 | 0.689 | 0.000 | 0.680 | 0.471 | 0.250 | 71 | 211 | 20203 | 5.361 |
| graph | hybrid_rrf | fixed | 2 | 0.623 | 0.607 | 0.000 | 0.582 | 0.398 | 0.248 | 110 | 6530 | 20400 | 5.147 |
| graph | hybrid_rrf_idf | fixed | 2 | 0.623 | 0.607 | 0.000 | 0.582 | 0.380 | 0.246 | 115 | 6934 | 19649 | 5.328 |
| graph | dense | fixed | 2 | 0.623 | 0.607 | 0.000 | 0.582 | 0.373 | 0.237 | 88 | 6097 | 19860 | 5.279 |
| graph | hybrid_rrf | hierarchical | 2 | 0.689 | 0.672 | 0.023 | 0.664 | 0.414 | 0.211 | 125 | 6155 | 19159 | 5.738 |
| graph | lexical | hierarchical | 2 | 0.574 | 0.557 | 0.000 | 0.549 | 0.320 | 0.199 | 63 | 136 | 21443 | 5.295 |

### Hop sweep (graph, hierarchical)

`results/hops/eval_20260921_202034.csv`.

| rag | searcher | chunker | hops | hit@8 | recall@8 | sect@8 | cover | MRR | nDCG@8 | p50 ms | 1st ms | chars | docs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| graph | dense | hierarchical | 1 | 0.951 | 0.926 | 0.500 | 0.844 | 0.747 | 0.563 | 87.750 | 11916.107 | 10193.147 | 4.049 |
| graph | hybrid_rrf_idf | hierarchical | 1 | 0.885 | 0.869 | 0.454 | 0.795 | 0.713 | 0.538 | 120.263 | 7972.554 | 10336.885 | 3.984 |
| graph | hybrid_rrf | hierarchical | 1 | 0.803 | 0.787 | 0.302 | 0.713 | 0.623 | 0.470 | 109.087 | 6975.068 | 11507.147 | 3.902 |
| graph | lexical_idf | hierarchical | 1 | 0.836 | 0.828 | 0.314 | 0.754 | 0.627 | 0.452 | 54.554 | 105.850 | 12069.803 | 3.688 |
| graph | lexical | hierarchical | 1 | 0.574 | 0.557 | 0.221 | 0.500 | 0.397 | 0.316 | 46.929 | 128.608 | 14895.574 | 3.229 |
| graph | dense | hierarchical | 2 | 0.836 | 0.820 | 0.046 | 0.811 | 0.481 | 0.270 | 103.704 | 7465.932 | 18013.885 | 5.853 |
| graph | hybrid_rrf_idf | hierarchical | 2 | 0.787 | 0.770 | 0.046 | 0.746 | 0.474 | 0.258 | 136.715 | 7301.188 | 18409.016 | 5.705 |
| graph | lexical_idf | hierarchical | 2 | 0.705 | 0.689 | 0.000 | 0.680 | 0.471 | 0.250 | 70.920 | 122.393 | 20203.377 | 5.361 |
| graph | hybrid_rrf | hierarchical | 2 | 0.689 | 0.672 | 0.023 | 0.664 | 0.414 | 0.211 | 122.962 | 6792.768 | 19158.787 | 5.738 |
| graph | lexical | hierarchical | 2 | 0.574 | 0.557 | 0.000 | 0.549 | 0.320 | 0.199 | 61.568 | 165.714 | 21443.246 | 5.295 |
| graph | lexical_idf | hierarchical | 3 | 0.607 | 0.590 | 0.000 | 0.582 | 0.329 | 0.171 | 177.376 | 423.086 | 21841.475 | 5.771 |
| graph | hybrid_rrf_idf | hierarchical | 3 | 0.639 | 0.623 | 0.000 | 0.615 | 0.314 | 0.159 | 184.234 | 8298.726 | 20387.279 | 5.853 |
| graph | dense | hierarchical | 3 | 0.623 | 0.607 | 0.000 | 0.598 | 0.282 | 0.142 | 140.603 | 15066.219 | 20429.164 | 6.066 |
| graph | lexical | hierarchical | 3 | 0.525 | 0.508 | 0.000 | 0.500 | 0.244 | 0.139 | 117.162 | 213.356 | 22040.574 | 5.443 |
| graph | hybrid_rrf | hierarchical | 3 | 0.557 | 0.541 | 0.000 | 0.533 | 0.279 | 0.138 | 170.321 | 11097.607 | 20630.000 | 5.820 |

### What the context is made of

Share of retrieved chunks per chunk kind, and per `support` label of their document.

| config | kind distribution | support |
| --- | --- | --- |
| vector/dense/hierarchical | tutorial 0.39, lecture 0.38, task 0.13, summary 0.09, code 0.01 | primary 0.98 |
| vector/hybrid_rrf_idf/hierarchical | lecture 0.34, tutorial 0.28, task 0.19, summary 0.15, code 0.03 | primary 0.95 |
| vector/lexical/hierarchical | task 0.36, lecture 0.31, code 0.13, tutorial 0.10, summary 0.10 | primary 0.93 |
| vector/dense/fixed | lecture 0.46, tutorial 0.26, summary 0.16, task 0.09, code 0.03 | primary 0.97 |
| graph/dense/hierarchical | **code 0.58**, lecture 0.30, tutorial 0.06, summary 0.05, task 0.00 | primary 1.00 |
| graph/lexical/hierarchical | **code 0.69**, lecture 0.21, task 0.07, summary 0.02, tutorial 0.01 | primary 1.00 |

### nDCG@8 per query kind

| config | definitional | howto | api | task | cross | Polish |
| --- | --- | --- | --- | --- | --- | --- |
| vector/dense/hierarchical | 0.709 | 0.551 | 0.504 | 0.883 | 0.586 | 0.518 |
| vector/hybrid_rrf_idf/hierarchical | 0.660 | 0.549 | 0.430 | 0.794 | 0.606 | 0.373 |
| vector/hybrid_rrf/hierarchical | 0.616 | 0.495 | 0.340 | 0.630 | 0.528 | 0.351 |
| vector/lexical_idf/hierarchical | 0.546 | 0.456 | 0.398 | 0.604 | 0.508 | 0.083 |
| vector/lexical/hierarchical | 0.348 | 0.373 | 0.128 | 0.268 | 0.602 | 0.040 |
| graph/dense/hierarchical | 0.212 | 0.250 | 0.209 | 0.430 | 0.449 | 0.243 |

### Reading

1. **`vector / dense / hierarchical / bge_m3` wins every metric** (nDCG@8 0.625, hit@8 0.967,
   MRR 0.841) and is also the cheapest context: 6.9k characters against 12-21k for the others, so
   it is both the most relevant and the smallest prompt. It misses only 2 of 61 queries
   (`l6_pl_shared_memory`, `l7_epoll_wait`).
2. **Hierarchical beats fixed** for every searcher (dense 0.625 vs 0.510, hybrid_rrf_idf 0.595 vs
   0.498). Heading-scoped chunks are shorter and single-topic, and they carry a `section_id`, which
   is what makes `section_recall@8 = 0.74` possible at all - `fixed` scores 0 there by
   construction.
3. **IDF weighting is the single cheapest improvement on the lexical side**: `lexical_idf` lifts
   nDCG from 0.342 to 0.492 and `hybrid_rrf_idf` lifts `hybrid_rrf` from 0.525 to 0.595, at no
   measurable cost in latency. Plain `ts_rank_cd` is dominated by long chunks that repeat a common
   term; the idf weights push the rare API name to the front.
4. **The embedder carries the multilingual burden.** On the 4 Polish queries lexical retrieval is
   useless (0.040) while dense `bge_m3` reaches 0.518 - the corpus is English, so only a
   multilingual embedding bridges the gap. The same holds for `kind:api` queries (0.128 lexical vs
   0.504 dense): a student rarely spells the API the way the tutorial does.
5. **GraphRAG loses on this gold set, and the per-kind table says why.** 58-69% of what the walk
   returns are `code` chunks: the lab -> code_file -> api_function edges are dense, so activation
   flows into the source files instead of the prose that answers the question. It also never
   reaches the lecture documents (all 5 lecture queries miss) or the netcat lab, which has no task
   and almost no API nodes - the walk can only return what the extractor attached to a node.
6. **The graph is not useless, it is over-walked.** At `hops = 1` the same configuration jumps from
   nDCG 0.270 to 0.563 and `section_recall` from 0.046 to 0.500, within striking distance of the
   vector rows; every extra hop then costs about 40% of the score. Depth 2 and 3 mostly add
   activation to hub nodes shared by every lab.
7. **Graph retrieval is the only setting that never returns background material** (support
   `primary` 1.00 against 0.93-0.98 for vector): the Kozlowski PDFs are attached to few nodes. That
   is a feature for grounding and a bug for coverage.
8. **Latency is dominated by connection setup**, not by strategy: 20-30 ms for lexical, 57-106 ms
   for anything that embeds a query, 63-138 ms for the graph walk. The first graph query costs
   about 0.2 s of edge loading and the first `bge_m3` query 6-10 s of model loading; both are
   one-off per process, which is why the runner reuses one instance per configuration.

### Limitations

* **Gold set size.** 61 queries written by one person from the same corpus they evaluate. They
  state what *should* be retrieved, not what a cohort of students would actually ask, and 61
  queries put the standard error of a mean around 0.05 - differences smaller than that are noise.
* **Lab-level relevance.** A chunk is relevant when it belongs to an expected lab or document.
  That is coarse: a chunk of the right lab about an unrelated API still counts. Section-level
  recall is the finer signal, but only the queries that name sections contribute to it.
* **Section ids.** `fixed` chunks carry no `section_id` at all and task chunks of the
  hierarchical chunker lose theirs, so `section_recall@k` is structurally 0 for the `fixed`
  strategy and for task-style queries. Compare it only between hierarchical configurations.
* **The `fake` embedder** hashes text into random unit vectors: its dense ranking is noise by
  construction. It exists to test the plumbing, never to produce a thesis number - a run that
  falls back to it says so loudly in the console and in the `embedder` column.
* **Latency.** Every store call opens its own psycopg connection (no pool), so the absolute
  milliseconds are dominated by connection setup; only the differences between configurations are
  meaningful. `latency_ms_first` of a `bge_m3` configuration also contains the one-off
  SentenceTransformer load (7-15 s).
* **One corpus state.** Numbers are only comparable inside one run: the corpus grew from 217 to
  231 documents while the harness was being written.

# rag-lab-generator

Design and evaluation of a Retrieval-Augmented Generation system for automatic creation of
laboratory assignments. Target courses: Operating Systems 1 and 2 (MiNI, Warsaw University of
Technology). A single LangGraph agent helps students prepare for labs: it generates new tasks in the
style and difficulty of the existing ones, explains topics, and draws concept diagrams. Two RAG
architectures (vector and graph) and several chunking / search strategies are implemented behind one
interface so they can be benchmarked against each other.

## Architecture

```
sources  ->  parsers  ->  data/raw (lab.xml, src/, slides/, extra/, summary)  ->  chunkers
                                                                                   |
Postgres + pgvector  <-  embeddings (bge-m3 | fake)  <-----------------------------+
   |            |
   |            +-- knowledge graph (nodes/edges tables + networkx)
   |
searchers: lexical | lexical_idf | dense | hybrid_rrf | hybrid_rrf_idf | graph_walk
   |
RAG: vector | graph   ->  LangGraph agent (generate_lab, explain_topic, visualize_concept)
   |                              |
eval harness (matrix, metrics)    +-- FastAPI (/api) -> React UI (web/)
```

Every swappable component (source, chunker, embedder, searcher, rag, llm) is an abstract class plus
a registry entry; the active strategy is chosen by name in `.env` or on the command line.

| Kind     | Strategies                                                        | Package                          |
|----------|-------------------------------------------------------------------|----------------------------------|
| source   | `sop_site` (git clone of the course site), `kozlowski` (http)     | `ingestion/sources/`             |
| chunker  | `hierarchical` (sections, semantic fallback), `fixed`, `semantic` | `ingestion/chunking/`            |
| embedder | `bge_m3` (local, multilingual), `fake` (tests)                    | `retrieval/embeddings/`          |
| searcher | `lexical`, `lexical_idf`, `dense`, `hybrid_rrf`, `hybrid_rrf_idf`, `graph_walk` | `retrieval/searchers/` |
| rag      | `vector`, `graph`                                                 | `retrieval/rag/`                 |
| llm      | `anthropic` (Claude API), `fake` (offline)                        | `generation/llm/`                |

Corpus layout and document ids: `docs/corpus.md`. Evaluation protocol and results: `docs/eval.md`.
Lab XML schema: `docs/lab.xsd`. QA reports: `docs/qa-report.md`, `docs/qa-web-report.md`.

## Quick start

```bash
uv sync                                  # Python 3.12 (pinned in .python-version)
cp .env.template .env                    # ANTHROPIC_API_KEY is optional; LLM_PROVIDER=fake works offline
docker compose up -d db                  # pgvector Postgres on localhost:5433, schema applied on first start

uv run rag-lab ingest                    # clone/download sources, build data/raw/<course>/<lab>/
uv run rag-lab corpus-stats
uv run rag-lab chunk --strategy hierarchical
uv run rag-lab index --embedder bge_m3 --strategy hierarchical   # first run downloads the model (~2 GB)
uv run rag-lab graph-build --strategy hierarchical

uv run rag-lab query "how to read directory entries with readdir" --rag vector --searcher hybrid_rrf
uv run rag-lab query "how does epoll differ from select" --rag graph
uv run rag-lab agent "generate a lab about FIFO similar to L5" --course sop2      # --llm anthropic with a key
uv run rag-lab eval --matrix              # results/*.csv and the eval_runs table

uv run rag-lab serve                      # FastAPI on 127.0.0.1:8000
cd web && npm install && npm run dev      # React UI on http://localhost:5173
```

## Development

```bash
uv run pytest -m "not integration"        # unit tests
uv run pytest -m integration              # needs the db container; rebuild the graph afterwards
uv run mypy src
uv run ruff check src tests && uv run ruff format --check src tests
uv run pre-commit run --all-files
cd web && npm run build && npm run lint
```

Code regulations (file headers, comments, typing, registries) are in `CLAUDE.md`. CI (`.github/workflows/ci.yml`)
runs pre-commit, mypy, unit and integration tests against a pgvector service, and the Docker build.

## Repository map

```
src/rag_lab_generator/
  config.py  models.py  registry.py  cli.py
  ingestion/   sources/ parsers/ chunking/ lab_xml.py layout.py mapping.yaml summarizer.py pipeline.py
  retrieval/   embeddings/ stores/ searchers/ rag/ graph/
  generation/  llm/ prompts/*.md schemas.py
  agent/       state.py graph.py rag_factory.py tools/
  eval/        queries.yaml metrics.py runner.py judge.py
  api/         app.py routers/ schemas.py deps.py
web/           Vite + React + TypeScript UI
sql/           001_schema.sql
data/          corpus (gitignored)      results/   eval outputs (gitignored)
```

## CI (GitHub Actions)

Three workflows under `.github/workflows/`:

| workflow | trigger | what it does |
| --- | --- | --- |
| `ci.yml` | every PR and push to `main` | pre-commit, mypy, unit + integration tests against a throwaway pgvector container, docker build |
| `deploy.yml` | every PR (preview) and push to `main` (production) | `vercel deploy` with a project token, so collaborators need only push rights on GitHub; the PR gets a comment with the preview URL |
| `rebuild-db.yml` | manual, or push to `main` touching `data/raw/**`, `sql/`, ingestion, retrieval or eval code | rebuilds the production database from the committed corpus: chunks of every strategy, bge-m3 vectors through the HuggingFace Inference API, the knowledge graph and its node descriptions (`graph-describe`, real model once `ANTHROPIC_API_KEY` is a secret), then three retrieval evaluations reported in the job summary and kept as an artifact |

The corpus is versioned: the text part of `data/raw` (lab.xml, sources, summaries, pdf text
sidecars, ~3 MB) is committed, pdfs and `data/external` are not. Whoever changes the corpus runs
`uv run rag-lab ingest` locally and commits the result; the database is a derived artifact that
`rebuild-db` recreates in about 15 minutes. `chunk --replace` empties a strategy before refilling
it, so production search is degraded for those minutes.

Repository secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` (from `.vercel/project.json`),
`NEON_DATABASE_URL_UNPOOLED` (the direct Neon connection string), `HF_API_TOKEN` (fine-grained token
with the "Make calls to Inference Providers" permission).

## Deployment (Vercel)

One Vercel project with two services defined in `vercel.json`: `frontend` (Vite build of `web/`) and
`backend` (FastAPI via `main.py`, Python 3.12 on Fluid Compute). Public routes: `/api/*` -> backend,
everything else -> frontend. Database: Neon Postgres with pgvector provisioned through the Vercel
Marketplace (env vars `DATABASE_URL`, `DATABASE_URL_UNPOOLED` are injected automatically).

Heavy dependencies are optional extras so the function stays small: `ingest` (pymupdf, xhtml2pdf,
markdown), `embed-local` (sentence-transformers), `serve` (uvicorn). Locally use `uv sync --all-extras`.
On Vercel query embeddings come from `EMBEDDING_PROVIDER=bge_m3_hf` (HuggingFace Inference API, same
bge-m3 vectors as the local model); set `HF_API_TOKEN`. Corpus files ship with the function from
`data/raw` (pdfs excluded by `.vercelignore`); the database is loaded once from a local dump:

```bash
vercel link && vercel integration add neon --non-interactive --no-claim
vercel integration resource connect <neon-resource> rag-lab-generator --yes
vercel env pull .env.vercel --environment=preview
pg_dump "$LOCAL_DATABASE_URL" --no-owner --no-privileges -f dump.sql && psql "$DATABASE_URL_UNPOOLED" -f dump.sql
printf 'hf_...' | vercel env add HF_API_TOKEN production
vercel deploy --prod
```

Production: https://rag-lab-generator.vercel.app

# RAG Lab Generator

![Coverage](https://img.shields.io/badge/coverage-97%25-brightgreen)

A Python project for building and evaluating a Retrieval-Augmented
Generation (RAG) application.

> **Current status (Stage 3):** the ingestion and indexing core is
> implemented: document upload (PDF, HTML, TXT, Markdown), text extraction,
> structure-aware chunking, PostgreSQL storage, embeddings, a Chroma vector
> index, background jobs on Redis/RQ, and baseline vector retrieval with the
> source-authority policy. Assignment generation, evidence validation, the
> other retrieval architectures, and the web client follow in later stages.

## Requirements

Install the following before working with the project:

-   Git
-   Python 3.12
-   `uv`
-   Docker Desktop
-   A GitHub account with access to the repository

### Verify prerequisites

``` bash
git --version
python3 --version
uv --version
docker --version
docker compose version
```

Python 3.12 is the version used by CI and Docker.

------------------------------------------------------------------------

## 1. Clone the repository

``` bash
git clone <REPOSITORY_URL>
cd rag-lab-generator
```

Replace `<REPOSITORY_URL>` with the repository URL.

------------------------------------------------------------------------

## 2. Install `uv`

If `uv` is not installed, install it using the official installer:

``` bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart the terminal or load the environment:

``` bash
source "$HOME/.local/bin/env"
```

Verify:

``` bash
uv --version
```

> Do not copy the `(sh, bash, zsh)` text from the installation message.
> It is documentation indicating supported shells, not part of the
> command.

------------------------------------------------------------------------

## 3. Set up the Python environment

From the project root:

``` bash
uv python install 3.12
uv sync
```

`uv sync` creates the project virtual environment and installs the
dependencies defined in `pyproject.toml`.

You do not need to manually activate `.venv` to run project commands.
Use `uv run`:

``` bash
uv run pytest
uv run pre-commit run --all-files
```

------------------------------------------------------------------------

## 4. Configure environment variables

Create your local environment file from the template:

``` bash
cp .env.template .env
```

Edit `.env` and add the required values.

Required values:

| Variable | Purpose |
|---|---|
| `TOKEN_SIGNING_KEY` | Signs bearer tokens; at least 32 random characters |
| `POSTGRES_PASSWORD` | Password of the PostgreSQL service in Docker Compose |
| `EMBEDDING_PROVIDER` | `openai` (semantic, needs `OPENAI_API_KEY`) or `hashing` (offline, deterministic, lexical only) |
| `OPENAI_API_KEY` | Needed only with `EMBEDDING_PROVIDER=openai` |

Optional settings (`DATABASE_URL`, `REDIS_URL`, `QUEUE_BACKEND`,
`FILE_STORAGE_DIR`, `CHROMA_PERSIST_DIRECTORY`, `MAX_UPLOAD_BYTES`,
`CHUNK_MAX_CHARS`, `CHUNK_OVERLAP_CHARS`) are listed in `.env.template` and in
`src/rag_lab_generator/config.py`. Course material is sent to the OpenAI API
only when `EMBEDDING_PROVIDER=openai`.

### Important

Never commit `.env`.

The repository contains `.env.template` as a safe template, while `.env`
is ignored by Git.

Check:

``` bash
git status
```

`.env` should not appear as an untracked file.

------------------------------------------------------------------------

## 5. Install and configure pre-commit

Pre-commit is part of the project dependencies.

Install the Git hooks:

``` bash
uv run pre-commit install
```

Run all hooks manually:

``` bash
uv run pre-commit run --all-files
```

The configured checks include:

-   Ruff formatting
-   Ruff linting
-   Flake8
-   Pylint
-   common file checks

Some hooks automatically fix issues. If a hook modifies files, run the
command again:

``` bash
uv run pre-commit run --all-files
```

The command should finish with all applicable hooks passing.

------------------------------------------------------------------------

## 6. Run tests

Run the unit tests (they use in-memory SQLite and need no services):

``` bash
uv run pytest
uv run pytest --cov            # with the coverage report
```

The integration tests run the PostgreSQL migrations, the repositories, the
RQ worker, and Chroma end to end. They need a **throw-away** PostgreSQL
database, because they drop and recreate the schema:

``` bash
TEST_DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5432/rag_test \
TEST_REDIS_URL=redis://localhost:6379/0 \
uv run pytest -m integration
```

Without `TEST_REDIS_URL` an in-process fake Redis is used.

Tests are located under:

``` text
tests/
```

The project is configured so tests can import the package from:

``` text
src/
```

------------------------------------------------------------------------

## 7. Build the Docker image

Make sure Docker Desktop is running.

Build the image:

``` bash
docker build -t rag-lab-generator .
```

Verify that the image exists:

``` bash
docker images
```

You can verify that the package is available inside the image:

``` bash
docker run --rm rag-lab-generator python -c "import rag_lab_generator; print('Docker OK')"
```

Expected output:

``` text
Docker OK
```

### Docker configuration

The repository contains:

-   `Dockerfile` --- builds the application image
-   `.dockerignore` --- prevents unnecessary files and secrets from
    being copied into the image

The Docker build uses Python 3.12 and `uv`.

------------------------------------------------------------------------

## 8. Run the application

### With Docker Compose

``` bash
cp .env.template .env      # set TOKEN_SIGNING_KEY, POSTGRES_PASSWORD, embeddings
docker compose up --build --detach --wait
```

This starts four services on a private network: `api` (FastAPI on port
8000, applies the database migrations on start-up), `worker` (RQ worker,
the only process that opens the Chroma store), `postgres`, and `redis`.
Uploaded files, the vector index, the database, and the queue are kept in
named volumes, so they survive restarts.

Create a user and get a bearer token:

``` bash
docker compose exec api rag-lab-generator create-user \
    --email you@example.edu --role instructor
```

The interactive API documentation is at <http://localhost:8000/docs>.

### Without Docker

Set `QUEUE_BACKEND=inline` to run jobs inside the API process (no Redis,
no worker); PostgreSQL is still required:

``` bash
uv run rag-lab-generator migrate
uv run rag-lab-generator create-user --email you@example.edu --role instructor
uv run rag-lab-generator api            # and, with QUEUE_BACKEND=rq: uv run rag-lab-generator worker
```

### API overview (`/api/v1`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/health` | public | Database and queue readiness |
| POST | `/documents` | instructor, administrator | Upload a source (`multipart/form-data`: `file`, JSON `metadata`); `202` with a job |
| GET | `/documents` | instructor, administrator | List with filters and pagination |
| GET | `/documents/{id}` | instructor, administrator | Document, status, and fragment count |
| PATCH | `/documents/{id}/metadata` | instructor, administrator | Update descriptive metadata |
| POST | `/courses/{course_id}/index` | instructor, administrator | Re-index all documents of a course; `202` with a job |
| POST | `/courses/{course_id}/retrieval` | instructor, researcher, administrator | Ranked evidence for a query; `202` with a job |
| GET | `/jobs/{id}` | job owner, administrator | Job status, result, or structured error |
| GET | `/jobs/{id}/logs` | job owner, administrator | Execution log of the job |

Errors use one JSON envelope: `{"error": {"code", "message", "details",
"request_id"}}`.

### End-to-end trace

`scripts/e2e_trace.py` uploads every file in `dataset/` through the API,
waits for the ingestion jobs, runs sample retrieval queries, and reports
latencies and the evidence found:

``` bash
uv run python scripts/e2e_trace.py --base-url http://localhost:8000 \
    --token <token> --output e2e-trace.json
```

------------------------------------------------------------------------

## 9. Development workflow

Create a feature branch from the latest `main`:

``` bash
git checkout main
git pull origin main
git checkout -b feature/<short-description>
```

Make your changes, then run the local quality checks:

``` bash
uv run pre-commit run --all-files
uv run pytest
docker build -t rag-lab-generator .
```

Fix any errors before pushing.

Commit your changes:

``` bash
git add .
git commit -m "feat: <description>"
```

Push the branch:

``` bash
git push --set-upstream origin feature/<short-description>
```

Then create a Pull Request targeting:

``` text
main
```

------------------------------------------------------------------------

## 10. CI/CD

Every Pull Request targeting `main` runs the GitHub Actions CI workflow.

The CI workflow has three jobs:

-   `build`: pre-commit, unit tests with coverage, Docker image build
-   `integration`: integration tests against PostgreSQL 16 and Redis 7
    service containers
-   `e2e`: starts the Docker Compose stack, creates a user, runs
    `scripts/e2e_trace.py`, and uploads the trace as an artifact

A Pull Request cannot be merged into `main` unless the required `build`
status check passes.

### CI locally

To reproduce the main checks locally:

``` bash
uv run pre-commit run --all-files
uv run pytest
docker build -t rag-lab-generator .
```

------------------------------------------------------------------------

## 11. Branch protection

The `main` branch is protected.

Development should follow:

``` text
feature branch
      ↓
Pull Request
      ↓
CI
      ↓
build ✓
      ↓
merge into main
```

Direct changes to `main` are not part of the normal development
workflow.

The required CI check is:

``` text
build
```

------------------------------------------------------------------------

## 12. Pull Request checklist

Before opening a Pull Request:

-   [ ] Code is on a feature branch
-   [ ] `uv run pre-commit run --all-files` passes
-   [ ] `uv run pytest` passes
-   [ ] `docker build -t rag-lab-generator .` succeeds
-   [ ] No secrets are committed
-   [ ] `.env` is not committed
-   [ ] Changes are described in the Pull Request

------------------------------------------------------------------------

## 13. Project structure

The repository is organized as:

``` text
rag-lab-generator/
├── .github/workflows/ci.yml         CI: build, integration, e2e
├── dataset/                         OPS course materials (Markdown corpus)
├── diploma paper/, documentation/   project report and requirements
├── scripts/e2e_trace.py             end-to-end trace through the API
├── src/rag_lab_generator/
│   ├── domain/                      entities, policies, ports (stdlib only)
│   ├── application/                 use cases: documents, jobs
│   ├── ingestion/                   extractors, chunking, ingestion service
│   ├── retrieval/                   vector retrieval strategy and service
│   ├── generation/                  (next stages)
│   ├── infrastructure/              PostgreSQL, Chroma, embeddings, RQ, files, tokens
│   ├── api/                         FastAPI app, routers, schemas, errors
│   ├── migrations/                  Alembic migrations
│   ├── container.py                 composition root
│   ├── worker.py                    RQ worker
│   └── cli.py                       rag-lab-generator command
├── tests/unit/, tests/integration/
├── docker-compose.yml, Dockerfile
└── pyproject.toml, uv.lock
```


------------------------------------------------------------------------

## 14. Dependency management with `uv`

Add a runtime dependency:

``` bash
uv add <package>
```

Add a development dependency:

``` bash
uv add --dev <package>
```

After changing dependencies, commit both:

``` text
pyproject.toml
uv.lock
```

For reproducible CI installations, CI uses:

``` bash
uv sync --locked
```

Do not manually edit `uv.lock`.

------------------------------------------------------------------------

## 15. Useful commands

### Install/sync dependencies

``` bash
uv sync
```

### Run tests

``` bash
uv run pytest
```

### Run all pre-commit checks

``` bash
uv run pre-commit run --all-files
```

### Install pre-commit Git hooks

``` bash
uv run pre-commit install
```

### Build Docker image

``` bash
docker build -t rag-lab-generator .
```

### Check Docker image

``` bash
docker images
```

### Check Git status

``` bash
git status
```

### Update local `main`

``` bash
git checkout main
git pull origin main
```

------------------------------------------------------------------------

## 16. Troubleshooting

### `uv: command not found`

Load the `uv` environment:

``` bash
source "$HOME/.local/bin/env"
```

If necessary, restart the terminal.

Then:

``` bash
uv --version
```

### Pre-commit fails after automatically changing files

Run it again:

``` bash
uv run pre-commit run --all-files
```

Some formatting and file hooks modify files on their first run.

### Docker build fails

Make sure Docker Desktop is running:

``` bash
docker --version
```

Then rebuild:

``` bash
docker build -t rag-lab-generator .
```

If you suspect a stale Docker cache:

``` bash
docker build --no-cache -t rag-lab-generator .
```

### Dependencies and lock file are inconsistent

Run:

``` bash
uv lock
uv sync
```

Then commit the updated `uv.lock` together with `pyproject.toml`.

------------------------------------------------------------------------

## 17. Architecture status

The project currently has the infrastructure needed to start RAG
development:

``` text
Git
 │
 ├── Feature branches
 └── Protected main
          │
          ▼
      Pull Request
          │
          ▼
     GitHub Actions
          │
     ┌────┼────┐
     ▼    ▼    ▼
 pre-commit pytest Docker
     │    │    │
     └────┼────┘
          ▼
       build ✓
          │
          ▼
      merge main
```

The application pipeline and its status:

``` text
Documents        implemented   PDF, HTML, TXT, Markdown upload
    ↓
Ingestion        implemented   text extraction with section paths and pages
    ↓
Chunking         implemented   structure-aware fragments
    ↓
Embeddings       implemented   OpenAI or offline hashing provider
    ↓
Vector Store     implemented   Chroma, one collection per course and model
    ↓
Retrieval        baseline      vector strategy with source-authority policy
    ↓
LLM              next stage    assignment generation
    ↓
Validation       next stage    evidence validation
    ↓
Evaluation       next stage    architecture comparison
```

SonarQube is intentionally not part of this project setup.

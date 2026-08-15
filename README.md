# RAG Lab Generator

A Python project for building and evaluating a Retrieval-Augmented
Generation (RAG) application.

> **Current status:** This repository contains the project
> infrastructure and development setup. The RAG implementation itself is
> intentionally not included yet.

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

Example:

``` env
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_EMBEDDING_MODEL=
CHROMA_PERSIST_DIRECTORY=./data/chroma
```

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

Run the complete test suite:

``` bash
uv run pytest
```

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

## 8. Development workflow

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

## 9. CI/CD

Every Pull Request targeting `main` runs the GitHub Actions CI workflow.

The CI pipeline performs:

``` text
Checkout
   ↓
Install uv
   ↓
Set up Python 3.12
   ↓
Install dependencies
   ↓
Run pre-commit
   ↓
Run pytest
   ↓
Build Docker image
```

The CI job is called:

``` text
build
```

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

## 10. Branch protection

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

## 11. Pull Request checklist

Before opening a Pull Request:

-   [ ] Code is on a feature branch
-   [ ] `uv run pre-commit run --all-files` passes
-   [ ] `uv run pytest` passes
-   [ ] `docker build -t rag-lab-generator .` succeeds
-   [ ] No secrets are committed
-   [ ] `.env` is not committed
-   [ ] Changes are described in the Pull Request

------------------------------------------------------------------------

## 12. Project structure

The current infrastructure is organized as:

``` text
rag-lab-generator/
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml
│   └── PULL_REQUEST_TEMPLATE/
│       └── pull_request.md
│
├── src/
│   └── rag_lab_generator/
│       └── __init__.py
│
├── tests/
│   └── unit/
│       └── test_smoke.py
│
├── .dockerignore
├── .env.template
├── .gitignore
├── .pre-commit-config.yaml
├── Dockerfile
├── README.md
├── pyproject.toml
└── uv.lock
```

The RAG application structure will be added separately.

------------------------------------------------------------------------

## 13. Dependency management with `uv`

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

## 14. Useful commands

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

## 15. Troubleshooting

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

## 16. Architecture status

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

The application layer will be introduced later:

``` text
Documents
    ↓
Ingestion
    ↓
Chunking
    ↓
Embeddings
    ↓
Vector Store
    ↓
Retrieval
    ↓
LLM
    ↓
RAG Answer
    ↓
Evaluation
```

SonarQube is intentionally not part of this project setup.

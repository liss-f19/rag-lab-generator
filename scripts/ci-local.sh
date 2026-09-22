#!/usr/bin/env bash
# Role:   Runs the steps of .github/workflows/ci.yml locally, on a copy of the files git would
#         push and against a throwaway pgvector container, so a push never discovers an
#         empty-database or "not versioned" failure first.
# Input:  Docker, uv, git; CI_LOCAL_PORT to override the host port (default 5498).
# Output: The same pass/fail as the CI build job; the copy and the container are removed at the end.
# Flow:   Copies every tracked and untracked-but-not-ignored file into a temp directory (what a
#         commit of the working tree would contain: no pdfs, no data/external, no empty dirs),
#         starts pgvector/pgvector:pg16 without any init script (exactly like the CI service),
#         exports DATABASE_URL and the fake providers, then runs sync, pre-commit, mypy, db-init,
#         unit tests, integration tests and the Docker build in CI order; stops at the first failure.
set -euo pipefail

PORT="${CI_LOCAL_PORT:-5498}"
NAME="raglab-ci-local"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/raglab-ci.XXXXXX")"

cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT
docker rm -f "$NAME" >/dev/null 2>&1 || true

echo "==> copying what git would push to $WORK"
cd "$REPO"
git ls-files -z --cached --others --exclude-standard | rsync -a --files-from=- --from0 ./ "$WORK/"
cd "$WORK"
# pre-commit and the CI checkout both work on a git tree, so the copy becomes one
git init -q && git add -A

echo "==> fresh pgvector on :$PORT"
docker run -d --name "$NAME" -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag -e POSTGRES_DB=raglab \
  -p "$PORT:5432" pgvector/pgvector:pg16 >/dev/null
until docker exec "$NAME" pg_isready -U rag -d raglab >/dev/null 2>&1; do sleep 1; done

export DATABASE_URL="postgresql://rag:rag@localhost:$PORT/raglab"
export LLM_PROVIDER=fake
export EMBEDDING_PROVIDER=fake
export UV_PROJECT_ENVIRONMENT="$WORK/.venv"

step() { echo; echo "==> $*"; "$@"; }
step uv sync --locked --extra ingest --extra serve
step uv run pre-commit run --all-files
step uv run mypy src
step uv run rag-lab db-init
step uv run pytest -m "not integration"
step uv run pytest -m integration
step docker build -t rag-lab-generator .
echo; echo "==> ci-local: all steps passed"

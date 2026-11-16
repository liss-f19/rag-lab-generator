FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --locked --no-dev --no-install-project

COPY src ./src

RUN uv sync --locked --no-dev

# Run as an unprivileged user; the data directories become the mount points of
# the named volumes, which inherit this ownership.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/files /data/chroma \
    && chown -R app:app /data

USER app

ENV PATH="/app/.venv/bin:$PATH" \
    FILE_STORAGE_DIR=/data/files \
    CHROMA_PERSIST_DIRECTORY=/data/chroma

EXPOSE 8000

CMD ["rag-lab-generator", "api"]

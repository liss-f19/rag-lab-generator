FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN pip install --no-cache-dir uv

RUN uv sync --locked --no-dev --no-install-project --extra ingest --extra serve

COPY src ./src

RUN uv sync --locked --no-dev --extra ingest --extra serve

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

CMD ["python"]

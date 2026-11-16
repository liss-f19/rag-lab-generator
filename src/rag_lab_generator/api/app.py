"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from rag_lab_generator import __version__
from rag_lab_generator.api.errors import install_error_handling
from rag_lab_generator.api.routers import courses, documents, health, jobs
from rag_lab_generator.config import get_settings
from rag_lab_generator.container import Container, build_container

API_PREFIX = "/api/v1"


def create_app(container: Container | None = None) -> FastAPI:
    """Build the API; tests pass a prepared container, production builds one at start-up."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if container is None:
            app.state.container = build_container(get_settings())
        try:
            yield
        finally:
            if container is None:
                app.state.container.engine.dispose()

    app = FastAPI(
        title="RAG Lab Generator API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    if container is not None:
        app.state.container = container
    install_error_handling(app)
    for router in (health.router, documents.router, courses.router, jobs.router):
        app.include_router(router, prefix=API_PREFIX)
    logging.basicConfig(level=logging.INFO)
    return app

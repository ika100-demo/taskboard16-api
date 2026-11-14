"""FastAPI entry point for taskboard16-api."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from . import __version__, tasks
from .logging_config import configure_logging
from .metrics import MetricsMiddleware
from .tasks.store import StorageUnavailable, TaskStore, close_task_store, get_task_store
from .tracing import configure_tracing, tracing_enabled

configure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
if tracing_enabled():
    configure_tracing()

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    store = app.dependency_overrides.get(get_task_store, get_task_store)()
    store.open()
    try:
        store.ensure_schema()
    except StorageUnavailable:
        log.warning("schema_deferred")
    yield
    close_task_store()


app = FastAPI(title="taskboard16-api", version=__version__, lifespan=lifespan)
app.add_middleware(MetricsMiddleware)
if tracing_enabled():
    FastAPIInstrumentor.instrument_app(app)
app.include_router(tasks.router)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe — returns 200 as long as the process is responding."""
    return HealthResponse(status="ok")


@app.exception_handler(StorageUnavailable)
async def storage_unavailable_handler(request: Request, exc: StorageUnavailable) -> JSONResponse:
    log.warning("storage_unavailable", error=type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Task storage unavailable"})


@app.get("/ready", response_model=HealthResponse)
def ready(store: Annotated[TaskStore, Depends(get_task_store)]) -> Response:
    """Readiness probe — 200 when the database answers, else 503."""
    if store.ping():
        return JSONResponse(status_code=200, content={"status": "ready"})
    return JSONResponse(status_code=503, content={"status": "unavailable"})


@app.get("/ping")
def ping() -> dict[str, str]:
    """Simple ping endpoint."""
    return {"pong": "taskboard16-api"}


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus scrape endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

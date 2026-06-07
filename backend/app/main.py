from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import dispose_engine
from app.services.job_dispatcher import job_dispatcher


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.storage_root_path).mkdir(parents=True, exist_ok=True)
    yield
    await job_dispatcher.shutdown()
    await dispose_engine()


app = FastAPI(
    title="Manga Translation API",
    version="0.1.0",
    lifespan=lifespan,
)

request_logger = logging.getLogger("manga_api.request")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4()) # Generate a new UUID if not provided by the client 
    start = time.perf_counter() # Start the timer at the beginning of the request processing
    request.state.request_id = request_id  

    try:
        response = await call_next(request) # this will call the actual endpoint handler and get the response
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        request_logger.exception(
            "request_id=%s method=%s path=%s status=500 duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-MS"] = f"{duration_ms:.2f}"
    request_logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

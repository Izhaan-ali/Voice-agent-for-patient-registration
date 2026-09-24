"""
FastAPI application entry point.

Logging middleware is implemented as a pure ASGI callable (not BaseHTTPMiddleware)
to avoid the known Starlette issue where BaseHTTPMiddleware swallows exceptions
before FastAPI's exception handlers can convert them to proper error responses.
"""

import logging
import time
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.database.database import init_db
import app.database.models  # noqa: F401 — registers ORM models with Base
from app.schemas.patient import error_response

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Startup ───────────────────────────────────────────────────────────────────
init_db()

# ── Application factory ───────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Voice AI patient registration backend. "
        "Accepts patient data from Vapi, validates it, and persists to SQLite."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Logging middleware (pure ASGI — does NOT use BaseHTTPMiddleware) ───────────
class _AccessLogger:
    """
    Lightweight ASGI middleware that logs method/path/status without wrapping
    the exception flow.  Uses the raw send callable to capture the status code
    after the inner app has fully handled the request (including exception
    handlers), so it never interferes with 422 / 500 error responses.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code: int = 0

        async def _send_interceptor(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self._app(scope, receive, _send_interceptor)
        duration_ms = (time.perf_counter() - start) * 1000
        method = scope.get("method", "?")
        path = scope.get("path", "?")
        logger.info("%s %s -> %s  (%.1f ms)", method, path, status_code, duration_ms)


app.add_middleware(_AccessLogger)  # type: ignore[arg-type]


# ── Global exception handlers ─────────────────────────────────────────────────
def _make_serializable(obj):
    """
    Recursively convert non-JSON-serializable objects (e.g. the ValueError
    stored in Pydantic v2 field_validator error ctx dicts) to strings.
    """
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)   # catches ValueError, Exception, etc.


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return Pydantic 422 validation errors inside the standard envelope."""
    safe_details = _make_serializable(exc.errors())
    return JSONResponse(
        status_code=422,
        content=error_response("Validation failed.", safe_details),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all: never expose stack traces to callers."""
    if isinstance(exc, RequestValidationError):
        return await validation_exception_handler(request, exc)
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=error_response(
            "An unexpected server error occurred. Please try again later."
        ),
    )


# ── Health / root ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "data": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "ok",
            "docs": "/docs",
        },
        "error": None,
    }


@app.get("/health", tags=["Health"])
def health():
    return {"data": {"status": "ok"}, "error": None}


# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.patients import router as patients_router  # noqa: E402
app.include_router(patients_router, prefix=settings.API_PREFIX)

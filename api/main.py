"""
Tek Watch API — FastAPI application serving dashboards and running alerting engine.

Endpoints:
  - Customer dashboard data (authenticated via Cognito JWT)
  - Admin portal operations (authenticated via Cognito Admin JWT)
  - Health check
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import load_config
from middleware.security import SecurityHeadersMiddleware
from rate_limit import (
    SlowAPIMiddleware,
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
)
from routers import (
    agent,
    alerts,
    chat,
    compute,
    cost,
    databases,
    messaging,
    metrics,
    networking,
    notifications,
    overview,
    security,
    storage,
)
from routers.admin import customers, operations, thresholds
from schemas.errors import ErrorDetail, ErrorResponse
from services.alerting.anomaly import anomaly_detection_loop
from services.alerting.threshold import threshold_evaluation_loop

logger = logging.getLogger(__name__)

# Background task handles — kept so they can be cancelled on shutdown
_background_tasks: list[asyncio.Task] = []


def _configure_logging(level: str) -> None:
    """Configure structured JSON logging for the API."""
    import json
    from datetime import datetime, timezone

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            return json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            })

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    root.handlers = [handler]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager — starts background workers on startup."""
    config = load_config()
    _configure_logging(config.log_level)
    logger.info("API starting: environment=%s", config.environment)

    _background_tasks.append(asyncio.create_task(threshold_evaluation_loop()))
    _background_tasks.append(asyncio.create_task(anomaly_detection_loop()))
    logger.info("Background workers started: threshold_evaluation, anomaly_detection")

    yield

    for task in _background_tasks:
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    logger.info("API shutting down — background workers stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = load_config()

    app = FastAPI(
        title="Tek Watch API",
        description="Cloud infrastructure monitoring platform by Tek Tribe Ltd",
        version="1.0.0",
        docs_url="/docs" if config.environment != "prod" else None,
        redoc_url="/redoc" if config.environment != "prod" else None,
        lifespan=lifespan,
    )

    # ── Rate limiting ─────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── Security headers ──────────────────────────────────────────────────────
    app.add_middleware(SecurityHeadersMiddleware)

    # ── CORS — origins from config, never hardcoded ───────────────────────────
    allowed_origins = [o.strip() for o in config.allowed_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ── Standardised error responses ──────────────────────────────────────────

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(code=f"HTTP_{exc.status_code}", message=str(exc.detail))
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message="Request validation failed",
                    details={"errors": exc.errors()},
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred",
                )
            ).model_dump(),
        )

    # ── Health check ──────────────────────────────────────────────────────────

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "environment": config.environment}

    # ── Customer dashboard routers ────────────────────────────────────────────
    app.include_router(overview.router,       prefix="/api/v1",              tags=["Overview"])
    app.include_router(compute.router,        prefix="/api/v1/compute",       tags=["Compute"])
    app.include_router(databases.router,      prefix="/api/v1/databases",     tags=["Databases"])
    app.include_router(networking.router,     prefix="/api/v1/networking",    tags=["Networking"])
    app.include_router(storage.router,        prefix="/api/v1/storage",       tags=["Storage"])
    app.include_router(messaging.router,      prefix="/api/v1/messaging",     tags=["Messaging"])
    app.include_router(security.router,       prefix="/api/v1/security",      tags=["Security"])
    app.include_router(cost.router,           prefix="/api/v1/cost",          tags=["Cost"])
    app.include_router(alerts.router,         prefix="/api/v1/alerts",        tags=["Alerts"])
    app.include_router(agent.router,          prefix="/api/v1/agent",         tags=["Agent"])
    app.include_router(metrics.router,        prefix="/api/v1/metrics",       tags=["Metrics"])
    app.include_router(chat.router,           prefix="/api/v1/chat",          tags=["Chat"])
    app.include_router(notifications.router,  prefix="/api/v1/notifications", tags=["Notifications"])

    # ── Admin portal routers ──────────────────────────────────────────────────
    app.include_router(customers.router,   prefix="/api/v1/admin/customers",   tags=["Admin - Customers"])
    app.include_router(thresholds.router,  prefix="/api/v1/admin/thresholds",  tags=["Admin - Thresholds"])
    app.include_router(operations.router,  prefix="/api/v1/admin/operations",  tags=["Admin - Operations"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = load_config()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.environment == "dev",
        log_level=config.log_level.lower(),
    )

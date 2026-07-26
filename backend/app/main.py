"""FastAPI application factory: middleware, logging, and router mounting."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import MaxBodySizeMiddleware


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="openQMS API", version="0.1.0")

    # Added before CORSMiddleware so CORS remains the outermost layer (its response
    # headers still get attached even to a request this middleware rejects) while
    # still running ahead of any route/dependency body parsing -- see
    # docs/DecisionLog.md#2026-07-26-document-upload-request-body-size-cap.
    app.add_middleware(
        MaxBodySizeMiddleware, max_body_bytes=settings.max_request_body_mb * 1024 * 1024
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    return app

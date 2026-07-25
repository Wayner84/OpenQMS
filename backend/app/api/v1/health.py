"""Liveness and readiness endpoints, per docs/API.md#health-and-readiness-endpoints-milestone-0."""

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def get_health() -> dict[str, str]:
    """Liveness probe. Does not touch the database; always returns quickly."""
    return {"status": "ok"}


@router.get("/health/ready")
async def get_health_ready(
    response: Response, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    """Readiness probe. Executes SELECT 1 to confirm database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "error"}
    return {"status": "ready", "database": "ok"}

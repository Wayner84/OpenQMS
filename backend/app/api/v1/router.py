"""Aggregates all v1 API routers into one, mounted under /api/v1 by app.main."""

from fastapi import APIRouter

from app.api.v1 import health
from app.modules.auth import router as auth

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)

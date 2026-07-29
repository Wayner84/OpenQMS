"""Aggregates all v1 API routers into one, mounted under /api/v1 by app.main."""

from fastapi import APIRouter

from app.api.v1 import health
from app.modules.auth import router as auth
from app.modules.documents import router as documents
from app.modules.people import router as people
from app.modules.products import router as products
from app.modules.suppliers import router as suppliers
from app.modules.users import router as users

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(people.companies_router)
api_router.include_router(people.people_router)
api_router.include_router(documents.categories_router)
api_router.include_router(documents.tags_router)
api_router.include_router(documents.documents_router)
api_router.include_router(suppliers.router)
api_router.include_router(products.categories_router)
api_router.include_router(products.products_router)

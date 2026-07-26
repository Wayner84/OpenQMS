"""Unit tests for app/core/middleware.py::MaxBodySizeMiddleware.

Per docs/DecisionLog.md#2026-07-26-document-upload-request-body-size-cap: a
defense-in-depth guard rejecting a request by its declared Content-Length before
the body is read, so an oversized upload can't reach Starlette's own (size-
unbounded) multipart spooling.
"""

from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core.middleware import MaxBodySizeMiddleware


async def _echo(request: object) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _make_app(max_body_bytes: int) -> Starlette:
    app = Starlette(routes=[Route("/", _echo, methods=["POST"])])
    app.add_middleware(MaxBodySizeMiddleware, max_body_bytes=max_body_bytes)
    return app


async def test_rejects_request_declaring_a_content_length_over_the_limit() -> None:
    app = _make_app(max_body_bytes=10)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/", content=b"x" * 100)

    assert response.status_code == 413


async def test_allows_request_within_the_limit() -> None:
    app = _make_app(max_body_bytes=1000)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/", content=b"x" * 10)

    assert response.status_code == 200


async def test_allows_request_with_no_body() -> None:
    app = _make_app(max_body_bytes=10)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code in (200, 405)  # route only registered for POST

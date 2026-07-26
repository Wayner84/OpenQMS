"""Request-level ASGI middleware, applied before any route/dependency logic runs.

Currently: a maximum-request-body-size guard. See
docs/DecisionLog.md#2026-07-26-document-upload-request-body-size-cap for why this
exists and its documented residual risk.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send


class MaxBodySizeMiddleware:
    """Rejects a request with `413` before its body is read/parsed if the client's
    own `Content-Length` header exceeds `max_body_bytes`.

    This is a defense-in-depth guard, not a substitute for the per-organisation
    `document_upload_policy` size limit enforced while streaming to disk (see
    app/modules/documents/storage.py::save_validated_upload). It exists because
    Starlette's multipart parser spools every uploaded file part to a temporary
    file with no size limit of its own *before* application code (including the
    per-organisation limit) ever runs -- an authenticated user could otherwise
    exhaust server disk space with an oversized upload regardless of the
    organisation's configured `max_size_mb`. Checking `Content-Length` up front
    rejects the common case (any client that sends a truthful `Content-Length`,
    which is virtually all HTTP clients including browsers) before Starlette
    allocates anything. A client using chunked transfer encoding with no
    `Content-Length` header is not caught by this check -- bounding that case
    requires a reverse-proxy-level body-size limit (see
    docs/Deployment.md#self-hosting-primary-supported-today), the same posture
    already taken for TLS termination.
    """

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None
            if declared_size is not None and declared_size > self._max_body_bytes:
                response: Response = JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body exceeds the maximum allowed size of "
                            f"{self._max_body_bytes} bytes"
                        )
                    },
                )
                await response(scope, receive, send)
                return

        await self._app(scope, receive, send)

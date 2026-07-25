# Builder: resolve and install dependencies with uv into a venv, per
# docs/DecisionLog.md#2026-07-25-backend-dependency-management.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.13 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

# Runtime: slim image, non-root user, only the venv and application code.
FROM python:3.12-slim

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app /app
COPY --chown=app:app docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
    && mkdir -p /app/uploads \
    && chown app:app /app/uploads

ENV PATH="/app/.venv/bin:${PATH}"

USER app

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]

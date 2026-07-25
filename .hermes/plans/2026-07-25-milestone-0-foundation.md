# Milestone 0 — Platform Foundation

**Status:** Planning complete (this batch). Implementation not started (next batch).
**Date planned:** 2026-07-25

## Purpose

Establish the smallest possible vertical slice of the full stack — backend,
database, frontend, Docker Compose, tooling — that later milestones (see
[Roadmap.md](../../docs/Roadmap.md)) can build real product modules on top of,
without any product module or SaaS feature being built yet. This document is the
exact scope contract for the *next* batch of work (implementation), written now
while the reasoning is fresh, so a fresh agent session can execute it without
re-deriving the plan.

Background reading before implementing: [Architecture.md](../../docs/Architecture.md),
[Database.md](../../docs/Database.md), [API.md](../../docs/API.md),
[Docker.md](../../docs/Docker.md), [CodingStandards.md](../../docs/CodingStandards.md),
[Contributing.md](../../docs/Contributing.md).

## In scope

1. **Repository scaffolding**
   - `backend/` — FastAPI app skeleton per the layout in
     [Architecture.md](../../docs/Architecture.md#directory-layout):
     `app/main.py`, `app/core/{config.py,db.py,logging.py}`,
     `app/api/v1/{router.py,health.py}`, `app/models/`, `app/schemas/`.
   - `backend/pyproject.toml` + `uv.lock`, ruff + mypy configuration.
   - `backend/tests/{unit,integration}/` with at least one real test per layer.
   - `backend/alembic/` initialised, one migration creating `organisations` and
     `configuration` tables (see [Database.md](../../docs/Database.md)), plus a data
     migration seeding exactly one `organisations` row.
   - `frontend/` — Vite + React + TypeScript scaffold per
     [Architecture.md](../../docs/Architecture.md#directory-layout), with ESLint,
     Prettier, Vitest + React Testing Library configured.
   - `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`,
     `.env.example` per [Docker.md](../../docs/Docker.md).

2. **Backend behaviour**
   - `GET /api/v1/health` — liveness, per [API.md](../../docs/API.md#get-apiv1health).
   - `GET /api/v1/health/ready` — readiness, checks DB connectivity, per
     [API.md](../../docs/API.md#get-apiv1healthready).
   - Typed `Settings` object reading `DATABASE_URL`, `BACKEND_CORS_ORIGINS`,
     `ENVIRONMENT`, `LOG_LEVEL` from environment variables.
   - CORS configured from `BACKEND_CORS_ORIGINS` (allow-list, not wildcard).
   - Structured JSON logging configured once in `core/logging.py`.
   - `organisations` and `configuration` tables exist via Alembic migration, with one
     seeded organisation row, proving the multi-tenancy and data-driven-configuration
     baseline end-to-end (no API surface for them yet — that's not needed until a
     module actually uses `configuration` rows).

3. **Frontend behaviour**
   - A minimal shell (routing scaffold, layout, theme provider supporting light/dark
     per the spec's UX requirement) with exactly one visible screen: it calls
     `GET /api/v1/health` (and ideally `/health/ready`) on load and displays whether
     the API is reachable and healthy. This is the full Milestone 0 UI — no
     navigation to non-existent modules.
   - Typed API client wrapper (`shared/api/client.ts`) that the health check uses,
     matching the convention in
     [CodingStandards.md](../../docs/CodingStandards.md#frontend-react-typescript)
     that later modules will reuse.

4. **Docker**
   - `docker compose up --build` brings up `db`, `backend`, `frontend` with health
     checks, per [Docker.md](../../docs/Docker.md#smoke-test-definition).
   - Migrations run automatically on backend container startup.
   - Named volumes persist Postgres data and reserve an (unused) uploads volume.

5. **Tooling commands** (must all exist and pass)
   - `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`,
     `uv run pytest` (backend, from `backend/`)
   - `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` (frontend,
     from `frontend/`)

## Out of scope (explicitly deferred)

- Authentication, users, sessions, JWTs (Milestone 1).
- Any product module (People, Documents, NCR, etc. — Milestone 1 onward per
  [Roadmap.md](../../docs/Roadmap.md)).
- Any SaaS/hosted feature: multi-organisation switching, billing, provisioning.
- File upload handling (the `openqms_uploads` volume is reserved but unused).
- Reverse proxy / TLS — that's a [Deployment.md](../../docs/Deployment.md) concern for
  a real deployment, not the Docker Compose dev/smoke-test stack.
- CI pipeline configuration (e.g. GitHub Actions) — not requested by this milestone;
  local commands must work, CI wiring is a separate future task if/when the project
  gains a CI runner (track in [TODO.md](../../docs/TODO.md) if decided later).

## Acceptance criteria

Implementation of this milestone is complete when all of the following are true:

- [ ] `docker compose up --build` succeeds from a clean clone with only `.env`
      populated from `.env.example`.
- [ ] `docker compose ps` shows `db`, `backend`, `frontend` all healthy.
- [ ] `curl http://localhost:8000/api/v1/health` → `200 {"status": "ok"}`.
- [ ] `curl http://localhost:8000/api/v1/health/ready` → `200 {"status": "ready", "database": "ok"}`.
- [ ] Loading the frontend shows the API reported as healthy, live (not hard-coded).
- [ ] `docker compose down` then `docker compose up` (no `--build`, no `-v`) preserves
      the seeded `organisations` row (proves volume persistence).
- [ ] All commands under "Tooling commands" above pass locally and inside the
      `backend`/`frontend` containers.
- [ ] At least one backend unit test, one backend integration test (hitting
      `/api/v1/health/ready` against real PostgreSQL), and one frontend component test
      exist and pass, written test-first per
      [Contributing.md](../../docs/Contributing.md#test-first-workflow-red-green-refactor).
- [ ] `docs/CurrentStatus.md` and `docs/TODO.md` updated in the same commit(s) to
      reflect Milestone 0 as implemented, not just planned.

## Suggested commit boundaries

Matches [Contributing.md](../../docs/Contributing.md#branching-and-commits) — commit
at coherent, working boundaries, not mid-edit:

1. `chore: scaffold backend FastAPI project with health/readiness endpoints` —
   backend skeleton + health endpoints + their tests, runnable outside Docker.
2. `feat: add organisations and configuration baseline via Alembic migration` —
   DB models + migration + seed + tests.
3. `chore: scaffold frontend Vite/React shell reporting API health` — frontend
   skeleton + health display + its test.
4. `chore: add Docker Compose stack for one-command startup` — Dockerfiles, compose
   file, `.env.example`, verified against the smoke test above.
5. `docs: mark Milestone 0 implemented` — update `CurrentStatus.md`, `TODO.md`,
   and this plan's checkboxes once verified.

Smaller or differently-grouped commits are fine as long as each is a coherent,
working unit and reason-focused commit messages are used throughout.

## Next milestone after this one

Milestone 1 — Authentication, Organisations (multi-user login against the seeded
`organisations` row), and the People module. See
[Roadmap.md](../../docs/Roadmap.md#m1-authentication-organisations-people).

# Architecture

openQMS is a Docker-first, self-hosted-by-default quality management system. This
document describes the platform architecture agreed for the project: the stack,
directory layout, module boundary pattern, multi-tenancy strategy, configuration
strategy, and security baseline. It is written before any application code exists
(see [CurrentStatus.md](CurrentStatus.md)); it is the contract the first
implementation batch (Milestone 0) must satisfy.

Stack decisions and their reasoning live in [DecisionLog.md](DecisionLog.md); this
document describes the resulting shape, not the reasoning for each choice.

## Stack summary

| Layer | Choice |
|---|---|
| Backend language/framework | Python 3.12+, FastAPI |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic |
| Database | PostgreSQL (Docker/production); SQLite permitted for fast local unit tests |
| Backend dependency management | uv + `pyproject.toml` / `uv.lock` |
| Backend lint/type-check | ruff (lint + format) + mypy |
| Backend tests | pytest, pytest-asyncio, httpx `AsyncClient` |
| Frontend framework | React 18+ with TypeScript, built with Vite |
| Frontend package manager | npm (`package-lock.json` committed) |
| Frontend lint/type-check | ESLint + TypeScript compiler (`tsc --noEmit`) |
| Frontend tests | Vitest + React Testing Library |
| Containerisation | Docker + Docker Compose, named persistent volumes |

## System shape

```
                    ┌─────────────────────┐
                    │   Browser (SPA)     │
                    │  React + TypeScript │
                    └──────────┬──────────┘
                               │ HTTPS (reverse proxy in production)
                               │ JSON over REST, /api/v1
                    ┌──────────▼──────────┐
                    │      FastAPI          │
                    │  backend/app/        │
                    │  ┌─────────────────┐ │
                    │  │ api/v1 routers  │ │
                    │  ├─────────────────┤ │
                    │  │ services        │ │
                    │  ├─────────────────┤ │
                    │  │ models (ORM)    │ │
                    │  └─────────────────┘ │
                    └──────────┬──────────┘
                               │ SQLAlchemy 2.0 (async)
                    ┌──────────▼──────────┐
                    │     PostgreSQL       │
                    │  (named Docker volume)│
                    └───────────────────────┘
```

Everything runs from one `docker-compose.yml` (see [Docker.md](Docker.md)): a
`db` service (PostgreSQL), a `backend` service (FastAPI, Uvicorn), and a `frontend`
service (Vite dev server in development; a static build served by Nginx in
production-style images). Self-hosting requires nothing beyond Docker and Docker
Compose.

## Layered backend architecture

Each request flows through three layers, in one direction only (routers depend on
services; services depend on models; models never depend upward):

1. **Routers (`api/v1/...`)** — FastAPI `APIRouter`s. Responsible only for HTTP
   concerns: path/query/body parsing (via Pydantic schemas), status codes, calling
   exactly one service method, and shaping the response. No business logic and no
   direct database queries here.
2. **Services (`services/...` or `modules/<module>/service.py`)** — business logic
   and orchestration. Services receive an `AsyncSession` via dependency injection and
   are the only layer allowed to combine multiple model operations into one
   transaction. Services are what unit tests target most heavily.
3. **Models (`models/...` or `modules/<module>/models.py`)** — SQLAlchemy 2.0
   declarative models (`Mapped[]` / `mapped_column()`), plus Pydantic schemas
   (`schemas/...`) that define the API's request/response contracts. Schemas are kept
   separate from ORM models so the API contract can evolve independently of storage
   detail.

Dependency injection (`Depends()`) provides the database session, the current
organisation (once Milestone 1 adds auth), and shared config to routers and services,
keeping both easily testable in isolation with substituted dependencies.

## Directory layout

The layout below is the target structure; Milestone 0 creates only the parts needed
for the platform vertical slice (see
[the Milestone 0 plan](../.hermes/plans/2026-07-25-milestone-0-foundation.md)) — no
module subpackages exist yet.

```
openQMS/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory, router mounting
│   │   ├── core/                # config, db session/engine, logging
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py    # aggregates all v1 routers
│   │   │       └── health.py    # liveness/readiness endpoints
│   │   ├── models/               # cross-cutting models (organisation, configuration)
│   │   ├── schemas/              # cross-cutting Pydantic schemas
│   │   └── modules/              # one package per QMS module (added from Milestone 1 onward)
│   │       └── <module_name>/
│   │           ├── models.py
│   │           ├── schemas.py
│   │           ├── service.py
│   │           └── router.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── pyproject.toml
│   ├── uv.lock
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/                  # routing, layout shell
│   │   ├── modules/               # one folder per QMS module (added from Milestone 1 onward)
│   │   └── shared/                # shared components, api client, theme
│   ├── public/
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   └── Dockerfile
├── docs/
│   ├── modules/                  # one document per product module
│   └── ...
├── .hermes/
│   └── plans/                    # dated implementation plans for each batch of work
├── docker-compose.yml
├── .env.example
├── README.md
└── CLAUDE.md
```

## Module boundary pattern

Each product module (Document Management, NCR, SPC, etc. — the full list is in
[the Roadmap](Roadmap.md) and one document per module lives under
[docs/modules/](modules/)) is implemented as a self-contained Python package under
`backend/app/modules/<module_name>/` and a matching TypeScript folder under
`frontend/src/modules/<module_name>/`. A module owns:

- its own SQLAlchemy models (`models.py`),
- its own Pydantic schemas (`schemas.py`),
- its own service layer (`service.py`),
- its own FastAPI router (`router.py`), mounted under `/api/v1/<module-prefix>` by
  `api/v1/router.py`.

Modules **reference** other modules' data through foreign keys and service calls, not
by duplicating data — matching the spec's explicit module relationship rules (e.g.
Products link to NCR/FAIR/SPC/documents; Suppliers link to NCR; People link to
Maintenance and actions; Assets link to Calibration and Maintenance; Documents link to
all appropriate domain records). A module may depend on another module's public
service functions; it must not reach into another module's models or database tables
directly. This keeps modules independently testable and lets the roadmap deliver them
as vertical slices without a big-bang rewrite.

## Multi-tenancy strategy

Recorded in detail in [DecisionLog.md](DecisionLog.md#2026-07-25-multi-tenancy-and-future-saas-shape).
In summary: every tenant-scoped table carries an `organisation_id` foreign key to an
`organisations` table from the moment it is created, even though Milestone 0 seeds
exactly one organisation and no authentication/tenant-switching exists yet. This keeps
self-hosting simple today (one instance, one organisation) while leaving the schema
ready for either a future shared hosted instance or (the currently preferred shape)
one Docker instance per hosted organisation.

## Configuration strategy

Two kinds of configuration exist, deliberately kept separate:

1. **Deployment configuration** — how to reach the database, secret keys, which
   environment (dev/prod), log level. Supplied via environment variables (see
   `.env.example`), loaded through a typed `Settings` object (Pydantic `BaseSettings`)
   in `backend/app/core/config.py`. Never stored in the database, never committed.
2. **Business configuration** — the cross-cutting, data-driven behaviour the spec
   requires: NCR/document prefixes, issue/document numbering schemes, risk scoring,
   supplier requirements, email templates, storage locations, folder structures,
   approval workflows, audit frequencies, calibration intervals. Stored in the
   database, scoped by `organisation_id`, editable without a deployment. Milestone 0
   introduces the `configuration` table and pattern (see
   [Database.md](Database.md#configuration-table)); individual modules add their own
   typed configuration rows as they are built, rather than hard-coding business rules.

## API versioning

All endpoints are mounted under `/api/v1/`. See
[DecisionLog.md](DecisionLog.md#2026-07-25-api-versioning-strategy) for the reasoning
and [API.md](API.md) for the concrete conventions.

## Security baseline

Authentication itself is out of scope for Milestone 0 (see the Milestone 0 plan), but
the following baseline applies from the first commit onward:

- No secrets committed to the repository; `.env.example` documents required variables
  with placeholder values only; `.gitignore` excludes `.env`.
- CORS is explicitly configured (allow-list, not wildcard) in
  `backend/app/core/config.py`, driven by an environment variable for allowed origins.
- All input crossing the API boundary is validated by Pydantic schemas; no
  unvalidated request data reaches a service or a raw SQL string.
- SQLAlchemy's parameterised query construction is used exclusively; no manual string
  interpolation into SQL.
- Passwords (once auth lands in Milestone 1) are hashed with a modern algorithm
  (Argon2id, via `passlib` or `argon2-cffi`) — never stored or logged in plain text.
- Dependency and base image versions are pinned (`uv.lock`, `package-lock.json`,
  pinned Docker base image tags) so builds are reproducible and auditable.
- Structured logging never logs secrets, passwords, or full request bodies containing
  personal data.
- Production deployment assumes TLS termination at a reverse proxy (see
  [Deployment.md](Deployment.md)); the application itself does not terminate TLS.
- **Frontend session handling** (Milestone 1): the JWT access token is held in
  `sessionStorage` only (never `localStorage`, never a cookie), attached to every
  authenticated request by `shared/api/client.ts`. A request that carried a token
  and is rejected `401` (expired, revoked by logout elsewhere, or the user was
  deactivated) fires a shared notification (`shared/auth/sessionEvents.ts`) that
  `AuthContext` uses to reset to a logged-out state and redirect, so a session going
  bad mid-use — not just at initial page load — is always handled. Reasoning and
  trade-offs in
  [DecisionLog.md](DecisionLog.md#2026-07-26-frontend-token-storage-and-mid-session-401-handling).
- **Constant-effort login lookups** (Milestone 1): `authenticate_user` always runs
  Argon2id verification, against a dummy hash when no user matches the supplied
  email, so an unknown-email login pays the same verification cost as a
  wrong-password one. Without this, the deliberately-slow Argon2id check only running
  for existing/active accounts would let an attacker enumerate valid accounts by
  response timing, even though the response body and status code are already
  identical for every failure case. See
  [DecisionLog.md](DecisionLog.md#2026-07-26-milestone-1-closeout-login-timing-side-channel-and-a-react-strictmode-mountedref-bug).

## Observability baseline

Milestone 0 establishes two HTTP endpoints that every later milestone can build on:

- `GET /api/v1/health` — liveness. No dependency on the database. Returns quickly so
  container orchestrators can distinguish "process is running" from "process is
  healthy."
- `GET /api/v1/health/ready` — readiness. Checks database connectivity. Used by
  Compose health checks and, later, orchestration platforms.

Structured JSON logging (via Python's standard `logging` module configured with a
JSON formatter) is established in Milestone 0 so every later module logs consistently
without each module reinventing logging setup.

## Related documents

- [Roadmap.md](Roadmap.md) — milestone and module delivery order.
- [Database.md](Database.md) — schema conventions and migration workflow.
- [API.md](API.md) — REST conventions and endpoint contract details.
- [Docker.md](Docker.md) — Compose services and volumes.
- [Deployment.md](Deployment.md) — self-hosting and future hosted deployment.
- [CodingStandards.md](CodingStandards.md) — code-level conventions and testing
  workflow.
- [docs/modules/](modules/) — one document per product module.

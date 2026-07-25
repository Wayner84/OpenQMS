# Current Status

_Last updated: 2026-07-25_

This document is kept truthful and current in the same commit as any work that
changes it, per [Contributing.md](Contributing.md). It must never describe
in-progress or planned work as complete.

## Current milestone

**M0 — Platform Foundation.** See
[.hermes/plans/2026-07-25-milestone-0-foundation.md](../.hermes/plans/2026-07-25-milestone-0-foundation.md)
for the exact scope and acceptance criteria, and [Roadmap.md](Roadmap.md) for how it
fits the overall delivery order.

**Phase: implementation in progress.** The backend platform, PostgreSQL database
baseline, and frontend shell are implemented and verified. The complete Docker
Compose stack remains.

## Completed work

- Backend FastAPI application skeleton: app factory (`backend/app/main.py`), typed
  `Settings` (`backend/app/core/config.py`), async SQLAlchemy engine/session factory
  (`backend/app/core/db.py`), structured JSON logging (`backend/app/core/logging.py`),
  allow-list CORS. Dependency management via `uv` (`backend/pyproject.toml`,
  `backend/uv.lock`).
- `GET /api/v1/health` (liveness) and `GET /api/v1/health/ready` (readiness, executes
  a real DB query) implemented per [API.md](API.md), in
  `backend/app/api/v1/health.py`.
- SQLAlchemy 2.0 `organisations` and `configuration` models plus the initial Alembic
  migration. The migration creates both tables and idempotently seeds exactly one
  default organisation.
- 14 backend tests passing: 10 unit tests (SQLite where appropriate) and 4 integration
  tests against PostgreSQL 17. The integration suite verifies migration application,
  seed idempotency, JSONB round-tripping, and live readiness.
- Backend quality gates pass: Ruff formatting/linting and strict mypy across 28 source
  files.
- Product specification received and read in full
  ([docs/ProductSpecification.md](ProductSpecification.md)).
- Full documentation-first architecture and implementation plan for Milestone 0
  produced (this batch), comprising:
  - Root project foundation: [README.md](../README.md), [CLAUDE.md](../CLAUDE.md),
    `.editorconfig`, `.gitattributes`, `.gitignore`.
  - Core documentation set: [Architecture.md](Architecture.md), [Roadmap.md](Roadmap.md),
    this file, [FutureIdeas.md](FutureIdeas.md), [CodingStandards.md](CodingStandards.md),
    [Database.md](Database.md), [API.md](API.md), [Docker.md](Docker.md),
    [Deployment.md](Deployment.md), [Contributing.md](Contributing.md),
    [TODO.md](TODO.md), [DecisionLog.md](DecisionLog.md).
  - One planning-stage document per product module under [docs/modules/](modules/)
    (13 documents — see the index in that folder), each labelled `Status: Planned`.
  - The Milestone 0 implementation plan itself:
    [.hermes/plans/2026-07-25-milestone-0-foundation.md](../.hermes/plans/2026-07-25-milestone-0-foundation.md).
- Technology stack chosen and recorded with reasoning: FastAPI + SQLAlchemy 2.0 +
  Alembic + PostgreSQL (backend), React + TypeScript + Vite (frontend), Docker
  Compose for orchestration. Full reasoning in [DecisionLog.md](DecisionLog.md).
- Frontend Vite + React + TypeScript (strict) shell (`frontend/`): app shell
  (`src/app/App.tsx`, `Layout.tsx`), a typed shared API client
  (`src/shared/api/client.ts`) built on `fetch` and `VITE_API_BASE_URL`, typed health
  client functions (`src/shared/api/health.ts`), and the one Milestone 0 screen
  (`src/app/HealthStatus.tsx`) that calls `GET /api/v1/health` and
  `GET /api/v1/health/ready` live and shows loading/success/error states. Accessible
  light/dark theming (`src/shared/theme/ThemeProvider.tsx`, `ThemeToggle.tsx`) follows
  `prefers-color-scheme` by default with a persisted user override; styling approach
  (plain CSS custom properties, no component library) recorded in
  [DecisionLog.md](DecisionLog.md#2026-07-25-frontend-styling-approach) and
  [CodingStandards.md](CodingStandards.md#frontend-react-typescript).
- Frontend tooling: ESLint (flat config, typescript-eslint strict type-checked +
  react/react-hooks/jsx-a11y), Prettier, `tsc --noEmit` (strict), Vitest + React
  Testing Library. `npm run lint`, `format:check`, `typecheck`, `test`, `build` all
  pass; 5 tests across 2 files (`client.test.ts`, `HealthStatus.test.tsx`), written
  test-first (RED confirmed against the missing modules, then GREEN).

## Work in progress

Milestone 0 containerisation slice (see
[.hermes/plans/2026-07-25-milestone-0-foundation.md](../.hermes/plans/2026-07-25-milestone-0-foundation.md)):
Dockerfiles, the Docker Compose stack, persistent-volume test, and full-stack smoke
test have not yet been implemented.

## Known bugs

None known in the code written so far. `npm audit` (frontend) reports 12
vulnerabilities, all in dev-only tooling transitive dependencies (ESLint's
`minimatch`/`brace-expansion`, Vite's dev-time `esbuild`), none in shipped runtime
code; each documented fix requires an unproven major-version jump (ESLint 9→10,
Vite 5→8) and is deferred rather than forced. Revisit when those majors are mature.

## Next recommended tasks

Continue Milestone 0 as scoped in
[.hermes/plans/2026-07-25-milestone-0-foundation.md](../.hermes/plans/2026-07-25-milestone-0-foundation.md):
the Docker Compose stack (Tasks 8-9) and Milestone 0 documentation close-out
(Task 10). Full task breakdown with dependencies and complexity in
[TODO.md](TODO.md) under "High Priority."

Note on local tooling: this backend was developed using a repository-local `uv`
install and virtual environment under `.tools/` (git-ignored) because `uv` was not
present as a global tool on the development host. `.tools/` is not part of the
committed project structure — any session/contributor without a global `uv` install
can recreate it by creating a venv, `pip install uv` into it, then using that `uv`
binary against `backend/pyproject.toml` exactly as documented in
[CodingStandards.md](CodingStandards.md).

## Future ideas

See [FutureIdeas.md](FutureIdeas.md) for deferred concepts (electronic signatures,
ISO compliance assistance, automatic CMM import, hosted/SaaS provisioning, and more)
that are intentionally out of scope until their relevant milestone, if ever.

## Blockers

None. The stack was chosen per the product specification's own preference (FastAPI +
SQLAlchemy 2/Alembic + PostgreSQL, React/TypeScript/Vite) with reasoning recorded in
[DecisionLog.md](DecisionLog.md); no open question is blocking the start of Milestone
0 implementation.

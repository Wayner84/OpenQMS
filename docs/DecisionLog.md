# Decision Log

This log records major architectural decisions for openQMS. Every entry captures the
problem being solved, the options considered, the option chosen and why, and the
resulting trade-offs. Entries are append-only: superseding a decision means adding a
new entry that references the old one, not editing history.

Related reading: [Architecture.md](Architecture.md), [Roadmap.md](Roadmap.md).

---

## 2026-07-25 — Backend language and web framework

**Problem:** Need a backend language/framework that supports clear type hints, modular
architecture, dependency injection, async I/O, and is realistic for a long-running
project maintained by autonomous coding agents across many sessions.

**Options considered:**
- **FastAPI (Python)** — async-first, Pydantic-based validation, automatic OpenAPI
  schema generation, built-in dependency injection (`Depends`), strong typing culture.
- **Django + Django REST Framework** — batteries-included, mature admin/ORM, but
  monolithic conventions and a sync-first ORM push against a modular, service-oriented
  design.
- **Flask** — minimal and flexible, but requires bolting on validation, DI, async
  support and OpenAPI generation by hand, increasing the chance of drift between docs
  and code.
- **Node.js/Express or NestJS** — NestJS has good structure and DI, but splits the
  stack across two ecosystems (backend and tooling) rather than one, and the product
  spec explicitly calls for Python on the backend.
- **Go** — excellent performance and concurrency, but a smaller ecosystem for the kind
  of CRUD/reporting-heavy domain modules openQMS needs (PDF generation, SPC math,
  templated documents), and the spec calls for Python.

**Chosen:** FastAPI.

**Reason:** The product specification requires Python with clear type hints and
sensible dependency injection — FastAPI provides both natively. Its automatic OpenAPI
schema doubles as always-current API documentation (see [API.md](API.md)), which
matters for a project whose continuity depends on documentation staying truthful.
Pydantic validation keeps request/response contracts explicit and type-checked.

**Pros:** async-native (good for I/O-bound QMS workloads: file uploads, PDF export,
email); automatic interactive docs at `/docs`; first-class `Depends()` injection keeps
routers thin and services testable; large, active ecosystem; plays well with
SQLAlchemy 2.0 async.

**Cons:** less "batteries-included" than Django (no built-in admin, auth, or ORM) —
these must be assembled deliberately, which is acceptable since the spec calls for a
modular, non-monolithic design anyway.

---

## 2026-07-25 — ORM and schema migrations

**Problem:** Need an ORM and migration tool that supports PostgreSQL in production and
SQLite for local development/tests without compromising correctness, and that keeps
schema changes reviewable and reversible.

**Options considered:**
- **SQLAlchemy 2.0 (async) + Alembic** — mature, framework-agnostic, explicit unit of
  work, first-class async support since 2.0, Alembic autogenerates migrations from
  model diffs with manual review.
- **Django ORM** — tied to Django; ruled out with the Django framework decision above.
- **Tortoise ORM** — async-native and lightweight, but a much smaller ecosystem and
  weaker migration tooling (Aerich) than Alembic.
- **SQLModel** — a thin, appealing layer over SQLAlchemy + Pydantic, but still young
  relative to SQLAlchemy 2.0 directly and adds an extra abstraction layer between the
  ORM and validation models that this project can define explicitly instead.
- **Raw SQL / query builder (e.g. `asyncpg` directly)** — maximum control, but no
  cross-database portability (PostgreSQL/SQLite) and no migration tooling, which is
  unacceptable for a project designed for long-lived, agent-driven maintenance.

**Chosen:** SQLAlchemy 2.0 (async engine) + Alembic.

**Reason:** SQLAlchemy 2.0's typed, async-native API meets the type-hint requirement
and works against both PostgreSQL (production/Docker) and SQLite (local dev), per the
spec's explicit allowance. Alembic is the de facto standard migration tool for
SQLAlchemy and produces reviewable, versioned migration scripts — required for
recoverability across sessions and contributors.

**Pros:** mature and extensively documented; explicit `Mapped[]`/`mapped_column()`
typing in 2.0 style; Alembic migrations are plain Python and diffable in code review;
works identically in tests (SQLite) and production (PostgreSQL) for the majority of
schema.

**Cons:** PostgreSQL-only features (e.g. `JSONB`, certain constraint types) will not
behave identically under SQLite, so tests that depend on those features must run
against PostgreSQL (see [Database.md](Database.md) for the exact policy).

---

## 2026-07-25 — Primary database engine

**Problem:** Need a production database that supports Docker-first self-hosting,
JSON-flexible configuration-driven business rules (numbering schemes, risk matrices,
email templates), and a credible path to future multi-tenant separation.

**Options considered:**
- **PostgreSQL** — required by the spec for Docker deployment; strong JSONB support,
  mature, widely operated, excellent Alembic/SQLAlchemy support.
- **MySQL/MariaDB** — viable alternative, weaker JSON querying ergonomics than
  PostgreSQL, and not what the spec asks for.
- **SQLite only** — rejected as the sole production database: no concurrent
  multi-writer story suitable for a multi-user QMS, and the spec requires PostgreSQL
  in Docker for production.

**Chosen:** PostgreSQL for Docker/production; SQLite permitted only for local
developer convenience and fast unit tests that do not depend on PostgreSQL-only
features.

**Reason:** Directly mandated by the spec. PostgreSQL's JSONB and strong constraint
system suit the cross-cutting "configuration should be data-driven" requirement
(numbering schemes, risk scoring, approval workflows stored as structured config
rows).

**Pros:** one production target to operate and back up; JSONB for flexible
configuration without schema churn; proven under Docker Compose with named volumes.

**Cons:** contributors need Docker (or a local PostgreSQL) to exercise the full
feature set; SQLite drift risk is mitigated by keeping SQLite-only usage to fast unit
tests, with integration tests running against PostgreSQL.

---

## 2026-07-25 — Frontend framework

**Problem:** Need a modern, maintainable frontend framework capable of rich data
tables, dashboards, filtering, and light/dark theming, realistic for long-term
maintenance by autonomous agents.

**Options considered:**
- **React + TypeScript + Vite** — largest ecosystem and component-library choice
  (tables, forms, charts), the framework autonomous coding agents most frequently have
  deep training exposure to, fast Vite dev server and builds.
- **Vue 3 + TypeScript + Vite** — also explicitly acceptable per the spec, excellent
  ergonomics (Composition API), somewhat smaller ecosystem of enterprise data-grid and
  dashboard component libraries than React.
- **Svelte/SvelteKit** — excellent performance and small bundles, but a materially
  smaller ecosystem for the dense CRUD/reporting UI this product needs, and less
  training-data exposure for autonomous agents, raising long-term maintenance risk.

**Chosen:** React + TypeScript + Vite.

**Reason:** The spec accepts either React or Vue and asks that the decision be
recorded. React's larger ecosystem of table/grid, form, and charting libraries
directly serves the document lists, NCR boards, calibration schedules and SPC charts
this product needs across many modules. Its ubiquity also reduces the risk that a
future autonomous agent session lacks strong working knowledge of the framework.

**Pros:** enormous component/library ecosystem; TypeScript-first tooling; Vite gives
fast HMR and builds; easy to hire/onboard against (human or agent).

**Cons:** React's flexibility means conventions must be documented explicitly (see
[CodingStandards.md](CodingStandards.md)) to avoid architectural drift across many
independent contributions — mitigated by a documented feature-folder structure and
component conventions.

---

## 2026-07-25 — Multi-tenancy and future SaaS shape

**Problem:** The product must stay self-hosted-first and single-tenant-simple today,
while remaining able to support a future hosted/SaaS offering with organisation
separation, without building SaaS features now.

**Options considered:**
- **Shared schema with an `organisation_id` column on tenant-scoped tables** — one
  database serves all organisations; every tenant-scoped row carries an
  `organisation_id` foreign key; row-level filtering happens in the service layer (and
  can later be enforced with PostgreSQL row-level security).
- **Schema-per-tenant** — one PostgreSQL schema per organisation in a shared database;
  stronger isolation, but heavier migration fan-out (every schema needs every
  migration applied) and awkward for a single self-hosted instance that only ever has
  one organisation.
- **Database-per-tenant / instance-per-tenant** — strongest isolation; matches the
  spec's own suggested future hosted shape ("multiple Docker instances managed on a
  server"), but is operationally the hosting layer's job, not the application schema's
  job.

**Chosen:** Shared schema with an `organisation_id` column, seeded today with exactly
one `organisations` row for the self-hosted case. Hosted/SaaS is expected to be
achieved primarily by running one Docker instance per organisation (each with its own
single-row `organisations` table and its own database), matching the spec's suggested
future shape — not by multiplexing many organisations inside one running instance.

**Reason:** This gives self-hosting today its simplest possible shape (one
organisation, one instance, one database) while keeping every tenant-scoped table
already carrying the column a future hosted mode would need, whichever hosting
strategy (shared instance or instance-per-tenant) is ultimately chosen. It costs
almost nothing now: Milestone 0 introduces the `organisations` table and a
database-driven `configuration` table scoped to it, proving the pattern end-to-end
without building authentication, tenant switching, or any other SaaS feature.

**Pros:** low cost today; does not foreclose either future hosting strategy; makes
"configuration is database-driven" (a cross-cutting spec requirement) concrete from
Milestone 0 onward; every future module's tables are designed tenant-scoped from day
one instead of retrofitted later.

**Cons:** shared-schema row filtering requires discipline in the service layer to
never leak cross-organisation data — documented as a mandatory review checklist item
in [CodingStandards.md](CodingStandards.md) once auth/organisations are implemented in
Milestone 1.

---

## 2026-07-25 — API versioning strategy

**Problem:** The API will evolve across many modules and milestones; breaking changes
must be possible without breaking existing clients (including the bundled frontend
during rolling upgrades).

**Options considered:**
- **URL path versioning (`/api/v1/...`)** — explicit, visible in logs and browser
  tools, trivial to route, well understood.
- **HTTP header versioning (`Accept: application/vnd.openqms.v1+json`)** — cleaner
  URLs, but harder to explore/debug manually and less common in FastAPI examples and
  tooling (e.g. auto-generated OpenAPI docs handle path versioning more naturally).
- **No explicit versioning (evolve in place)** — simplest short-term, but breaks the
  spec's requirement to document explicit API versioning and risks silent breaking
  changes for self-hosted operators who upgrade on their own schedule.

**Chosen:** URL path versioning under `/api/v1/`.

**Reason:** Simplest to implement, debug, and document; every module's router mounts
under a versioned prefix from the start, so introducing `/api/v2/` later (if ever
needed) does not require restructuring existing modules.

**Pros:** visible and explorable; trivial FastAPI `APIRouter(prefix="/api/v1")`
composition per module; self-hosted operators can see exactly which contract they are
running against.

**Cons:** running two versions in parallel long-term means duplicated router code
until the old version is retired — acceptable, since the project intends to avoid
breaking `v1` for as long as practical rather than version frequently.

---

## 2026-07-25 — Backend dependency management

**Problem:** Need reproducible, fast, Docker-friendly Python dependency management
that a long series of autonomous agent sessions can operate without ambiguity.

**Options considered:**
- **uv (Astral)** — single static binary, very fast resolves/installs, native
  `pyproject.toml` + lockfile (`uv.lock`) support, increasingly the default
  recommendation in the Python packaging ecosystem.
- **Poetry** — mature and widely used, but slower dependency resolution and an extra
  layer of Poetry-specific tooling/config beyond `pyproject.toml`.
- **pip + requirements.txt** — universally understood, but no first-class lockfile
  with hashes and slower iteration without extra tooling (`pip-tools`).

**Chosen:** uv, with dependencies declared in `pyproject.toml` and pinned in
`uv.lock`.

**Reason:** uv's speed materially helps Docker build times (a one-command Compose
startup is a hard requirement) and agent iteration speed, while `pyproject.toml` stays
the standard, tool-agnostic dependency manifest so nothing is locked into a
non-standard format.

**Pros:** fast installs in Docker layer-cached builds; single lockfile for
reproducibility; standard `pyproject.toml` metadata readable by any tool.

**Cons:** newer tool than Poetry/pip — mitigated by uv's stable 1.0+ CLI and growing
adoption; documented explicitly in [CodingStandards.md](CodingStandards.md) and
[Docker.md](Docker.md) so no session has to guess the command.

---

## 2026-07-25 — Frontend package manager

**Problem:** Need a frontend package manager that works everywhere (contributor
machines, CI, Docker builds) with minimal setup friction.

**Options considered:**
- **npm** — ships with Node.js, zero extra install, universally available.
- **pnpm** — faster installs and disk-efficient via a content-addressable store, but
  requires an extra global install step before first use.
- **yarn (classic or berry)** — mature, but adds another lockfile format and, for
  Yarn Berry, a PnP resolution model that occasionally trips up tooling expecting a
  `node_modules` tree.

**Chosen:** npm, with `package-lock.json` committed.

**Reason:** Zero-friction: any environment with Node.js already has npm, which matters
for a project designed to be picked up cold by a new agent session or contributor with
no assumed global tooling beyond Node and Docker.

**Pros:** no extra install step; universally documented; lockfile committed for
reproducible installs in Docker builds and CI.

**Cons:** slower installs and more disk usage than pnpm — acceptable given the
project's frontend dependency surface is modest in Milestone 0 and npm's ubiquity is
worth more than the speed difference at this scale.

---

## 2026-07-25 — Primary key strategy

**Problem:** Need a primary key strategy for database tables that stays safe under
future multi-instance/hosted deployments (see the multi-tenancy decision above),
where IDs may need to be generated by more than one process without collision.

**Options considered:**
- **Auto-incrementing integer/bigint** — simplest and most compact, but collides
  across independently-seeded databases (a problem if data is ever merged or
  synchronised across self-hosted/hosted instances) and leaks row counts.
- **UUID (v4, random)** — globally unique without coordination, supported natively by
  PostgreSQL (`uuid` type) and by SQLAlchemy 2.0's `Uuid` type across PostgreSQL and
  SQLite; widely understood.
- **UUID v7 (time-ordered)** — same collision-safety as v4 with better index locality
  (roughly sortable by creation time), but requires an extra library since Python's
  standard library does not generate v7 natively.

**Chosen:** UUID v4 primary keys (`uuid.uuid4`), generated application-side via
SQLAlchemy's `Uuid` column type, for all new tables.

**Reason:** Collision-safety across independently-seeded self-hosted instances matters
more at this stage than index locality. UUID v4 needs no extra dependency (Python's
standard library `uuid` module is sufficient), keeping Milestone 0 dependency-light.
Revisit UUID v7 later if index locality on very large tables becomes a measured
problem (see [FutureIdeas.md](FutureIdeas.md)).

**Pros:** globally unique without coordination; no extra dependency; identical column
type works on PostgreSQL and SQLite; safe if instances are ever merged or
synchronised.

**Cons:** slightly larger index footprint than bigint; worse B-tree locality than
sequential IDs — not a concern at Milestone 0 scale, revisit if it becomes measurable.

---

## 2026-07-25 — Milestone 0 scope boundary

**Problem:** The spec asks for a small, Docker-smoke-testable vertical foundation
before any module work begins. Need to decide exactly what is in and out of scope to
avoid the "overcomplicated ERP" failure mode the spec explicitly warns against.

**Options considered:**
- **Build the first real module (e.g. Document Management) immediately** — delivers
  visible product value sooner, but skips the platform foundation (health checks, DB
  baseline, CI-less but testable Docker setup) that every later module depends on,
  risking rework.
- **Build a full auth/multi-tenant system first** — front-loads complexity the spec
  explicitly says to defer ("design must permit future hosted/SaaS deployment without
  implementing SaaS features now").
- **Build a minimal platform vertical slice only** — backend health/readiness
  endpoints, a database baseline that proves the organisation-scoped configuration
  pattern, a frontend shell that displays API health, and one-command Compose; no
  auth, no modules yet.

**Chosen:** Minimal platform vertical slice (the third option), detailed in
[.hermes/plans/2026-07-25-milestone-0-foundation.md](../.hermes/plans/2026-07-25-milestone-0-foundation.md).

**Reason:** Matches the spec's explicit scope discipline instruction and gives every
later milestone a working, tested, Docker-smoke-tested foundation (project structure,
lint/type/test commands, migration workflow, health checks) to build on, without
speculative auth or module code that might need to be reworked once real requirements
land in Milestone 1.

**Pros:** fastest path to a genuinely working, smoke-testable full-stack skeleton;
nothing built speculatively; every later milestone inherits a proven pattern instead
of guessing one.

**Cons:** no user-visible product feature ships in Milestone 0 — acceptable, since
[CurrentStatus.md](CurrentStatus.md) and [Roadmap.md](Roadmap.md) make this explicit
and the next batch (Milestone 0 implementation) is scoped to be small and fast.

---

## 2026-07-25 — Frontend styling approach

**Problem:** [CodingStandards.md](CodingStandards.md) commits to picking one styling
approach and documenting it once Milestone 0 builds the frontend shell, rather than
letting each component invent its own. Needed something that supports accessible
light/dark theming with minimal dependency weight for a health-check-only screen.

**Options considered:**
- **Plain CSS with custom properties (CSS variables) + a `data-theme` attribute** —
  zero extra dependencies, themes are a flat set of variables swapped by one
  attribute, works with any future component approach.
- **A component library (e.g. MUI, Chakra, Mantine)** — batteries-included
  components and theming, but a heavy dependency and an opinionated design system to
  commit to before any real product screen exists to justify the choice.
- **CSS-in-JS (styled-components, Emotion)** — colocates styles with components, but
  adds a runtime dependency and build-time complexity Milestone 0's single screen
  does not need.
- **Utility-first CSS (Tailwind)** — fast to write once learned, but adds a build
  pipeline dependency and a class-naming convention across every future module before
  there is a real design system to validate it against.

**Chosen:** Plain CSS with custom properties, themed via a `data-theme` attribute on
`<html>` set by `shared/theme/ThemeProvider.tsx`.

**Reason:** Milestone 0 has exactly one screen; committing to a component
library or CSS-in-JS runtime now would be a speculative bet ahead of any real product
UI. CSS variables give light/dark theming (respecting `prefers-color-scheme`, with a
user-toggle override persisted to `localStorage`) with no added dependency, and don't
foreclose adopting a component library later once real product modules (data tables,
forms) make that trade-off worthwhile.

**Pros:** zero extra dependencies; themes fully expressed as a small set of CSS
variables; no build-time cost; trivially inspectable in devtools.

**Cons:** no pre-built component primitives (buttons, tables, dialogs) — acceptable
since Milestone 0 has no such components yet; revisit when a module needs a data grid
or complex form library.

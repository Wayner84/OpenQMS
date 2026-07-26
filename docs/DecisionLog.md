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

---

## 2026-07-25 — Authentication: password hashing and token revocation strategy

**Problem:** Milestone 1 needs real user accounts, password storage, and JWT issuing/
validation, per
[the Milestone 1 plan](../.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md).
Three sub-decisions: which password hashing library, which JWT library, and how
logout/revocation works without adding infrastructure (Redis, a session table) this
milestone doesn't otherwise need.

**Password hashing options considered:**
- **`passlib[argon2]`** — the traditional choice, but effectively unmaintained (no
  release since 2020) and has had compatibility breaks with newer `argon2-cffi`
  releases it wraps.
- **`argon2-cffi` directly** — the same underlying Argon2 C library, actively
  maintained, a smaller and simpler API (`PasswordHasher().hash()`/`.verify()`) for
  exactly the one algorithm the spec requires.

**Chosen:** `argon2-cffi` directly, Argon2id (`argon2-cffi`'s default variant).

**JWT library options considered:**
- **`PyJWT`** — small, actively maintained, the most common minimal JWT library for
  Python.
- **`python-jose`** — broader (JWS/JWE/JWK), but heavier than needed for one HS256
  signing/verification use case.

**Chosen:** `PyJWT`, HS256, secret from a required `JWT_SECRET_KEY` environment
variable with no default (the app refuses to start without one — see
`backend/app/core/config.py`).

**Token revocation options considered:**
- **Refresh tokens + a server-side session/blocklist table** — the conventional
  "proper" design, but adds a second token type, rotation logic, and a table this
  milestone doesn't otherwise need.
- **A pure stateless JWT with no revocation at all** — simplest, but a "logout"
  button that does nothing until the token naturally expires is a poor security
  property for a QMS that will hold access-controlled records.
- **A `token_version` integer column on `users`, embedded in the JWT as a `ver`
  claim** — logout increments it; `get_current_user` rejects any token whose `ver`
  doesn't match the user's current value. Coarse (revokes every outstanding token for
  that user, not just the current device/session) but requires no new
  infrastructure and no second token type.

**Chosen:** the `token_version` column, with a 60-minute default access-token expiry
(`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`) so the blast radius of an unrevoked token is
bounded even between explicit logouts.

**Pros:** no Redis/session-store dependency; one extra integer column; simple to
reason about and test; bounded exposure window via short-lived tokens.

**Cons:** logout revokes *all* of a user's sessions at once, not just the current
one — acceptable for Milestone 1's scope (no "log out other devices" UX is
promised); revisit with real refresh tokens if per-device session management is ever
needed (see [FutureIdeas.md](FutureIdeas.md)).

---

## 2026-07-25 — Bootstrap admin mechanism

**Problem:** A fresh self-hosted instance needs exactly one admin account to exist
after first startup, without a committed default password (a well-known security
anti-pattern) and without any manual out-of-band step beyond `docker compose up`.

**Options considered:**
- **A committed default admin/password** (e.g. `admin`/`admin`) — rejected outright:
  a well-known, real-world source of compromised self-hosted deployments.
- **A required interactive setup wizard on first web visit** — safe, but adds a
  first-run UI flow this milestone doesn't otherwise need, and complicates the
  Docker smoke test (no clean way to script "the first browser visit" as a
  reproducible test step).
- **Environment-variable-driven bootstrap, run once at backend startup, before
  Uvicorn starts serving** (`BOOTSTRAP_ADMIN_EMAIL` required to opt in;
  `BOOTSTRAP_ADMIN_PASSWORD` optional — if unset, a random password is generated
  with `secrets.token_urlsafe` and logged once at `WARNING` level, never persisted
  anywhere but the hashed column) — no committed secret, no required UI flow,
  scriptable and testable, and idempotent (a no-op once any user exists).

**Chosen:** the environment-variable-driven bootstrap
(`backend/app/core/bootstrap.py`), invoked from `docker-entrypoint.sh` after
`alembic upgrade head` and before Uvicorn starts.

**Reason:** Matches the "no secrets committed" security baseline
([Architecture.md](Architecture.md#security-baseline)) while still giving a
self-hosted operator a working login immediately after `docker compose up --build`
with zero manual database steps — the generated password is readable via
`docker compose logs backend` on first boot.

**Pros:** no committed credential ever; idempotent and safe to run on every restart;
no new UI surface required this milestone; fully unit-testable
(`backend/tests/unit/test_bootstrap.py`).

**Cons:** an operator who doesn't check the backend logs promptly after first boot
could have a generated password logged and then rotated out of the log buffer with
no other way to recover it short of re-triggering bootstrap by deleting the user row
directly in the database — acceptable for Milestone 1 given `BOOTSTRAP_ADMIN_PASSWORD`
is always available as an explicit alternative for operators who want a known value.

## 2026-07-26 — People module: `is_employee`/`company_id` invariant enforced at the schema layer, not a DB constraint

**Problem:** A `people` row must be either an employee (`is_employee=true`,
`company_id=null`) or a company contact (`is_employee=false`, `company_id` set) —
never both, never neither. Where should this rule live?

**Options considered:**
- **A PostgreSQL `CHECK` constraint** on the `people` table — enforces the invariant
  even against direct database writes or a future bulk-import path, but SQLite (used
  for the fast unit test suite per [Contributing.md](Contributing.md)) has weaker
  `CHECK` support in this SQLAlchemy version and the ORM-level unit tests
  (`backend/tests/unit/test_people_models.py`) intentionally construct both employee
  and contact rows directly to test the mapping, independent of the invariant.
- **A Pydantic `model_validator` on `PersonWriteRequest`** (chosen) — rejects a
  contradictory request with `422` before it reaches the service or database layer.

**Chosen:** schema-level validation only
(`backend/app/modules/people/schemas.py::PersonWriteRequest._check_employee_company_invariant`).

**Reason:** Every write path in Milestone 1 goes through the API (no bulk import, no
direct-database admin tooling yet), so schema-level enforcement covers every real
write today while keeping the ORM model free to represent either state for testing
and any future service-layer code (e.g. a bulk import) that needs to construct rows
before validating them as a batch.

**Trade-off, revisit when relevant:** this does not protect against a future
direct-database write or bulk import bypassing the API layer. If/when Task 30-style
bulk import work begins, reconsider adding a `CHECK` constraint (PostgreSQL-only,
via a targeted migration) at that point rather than deferring indefinitely.

## 2026-07-26 — Frontend token storage and mid-session 401 handling

**Problem:** Where should the frontend hold the JWT access token issued by
`POST /api/v1/auth/login`, and how should the app react when a token that was valid
at page load stops working partway through a session (natural 60-minute expiry per
[DecisionLog.md](DecisionLog.md#2026-07-25-authentication-password-hashing-and-token-revocation-strategy),
a `POST /auth/logout` from another tab, or an admin deactivating the account)?

**Options considered:**
- **`localStorage`** — survives tab/browser close, but keeps a live bearer token
  around indefinitely with no corresponding server-side session to revoke it early
  (Milestone 1 has no refresh tokens or session table by design), which is more
  standing exposure than the access-token-only design intends.
- **An in-memory-only token (React state, no storage)** — least persistent, but loses
  the session on every full page reload, forcing a re-login far more often than a
  60-minute-expiry token justifies.
- **`sessionStorage`** (chosen) — cleared automatically when the tab/browser closes,
  matching the "don't keep more standing exposure than necessary" posture of the
  backend's short-lived, non-refreshable token design, while surviving an in-tab
  reload.

**Chosen:** `sessionStorage`, wrapped by `frontend/src/shared/auth/tokenStore.ts` so
no other module touches Web Storage directly.

**Reason:** Matches the backend's access-token-only trade-off (see the linked entry
above) instead of fighting it with a longer-lived client-side cache.

A separate but related problem: `AuthContext`'s mount-time check
(`GET /api/v1/auth/me`) only catches a bad token at page load. Once Users and People
API calls exist beyond this slice, any of them can get back a `401` mid-session. A
tiny pub/sub, `frontend/src/shared/auth/sessionEvents.ts`, lets the shared API client
(`shared/api/client.ts`, which has no React dependency) notify `AuthContext` when a
request that carried a token comes back `401`; `AuthContext` resets to logged-out,
and `ProtectedRoute` redirects to `/login`. The 401-with-no-token case (e.g. a wrong
password on the login form itself) is deliberately excluded from this notification —
`shared/api/client.ts`'s `skipAuth` option keeps `POST /auth/login` from ever sending
an existing token, so a stale-but-still-valid session can never be misread as an
invalid-credentials response and cleared by mistake.

**Trade-off:** this is all-sessions-only feedback (matching the backend's
`token_version` revocation granularity — see the linked entry) and client-side only;
every action it gates is still re-enforced by the backend regardless of what the UI
shows.

## 2026-07-26 — `react-router-dom` upgraded to v7 for moderate open-redirect advisories; residual high-severity RSC advisory accepted as not applicable

**Problem:** `react-router-dom@6.30.4` (the version this slice's `npm install` first
pulled in, and the latest available `6.x` release — no patched `6.x` exists) carries
two moderate advisories reachable by this app's actual usage: an open-redirect-to-XSS
issue in `<Link>`/`useNavigate` path resolution (GHSA-jjmj-jmhj-qwj2) and a related
backslash-path bypass (GHSA-wrjc-x8rr-h8h6) — both relevant here because
`LoginPage.tsx` and `ProtectedRoute.tsx` build `<Navigate>` targets from
router-supplied `location` values.

**Options considered:**
- **Stay on `6.30.4` and defer**, per the existing posture for the dev-only ESLint/
  Vite `npm audit` findings recorded in [CurrentStatus.md](CurrentStatus.md) — rejected
  here because those findings are dev-tooling-only, while this is a runtime dependency
  in the exact code path (login/protected-route redirects) this slice just built.
- **Upgrade to `react-router-dom@7.18.1`** (chosen) — fixes both advisories above
  (`>=7.18.0`); requires removing the now-unnecessary `future` flags from
  `BrowserRouter` (v7 defaults to that behaviour) and one `await` on `navigate()` in
  `LoginPage.tsx` (its return type changed to `Promise<void>`).

**Chosen:** `react-router-dom@7.18.1`.

**Reason:** Fixes both advisories this app's declarative-mode usage
(`BrowserRouter`/`Routes`/`Route`/`Navigate`/`Outlet`/`useNavigate`/`useLocation`) can
actually reach, for a two-line code change plus a `package.json` bump.

**Residual finding, accepted:** `npm audit` still reports one high-severity advisory
against `react-router` (GHSA-qwww-vcr4-c8h2, "RSC Mode CSRF Bypass") for the range
`>=7.12.0 <8.3.0`, with no released fix as of this entry. It describes a bypass in
React Router's RSC (React Server Components) / data-router server-action mode. This
app uses none of that: no `RouterProvider`/data router, no `<Form>` actions, no
server loaders/actions, only the plain declarative components listed above. Tracked
here rather than silently ignored; revisit if a future milestone adopts data-router
or RSC mode, or when an upstream fix ships.

## 2026-07-26 — Milestone 1 closeout: login timing side-channel and a React StrictMode `mountedRef` bug

**Problem:** Final Milestone 1 validation (backend/frontend gates, real-PostgreSQL
migration cycle, dependency audits, an independent security/tenant-isolation review,
and — critically — a real browser-driven Docker Compose smoke test, not just the
mocked-API Vitest suite) surfaced two defects that every prior automated gate had
missed.

**Finding 1 — login timing side-channel.** The independent security review found that
`authenticate_user` (`backend/app/modules/auth/service.py`) used
`if user is None or not user.is_active or not verify_password(...)`. Python's `or`
short-circuits, so the deliberately-slow Argon2id `verify_password` call only ran when
a user existed **and** was active. An unknown-email or deactivated-account login
therefore returned in normal query time, while a real, active account with a wrong
password took measurably longer — an identical response body/status (already
correctly enforced and tested) does not prevent an attacker enumerating valid, active
accounts by response *timing* alone. Existing tests only asserted body/status
equality, never call counts on the verification function, so this was invisible to
the suite.

**Fix:** `authenticate_user` now always calls `verify_password`, against a module-level
dummy Argon2id hash when no user matches the supplied email, so an unknown-email
lookup pays the same verification cost as a wrong-password one on a real account. Two
new unit tests (`test_authenticate_user_performs_password_verification_even_for_unknown_email`,
`...for_inactive_user`) assert `verify_password` is called exactly once regardless of
whether the user exists or is active, confirmed RED against the old code before the
fix and GREEN after.

**Finding 2 — a `mountedRef` unmount-safety guard was permanently broken by React 18
StrictMode's development double-invoke.** `UsersPage`, `CompaniesPage`, and
`PeoplePage` each guard post-await `setState` calls with `if (mountedRef.current)`,
where `mountedRef = useRef(true)` and a `useEffect(() => () => { mountedRef.current =
false; }, [])` cleared it only on unmount. `frontend/src/main.tsx` renders the app
inside `<StrictMode>`, which deliberately mounts, cleans up, and re-mounts every
component once in development to surface missing-cleanup bugs. Because nothing ever
set `mountedRef.current` back to `true` on (re-)mount, that simulated first
mount/cleanup left it permanently `false` — silently dropping every subsequent
`setState` call in the component, including the one that turns off the initial
loading state. In a real browser, all three pages were stuck on "Loading…" (or a
create/update button stuck reading "Creating…"/"Saving…" forever) from the moment
they mounted. This was invisible to the existing 83 Vitest/RTL tests because plain
`render()` does not wrap components in `<StrictMode>`. It was only found by scripting
a real headless-browser walkthrough of the Docker Compose dev stack (bootstrap admin
login → create/deactivate a user → create a company/contact), per the Milestone 1
plan's Docker smoke test acceptance criterion.

**Fix:** all three effects now reset `mountedRef.current = true` at the start of the
effect body, in addition to the existing cleanup that sets it `false`, per the pattern
now documented in
[CodingStandards.md](CodingStandards.md#frontend-react-typescript). A new
`<StrictMode>`-wrapped test was added to each of the three pages' test files,
confirmed RED against the old code (reproducing the exact "stuck on Loading…"
symptom) and GREEN after the fix.

**Why this matters beyond the two fixes:** neither defect was reachable by unit
tests, integration tests against real PostgreSQL, or a mocked-API Vitest run — all of
which passed throughout. Both were only found by the parts of the Milestone 1
acceptance criteria that exercise the *real* stack end-to-end (an independent
security review reading the actual code path, and a real browser against a real
`docker compose up` dev-mode frontend). This is the concrete argument for keeping
both of those steps as mandatory milestone-closeout gates, not optional nice-to-haves,
for every future milestone.

## 2026-07-26 — Document Management: schema, numbering, and the deferred `audit_log` table

**Problem:** [docs/modules/DocumentManagement.md](modules/DocumentManagement.md) (written
before Milestone 1 existed) sketched `document_approvals.approver_id` and the
acknowledgement record's actor as referencing `people.id`, and
[Database.md](Database.md#soft-delete-and-audit-trail) tied introducing a generic
`audit_log` table to "the first module that needs it (Document Management,
Milestone 2)". Both needed a real decision once Milestone 2 implementation started.
Full reasoning also recorded in
[.hermes/plans/2026-07-26-milestone-2-document-management.md](../.hermes/plans/2026-07-26-milestone-2-document-management.md#design-decisions-made-in-this-plan-refining-the-planned-module-doc).

**Decision 1 — `document_approvals`/`document_acknowledgements` reference `users.id`,
not `people.id`.** Approving and acknowledging are actions performed by an
authenticated API caller; Milestone 1 added no link between a `users` row and a
`people` row, and approving/acknowledging must be attributed to the verified
`current_user`, not an arbitrary `people` row a caller could claim to be. Using
`users.id` matches the `created_by_id`/`updated_by_id` attribution pattern already
established on `companies`/`people` themselves. `documents.owner_id` still
references `people.id` as originally planned, since ownership is an organisational
assignment (who this document belongs to), not an action performed through the API —
it can validly name someone without a login.

**Decision 2 — no generic `audit_log` table in Milestone 2.** `document_versions`
(immutable revision history) and the `document_approvals`/`document_acknowledgements`
tables (added in a later Milestone 2 slice) are themselves immutable,
actor-and-timestamp-stamped audit records for everything that matters in document
control. A separate generic audit table would duplicate that without adding value
yet, and a cross-cutting instrumentation layer for every table's mutations is a
materially larger, separate piece of work than this milestone's vertical slice.
`documents.deleted_at` (soft delete) **is** implemented now, since it is directly
needed and narrowly scoped — see [Database.md](Database.md#soft-delete-and-audit-trail).

**Decision 3 — numbering is organisation-wide, generated via a `configuration` row.**
A `document_numbering_scheme` row (`{"prefix", "separator", "padding",
"next_sequence"}`) is seeded per organisation by the schema migration and read/
incremented with `SELECT ... FOR UPDATE` under PostgreSQL, so concurrent document
creation can't allocate the same number twice, per the spec's "no hard-coded business
rules" requirement. Per-category or per-document-type numbering is a noted future
improvement, not built speculatively now.

**Pros (all three):** no premature cross-module linkage table; no premature generic
instrumentation layer; numbering stays configurable without a deployment. **Cons:**
decision 1 means a future "who is this person in the system" report can't join
`document_approvals` straight to `people` — acceptable, since `users` and `people`
are already independently addressable and a report can join through `email` if ever
needed; decision 2 will need revisiting if a future module's audit requirements
outgrow per-table immutable trails.

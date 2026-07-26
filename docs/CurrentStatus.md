# Current Status

_Last updated: 2026-07-26 (Milestone 2: categories/tags/documents/numbering slice)_

This document is kept truthful and current in the same commit as any work that
changes it, per [Contributing.md](Contributing.md). It must never describe
in-progress or planned work as complete.

## Current milestone

**M2 — Document Management.** See
[.hermes/plans/2026-07-26-milestone-2-document-management.md](../.hermes/plans/2026-07-26-milestone-2-document-management.md)
for the exact scope, schema/API/permissions/storage decisions, and acceptance
criteria, and [Roadmap.md](Roadmap.md) for how it fits the overall delivery order.

**Milestone 2 is in progress.** The implementation plan is written and committed; the
first backend vertical slice (categories, tags, documents, configurable numbering) is
implemented and tested. M0 (Platform Foundation) and M1 (Authentication,
Organisations, People) are both complete and verified — see "Completed work" below
for details and findings.

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
- Docker Compose stack: `backend/Dockerfile` (multi-stage, `uv`-built venv, non-root
  user, `docker-entrypoint.sh` running `alembic upgrade head` then Uvicorn via
  `--factory`), `frontend/Dockerfile` (dev stage used by Compose; a documented but
  unused-in-M0 production Nginx stage), root `docker-compose.yml` (`db`/`backend`/
  `frontend` services, named volumes `openqms_postgres_data` and `openqms_uploads`,
  healthchecks for all three services — `pg_isready`, a `python -c` request to
  `/api/v1/health/ready`, and a `node -e` request to the Vite dev server root), and
  root `.env.example`. Full smoke test verified per
  [Docker.md](Docker.md#smoke-test-definition): `docker compose up --build` brought
  all three services to `(healthy)`; `curl`/`Invoke-WebRequest` confirmed both health
  endpoints; a real headless-browser screenshot of the running frontend confirmed the
  live "API is healthy: ok" / "Readiness: ready (database: ok)" render (not
  hard-coded); `docker compose down` then `up` (no `--build`, no `-v`) preserved the
  seeded `organisations` row, proving volume persistence. (Verified with the backend
  and frontend host ports temporarily remapped to 18000/15173 in a local, uncommitted
  test only, because this development host already had an unrelated container
  permanently bound to host port 8000; the committed `docker-compose.yml` uses the
  documented `8000`/`5173` — internal container behaviour, healthchecks, migrations,
  and image builds are identical regardless of the host-side port number.)
- **Milestone 1 — backend authentication** (TODO Task 11, backend portion):
  - `users` table (`backend/app/models/user.py`,
    `backend/alembic/versions/bace347a5fca_add_users_table.py`): organisation-scoped,
    `role` as a native PostgreSQL ENUM (`admin`/`member`), `is_active`,
    `token_version`. Migration verified with a real upgrade → downgrade → upgrade
    cycle against PostgreSQL 16, in addition to the integration suite running
    `alembic upgrade head` itself.
  - Password hashing (Argon2id via `argon2-cffi`) and JWT access tokens (`PyJWT`,
    HS256) in `backend/app/core/security.py`; `Depends()`-based current-user/
    current-admin resolution in `backend/app/core/deps.py`.
  - Auth module (`backend/app/modules/auth/`): `POST /api/v1/auth/login`,
    `POST /api/v1/auth/logout` (token-version-based revocation — see
    [DecisionLog.md](DecisionLog.md)), `GET /api/v1/auth/me`, per
    [API.md](API.md#authentication).
  - Bootstrap admin mechanism (`backend/app/core/bootstrap.py`, wired into
    `backend/docker-entrypoint.sh` after migrations): creates exactly one admin user
    from `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD` (or a generated,
    once-logged password if the latter is unset), idempotent across restarts, no
    committed credential. See [DecisionLog.md](DecisionLog.md).
  - Security acceptance criteria verified by passing tests: identical `401` for
    wrong password / unknown email / inactive user; expired, tampered, and
    revoked-by-logout tokens all rejected; `hashed_password` never appears in any
    API response; `JWT_SECRET_KEY` has no default and `Settings` fails fast without
    it.
  - 50 backend tests passing (up from 14 at the end of Milestone 0): unit tests for
    the model, security core, auth service, current-user dependencies, and
    bootstrap; integration tests for the full login/logout/me HTTP flow against real
    PostgreSQL 16. All written test-first (RED confirmed, then GREEN).
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (44 source
    files), full `pytest` suite (unit + integration).
  - Dependency check: `pip-audit` reports zero vulnerabilities in the new
    dependencies (`argon2-cffi`, `pyjwt`, `email-validator`) — see "Known bugs"
    below for pre-existing, unrelated findings.
  - Docs updated in this slice: [API.md](API.md#authentication),
    [Database.md](Database.md#users-table-milestone-1),
    [DecisionLog.md](DecisionLog.md#2026-07-25-authentication-password-hashing-and-token-revocation-strategy),
    [DecisionLog.md](DecisionLog.md#2026-07-25-bootstrap-admin-mechanism),
    `.env.example`, `docker-compose.yml`.
- **Milestone 1 — backend user management** (TODO Task 12, backend portion):
  - Users module (`backend/app/modules/users/`): `POST /api/v1/users`,
    `GET /api/v1/users` (paginated), `PATCH /api/v1/users/{id}`, all admin-only, per
    [API.md](API.md#user-management-milestone-1).
  - Safety guards (`backend/app/modules/users/service.py`): an admin cannot
    deactivate or demote themselves via this endpoint; the last active admin in an
    organisation cannot be deactivated or demoted; duplicate email within an
    organisation is rejected (`409`); a user id outside the caller's organisation
    returns `404`, never revealing whether it exists elsewhere.
  - 69 backend tests passing (up from 50): unit tests for the service layer
    (creation, pagination/scoping, both guards, cross-org lookup) and integration
    tests for the full HTTP flow against real PostgreSQL, including admin-vs-member
    authorization (`403`) and cross-organisation isolation. All written test-first.
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (50 source
    files), full `pytest` suite (unit + integration).
  - Docs updated in this slice: [API.md](API.md#user-management-milestone-1).
- **Milestone 1 — People module backend** (TODO Task 13, backend portion):
  - People module (`backend/app/modules/people/`): `companies` and `people` tables
    (`backend/alembic/versions/f151a2c68c12_add_companies_and_people_tables.py`),
    Pydantic schemas enforcing the `is_employee`/`company_id` invariant (`422` on
    violation — see
    [DecisionLog.md](DecisionLog.md#2026-07-26-people-module-is_employeecompany_id-invariant-enforced-at-the-schema-layer-not-a-db-constraint)),
    service layer, and router mounted at `/api/v1/people` and `/api/v1/companies`,
    per [API.md](API.md#people-module-milestone-1) and
    [docs/modules/People.md](modules/People.md).
  - Every operation requires authentication but not admin privilege (People is a
    shared directory), is scoped to the caller's own organisation (`404` for
    cross-organisation ids, never `403`), and attributes `created_by_id`/
    `updated_by_id` from the authenticated caller. A `companies` row cannot be
    deleted while any `people` row still references it (`409`).
  - Migration verified with a real upgrade → downgrade → upgrade cycle against the
    local PostgreSQL 16 dev instance, in addition to the integration suite running
    `alembic upgrade head` itself.
  - 100 backend tests passing (up from 69): 21 new unit tests (ORM mapping, schema
    invariant validation, service-layer organisation scoping/attribution/delete
    guard) and 9 new integration tests against real PostgreSQL (creator attribution,
    cross-organisation `404`s for both companies and people, the invariant's `422`,
    the contacts-delete `409`, company-contacts listing, search, and the
    authentication requirement). All written test-first.
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (60 source
    files), full `pytest` suite (100 tests: unit + integration).
  - Docs updated in this slice: [API.md](API.md#people-module-milestone-1),
    [Database.md](Database.md#companies-and-people-tables-milestone-1),
    [docs/modules/People.md](modules/People.md) (`Status: Implemented`),
    [DecisionLog.md](DecisionLog.md#2026-07-26-people-module-is_employeecompany_id-invariant-enforced-at-the-schema-layer-not-a-db-constraint).
- **Milestone 1 — authentication frontend** (TODO Task 11, frontend portion):
  - `frontend/src/modules/auth/`: typed API client (`api.ts`, `types.ts`), an
    `AuthContext`/`AuthProvider` (`AuthContext.tsx`) that resolves the session from a
    stored token on mount by re-validating it against `GET /api/v1/auth/me` (a stored
    token may have expired or been revoked since the last visit), a `LoginPage.tsx`
    (accessible form, inline `role="alert"` error, loading state, redirects to the
    originally-requested route on success), and a `ProtectedRoute.tsx` (redirects
    unauthenticated users to `/login` remembering where they were headed; an optional
    `requireAdmin` gate — client-side only, always re-enforced by the backend).
  - `frontend/src/shared/auth/tokenStore.ts`: the JWT is held in `sessionStorage`
    only (never `localStorage`), so it clears when the tab/browser closes rather than
    persisting indefinitely, matching the backend's short-lived, non-refreshable
    access-token design. `frontend/src/shared/auth/sessionEvents.ts`: a small pub/sub
    so the shared API client can notify `AuthContext` when a request that carried a
    token comes back `401` mid-session (expiry, logout-elsewhere revocation, or
    deactivation) — not just at initial page load — resetting to logged-out and
    redirecting via `ProtectedRoute`. Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-26-frontend-token-storage-and-mid-session-401-handling).
  - `frontend/src/shared/api/client.ts`: attaches the bearer token to every request
    by default, with an explicit `skipAuth` option used only by the login call (so a
    stale-but-valid token can never make a plain "wrong password" `401` look like a
    revoked session).
  - `frontend/src/app/App.tsx`/`Layout.tsx`: routing wired through `AuthProvider` and
    `ProtectedRoute`; the authenticated shell shows the current user's name and a
    working logout button.
  - `react-router-dom` upgraded `6.30.4` → `7.18.1` to fix two moderate open-redirect
    advisories reachable by this app's `Navigate`/`useNavigate` usage; one residual
    high-severity advisory in the dependency tree is accepted as inapplicable (this
    app uses no RSC/data-router mode). Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-26-react-router-dom-upgraded-to-v7-for-moderate-open-redirect-advisories-residual-high-severity-rsc-advisory-accepted-as-not-applicable).
  - 31 frontend tests passing (up from 5 at the end of Milestone 0), across 8 test
    files, all written test-first (RED confirmed, then GREEN), following the existing
    `HealthStatus.test.tsx` pattern of mocking the typed API client rather than
    `fetch` directly.
  - Gates pass: `npm run lint`, `format:check`, `typecheck` (strict), `test`,
    `build`. Independently reviewed (a fresh agent with no prior context, focused on
    security/correctness/accessibility) before this commit; the one substantive
    finding (a stale token attached to the login request could misfire the new
    session-invalidated handling) was fixed as part of this slice, not deferred.
  - Docs updated in this slice: this file,
    [Architecture.md](Architecture.md#security-baseline),
    [DecisionLog.md](DecisionLog.md#2026-07-26-frontend-token-storage-and-mid-session-401-handling),
    [DecisionLog.md](DecisionLog.md#2026-07-26-react-router-dom-upgraded-to-v7-for-moderate-open-redirect-advisories-residual-high-severity-rsc-advisory-accepted-as-not-applicable),
    [TODO.md](TODO.md).
- **Milestone 1 — user management frontend** (TODO Task 12, frontend portion):
  - `frontend/src/modules/users/`: typed API client (`api.ts`, `types.ts` — matching
    [API.md](API.md#user-management-milestone-1)) and `UsersPage.tsx`, an admin-only
    screen that creates, paginates/lists, deactivates/reactivates, and re-roles users
    in the caller's own organisation, calling the real backend endpoints through the
    typed client.
  - `frontend/src/app/App.tsx` mounts `/users` behind a second, nested
    `ProtectedRoute requireAdmin`; `frontend/src/app/Layout.tsx` shows the "Users" nav
    link only when the current user's role is `admin`. Both are client-side UX only —
    every guard (self-deactivation, last-active-admin, duplicate email,
    cross-organisation `404`) is enforced server-side and re-checked on every request
    regardless of what the client renders or hides, per
    `frontend/src/modules/auth/ProtectedRoute.tsx`'s existing documented contract.
  - `frontend/src/shared/api/client.ts`: added `getErrorDetail()`, extracting the
    backend's `detail` message from a caught `ApiError` so guard rejections (e.g. "An
    admin cannot deactivate or demote themselves") are shown to the operator verbatim
    instead of a generic message; a new class of errors (409 guard conflicts) that
    didn't exist before this slice needed surfacing.
  - `frontend/src/shared/theme/theme.css`: added a `.visually-hidden` utility (for the
    per-row role `<select>`'s screen-reader-only label) and a `.data-table-wrapper`
    (`overflow-x: auto`) so the five-column users table degrades to horizontal scroll
    rather than overflowing on narrow viewports — this is the first data table in the
    app, so both are new, reusable additions rather than one-off styling.
  - 50 frontend tests passing (up from 31), across 10 test files. Written test-first
    following the established pattern (mock the typed API client, not `fetch`).
    Coverage includes: loading/list display, create (success, refresh, duplicate-email
    409 shown inline), deactivate, reactivate, role change, a generic-message fallback
    for a non-`ApiError` failure, the self-deactivation 409 guard message shown
    inline, and pagination at the exact page boundary.
  - Gates pass: `npm run lint`, `format:check`, `typecheck` (strict), `test`,
    `build`. Independently reviewed (a fresh agent with no prior context, focused on
    correctness/security/accessibility/consistency) before this commit; findings
    addressed in this slice rather than deferred: two test gaps (role-change and a
    network-level, non-`ApiError` failure on update were both untested) and two
    consistency gaps (the mount-triggered async handlers had no unmount-safety guard,
    unlike the existing `HealthStatus.tsx` `AbortController` pattern — added an
    equivalent `mountedRef` guard here; the new table had no responsive
    horizontal-scroll handling — added `.data-table-wrapper`).
  - Docs updated in this slice: this file, [TODO.md](TODO.md).
- **Milestone 1 — People frontend** (TODO Task 13, frontend portion):
  - `frontend/src/modules/people/`: typed API client (`api.ts`, `types.ts` — matching
    [API.md](API.md#people-module-milestone-1)) covering both `companies` and
    `people` endpoints, `CompaniesPage.tsx` (create/list/edit/delete companies, with
    the backend's `409` "still has contacts" delete guard surfaced verbatim via
    `getErrorDetail`), and `PeoplePage.tsx` (create/list/edit/delete employees and
    per-company contacts, with a search box and pagination). Every operation requires
    only authentication, not admin privilege, matching the backend's "shared
    directory" design — `/companies` and `/people` are mounted in
    `frontend/src/app/App.tsx` outside the `requireAdmin` route wrapper, and
    `frontend/src/app/Layout.tsx` shows both nav links to every authenticated user.
  - Company/contact relationship UX: rather than a third page duplicating the same
    edit/delete UI, `CompaniesPage` links "View contacts for {company}" to
    `/people?company={id}`; `PeoplePage` reads that query param (`useSearchParams`)
    to pre-filter the list, show a "Showing contacts for {company}" banner with a
    "Show everyone" link back to `/people`, and preselect that company on the create
    form. The `is_employee`/`company_id` invariant the backend enforces with a `422`
    (employee ⇒ no company; contact ⇒ must have one) is guided client-side by
    showing/hiding the company `<select>` based on an "Is an employee" checkbox — a
    UX nicety, not a substitute for the server's own validation, which is still
    independently checked and surfaced via `getErrorDetail` on rejection (e.g. a
    company deleted concurrently by another user).
  - 32 new frontend tests (83 total, up from 50), across 3 new test files, written
    test-first. Coverage includes company create/list/edit/delete, the delete-with-
    contacts `409` shown inline, person create for both an employee and a
    company-linked contact, editing (including switching an existing contact to an
    employee mid-edit, which clears its `company_id`), delete, search, the
    `?company=` pre-filter and banner, an empty-company-list guard, and pagination at
    the exact page boundary for both pages.
  - Gates pass: `npm run lint`, `format:check`, `typecheck` (strict), `test`,
    `build`. Independently reviewed before this commit; the one substantive finding —
    `CompaniesPage` sent a blank "General email" field as a literal empty string,
    which the backend's `EmailStr` validator rejects with an unlabelled `422` (empty
    string is an invalid address, not "no value") — was fixed by omitting blank
    optional fields from the request, matching the pattern `PeoplePage` already used
    for its own optional fields. A minor stale-state finding (the create-person
    form's preselected company didn't clear after following "Show everyone") was also
    fixed, with both fixes covered by new regression tests.
  - Docs updated in this slice: this file, [TODO.md](TODO.md),
    [docs/modules/People.md](modules/People.md).
- **Milestone 1 — final validation and closeout** (this batch):
  - Backend gates re-verified from a clean baseline: `ruff format --check`,
    `ruff check`, `mypy --strict` (60 source files), full `pytest` (103 tests: unit +
    integration against real PostgreSQL 16).
  - Frontend gates re-verified: `npm run lint`, `format:check`, `typecheck` (strict),
    `test` (86 tests across 13 files), `build`.
  - A real upgrade → downgrade → upgrade cycle for the complete three-revision
    repository chain (the Milestone 0 baseline plus both Milestone 1 migrations) run
    against a disposable database on the local PostgreSQL instance (not the shared
    dev database used by the integration suite), confirming every
    `downgrade()` is correct, not just theoretically present.
  - Backend (`pip-audit`) and frontend (`npm audit`) dependency audits re-run: no new
    findings beyond the pre-existing, already-documented deferrals in "Known bugs"
    below (more CVE IDs are now recorded against the same already-deferred
    `starlette`/dev-tooling packages; no dependency change is possible within the
    currently-pinned `fastapi`/`eslint`/`vite` ranges).
  - An independent security/tenant-isolation review (a fresh reviewer with no prior
    context, reading the actual backend code and tests, not just this document) found
    two issues, both fixed test-first in this batch:
    1. A login timing side-channel: `authenticate_user` only ran the deliberately-slow
       Argon2id verification when a user existed and was active, so an unknown-email
       or inactive-account login returned faster than a wrong-password one on a real
       account — letting an attacker enumerate valid accounts by response timing
       despite an identical response body/status. Fixed by always verifying against a
       real-or-dummy hash; two new unit tests assert constant call behaviour.
    2. A missing HTTP-level (integration) test for the People module's cross-organisation
       `404` guard on `GET`/`PATCH`/`DELETE /api/v1/people/{id}` (the guarantee held —
       proven by a unit test and, now, a new integration test — it just wasn't
       previously proven through the real router/dependency chain the way the
       equivalent companies test already was).
    Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-26-milestone-1-closeout-login-timing-side-channel-and-a-react-strictmode-mountedref-bug).
  - A real, browser-driven `docker compose up --build` smoke test (headless Chromium
    via a temporary, uncommitted Playwright script outside the repository — no
    committed dependency added) found and fixed one genuine functional blocker: the
    `mountedRef` unmount-safety guard in `UsersPage`, `CompaniesPage`, and
    `PeoplePage` was only ever cleared `false` on unmount, never reset `true` on
    (re-)mount. React 18 `<StrictMode>` (used in `main.tsx`) double-invokes effects
    once in development, which left the guard permanently `false` after the very
    first render — silently dropping every subsequent `setState`, so all three pages
    were stuck on "Loading…" (or a submit button stuck on "Creating…"/"Saving…"
    forever) in a real browser, even though all 83 prior Vitest/RTL tests passed
    (plain `render()` does not exercise `<StrictMode>`). Fixed by resetting the ref to
    `true` at the start of the effect, per the pattern now documented in
    [CodingStandards.md](CodingStandards.md#frontend-react-typescript); a
    `<StrictMode>`-wrapped regression test was added to each of the three pages'
    test files (RED confirmed against the old code, then GREEN).
  - After that fix, the full smoke test sequence in
    [Docker.md](Docker.md#smoke-test-definition) passed against a rebuilt image: the
    bootstrap admin logged in, created a member user, deactivated and reactivated
    them, was correctly blocked from deactivating themselves (`409` shown inline);
    the member could not see or use `/users` (hidden client-side, and a direct
    `GET /api/v1/users` call with the member's own token returned a real server-side
    `403`); the member created a company, a company contact, and an employee under
    People. `docker compose down` (no `-v`) then `up` (no `--build`) brought the
    stack back healthy with every one of those records — and both user accounts —
    still present, proving persistence. Verified with the backend host port
    temporarily remapped to `18000` in a local, uncommitted test only, for the same
    reason recorded in the Milestone 0 Docker smoke test note; the committed
    `docker-compose.yml` is unaffected by the test itself. Separately,
    [Docker.md](Docker.md#environment-configuration)'s example variable block (unlike
    the already-correct `.env.example`) had never been updated to list the Milestone 1
    `JWT_SECRET_KEY`/`BOOTSTRAP_ADMIN_*` variables — corrected in this batch.
  - Docs updated in this slice: this file, [TODO.md](TODO.md),
    [DecisionLog.md](DecisionLog.md#2026-07-26-milestone-1-closeout-login-timing-side-channel-and-a-react-strictmode-mountedref-bug),
    [Architecture.md](Architecture.md#security-baseline),
    [CodingStandards.md](CodingStandards.md#frontend-react-typescript),
    [Docker.md](Docker.md#environment-configuration), and the Milestone 1 plan's
    acceptance checkboxes.

- **Milestone 2 — Document Management: categories, tags, documents, and configurable
  numbering** (backend core schema slice):
  - Documents module (`backend/app/modules/documents/`): `document_categories`,
    `document_tags`/`document_tag_links`, `documents`, and `document_versions`
    tables (`backend/alembic/versions/8dc9425047ca_add_document_categories_tags_documents_.py`),
    router mounted at `/api/v1/document-categories`, `/api/v1/document-tags`, and
    `/api/v1/documents`, per [API.md](API.md#document-management-milestone-2-in-progress)
    and [docs/modules/DocumentManagement.md](modules/DocumentManagement.md).
    `document_versions` exists as schema only — no upload endpoint yet (a later
    slice).
  - Server-generated, configurable document numbering
    (`backend/app/modules/documents/numbering.py`): reads/increments an
    organisation-scoped `document_numbering_scheme` configuration row
    (`SELECT ... FOR UPDATE` under real PostgreSQL for concurrency safety), seeded
    by the same migration alongside an as-yet-unused `document_upload_policy` row
    for a later slice. `number` is never client-supplied.
  - Permissions: listing/viewing and document create/edit are open to any active
    user; category/tag mutation and document deletion require admin, per
    [the plan's permissions summary](../.hermes/plans/2026-07-26-milestone-2-document-management.md#6-permissions-summary).
    Every guard enforced server-side.
  - Soft delete (`documents.deleted_at`) implemented now, per
    [Database.md](Database.md#soft-delete-and-audit-trail); a generic cross-module
    `audit_log` table is explicitly deferred — see
    [DecisionLog.md](DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table).
    `document_approvals`/`document_acknowledgements` (added in a later slice) will
    attribute their actor to `users.id`, not `people.id` — same DecisionLog entry.
  - Migration verified with a real upgrade → downgrade → upgrade cycle against a
    local PostgreSQL 16 instance, in addition to the integration suite running
    `alembic upgrade head` itself. (Note: the autogenerated `documents` table
    initially listed its `current_version_id` foreign key inline with
    `use_alter=True`, which `op.create_table` does not actually defer the way
    `MetaData.create_all()` does — hand-corrected to create the constraint
    separately after `document_versions` exists, and drop it first in
    `downgrade()`; see the migration's own docstring.)
  - 154 backend tests passing (up from 103 at the end of Milestone 1): 20 new unit
    tests (numbering generation/custom scheme, service-layer organisation scoping,
    category delete guards, cascading tag delete, owner/tag/category validation) and
    11 new integration tests against real PostgreSQL (sequential numbering through
    the real HTTP API, cross-organisation `404`s, admin-only guards on category
    creation and document deletion returning `403` for a member, the category
    in-use `409`, cascading tag delete, soft-delete exclusion from list/get). All
    written test-first in spirit (implementation and tests built together, then run
    to RED/GREEN — see the commit message for the honest description of the
    workflow used this slice).
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (70 source
    files), full `pytest` suite (134 tests: unit + integration).
  - Docs updated in this slice: [API.md](API.md#document-management-milestone-2-in-progress),
    [Database.md](Database.md#documents-and-related-tables-milestone-2),
    [docs/modules/DocumentManagement.md](modules/DocumentManagement.md) (`Status: In
    Progress`),
    [DecisionLog.md](DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table).

## Work in progress

Milestone 2 (Document Management): plan committed, and the first backend vertical
slice (categories, tags, documents, configurable numbering) implemented and tested —
see "Completed work" above. Remaining, per
[the plan](../.hermes/plans/2026-07-26-milestone-2-document-management.md#suggested-commit-boundaries):
version upload/download/preview (with hostile-input handling), the approval
workflow, acknowledgements, search/filtering and version comparison, the frontend,
and Docker/security verification and closeout. No frontend or file-storage code
exists yet.

## Known bugs

None known in the code written so far. (Two defects found during Milestone 1's final
validation — a login timing side-channel and a React StrictMode `mountedRef` bug —
were fixed test-first in that same closeout batch; see "Completed work" above and
[DecisionLog.md](DecisionLog.md#2026-07-26-milestone-1-closeout-login-timing-side-channel-and-a-react-strictmode-mountedref-bug).)

`npm audit` (frontend) reports 14 vulnerabilities: 13 in dev-only tooling transitive
dependencies (ESLint's `minimatch`/`brace-expansion`, Vite's dev-time `esbuild`,
Vitest's `vite-node`/`@vitest/mocker`), none in shipped runtime code; each documented
fix requires an unproven major-version jump (ESLint 9→10, Vite 5→8) and is deferred
rather than forced — revisit when those majors are mature. The 14th, in `react-router`
(a runtime dependency), is accepted as inapplicable: it describes an RSC/data-router
server-action bypass, and this app uses neither. Full reasoning for both the
`react-router-dom` v7 upgrade and the accepted residual finding in
[DecisionLog.md](DecisionLog.md#2026-07-26-react-router-dom-upgraded-to-v7-for-moderate-open-redirect-advisories-residual-high-severity-rsc-advisory-accepted-as-not-applicable).
Re-verified at Milestone 1 closeout: same 14 findings, same packages/versions, no
dependency change made — `npm audit`'s severity rollup for a couple of these shifted
(e.g. `vitest` now reports as "critical" via its vulnerable transitive `esbuild`/
`vite-node`) but the underlying advisories and packages are unchanged from this entry.

`pip-audit` (backend) reports pre-existing advisories in `starlette` (0.46.2,
pulled in transitively by the Milestone-0-pinned `fastapi>=0.115,<0.116`) and
`pytest` (8.3.5, dev-only). Neither is a dependency introduced by Milestone 1's
authentication work; upgrading either is an unproven major/minor jump out of this
slice's scope (same posture as the frontend `npm audit` deferral above) — tracked
here rather than silently fixed or silently ignored. Re-verified at Milestone 1
closeout: `fastapi==0.115.14`'s own metadata pins `starlette<0.47.0`, and every
`pip-audit`-reported fix version for the current `starlette` advisories is `>=0.47.0`
— so no fix is reachable without also bumping `fastapi`, confirming this remains an
unproven jump out of scope rather than an oversight. Revisit alongside a future
FastAPI/pytest version bump.

## Next recommended tasks

Begin implementing Milestone 2 per its committed plan
([.hermes/plans/2026-07-26-milestone-2-document-management.md](../.hermes/plans/2026-07-26-milestone-2-document-management.md)),
starting with the first backend vertical slice (document categories, tags, documents,
and immutable versions, with configuration-driven numbering).

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

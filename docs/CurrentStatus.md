# Current Status

_Last updated: 2026-07-30 (Milestone 4: NCR attachments and supplier NCR history slice implemented)_

This document is kept truthful and current in the same commit as any work that
changes it, per [Contributing.md](Contributing.md). It must never describe
in-progress or planned work as complete.

## Current milestone

**M4 — NCR.** See
[.hermes/plans/2026-07-29-milestone-4-ncr.md](../.hermes/plans/2026-07-29-milestone-4-ncr.md)
for the exact scope, schema/API/permissions decisions, and acceptance criteria, and
[Roadmap.md](Roadmap.md#m4-ncr) for how it fits the overall delivery order.

**Milestone 4 is in progress.** The `ncrs`/`ncr_status_history` schema, CRUD, the
full transition workflow, containment/corrective/preventive actions, the four
structured investigation tools, document attachments, and the Suppliers
`ncr-history` read endpoint are implemented and tested (backend only) — see
"Completed work" below. Not yet implemented: PDF export and the frontend. M0
(Platform Foundation), M1 (Authentication, Organisations, People), M2 (Document
Management), and M3 (Products and Suppliers) are all complete and verified —
see "Completed work" below for details and findings.

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
  - Server-generated, configurable document numbering
    (`backend/app/modules/documents/numbering.py`): reads/increments an
    organisation-scoped `document_numbering_scheme` configuration row
    (`SELECT ... FOR UPDATE` under real PostgreSQL for concurrency safety), seeded
    by the same migration alongside a `document_upload_policy` row consumed by the
    upload slice below. `number` is never client-supplied.
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
- **Milestone 2 — secure document version upload, download, and PDF/image preview**
  (backend slice):
  - `backend/app/modules/documents/storage.py`: server-generated `storage_key`
    (never derived from client input — path traversal is structurally impossible,
    not just filtered), extension allow-list + best-effort magic-byte signature
    validation (not the client's declared `Content-Type`), and a streaming
    size-bounded write with SHA-256 checksum computed in the same pass.
    `backend/app/modules/documents/upload_policy.py`: reads the
    `document_upload_policy` configuration row (allowed extensions, max size),
    falling back to a conservative built-in default.
  - Endpoints: `POST /api/v1/documents/{id}/versions` (multipart upload, any active
    user), `GET .../download` (`attachment`), `GET .../preview` (`inline` for
    PDF/PNG/JPEG only, `415` otherwise) — all per
    [API.md](API.md#document-management-milestone-2-in-progress). File access is
    always resolved via `(organisation_id, document_id, version_id)`, never a raw
    path or `storage_key` (never present in any response body).
  - **Independent security/tenant-isolation review** (a fresh agent with no prior
    session context, reading the actual code and tests) found and fixed three
    issues before this slice was committed, none of which the 30+ tests already
    written for the slice had caught:
    1. Starlette's multipart parser spools uploaded files to disk with no size
       limit of its own before the app's per-organisation size check ever runs — a
       disk-exhaustion DoS reachable by any authenticated user. Fixed with a new
       `MaxBodySizeMiddleware` (`backend/app/core/middleware.py`) rejecting an
       oversized request by its declared `Content-Length` before the body is read.
    2. An unlocked version-number race could let two concurrent uploads to the same
       document collide, leaving an orphaned file on disk after an unhandled `500`.
       Fixed with a `SELECT ... FOR UPDATE` lock on the parent document row
       (matching the existing numbering pattern) plus a belt-and-braces
       `IntegrityError` handler that deletes the file before re-raising.
    3. An operator-configured upload policy could name a file extension the
       backend has no `Content-Type` mapping for, crashing the upload path. Fixed
       by filtering configured extensions against the known set, dropping unknown
       ones with a logged warning.
    Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-26-document-upload-request-body-size-cap-version-number-locking-and-upload-policy-extension-validation).
  - New dependency: `python-multipart` (required by FastAPI for `File`/`Form`
    parsing) — `pyproject.toml`/`uv.lock` updated.
  - 170 backend tests passing (up from 134): 34 new unit tests (storage validation
    incl. path-traversal/signature/oversized-file cases, upload-policy fallback and
    extension filtering, the new middleware) and 2 new integration tests (a
    non-admin member upload/download round trip) plus the upload/download/preview
    HTTP-level tests already added before the review (roundtrip, preview
    inline/415, cross-org `404`, disallowed extension, signature mismatch,
    oversized-file `413`, path-traversal filename sanitisation).
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (77 source
    files), full `pytest` suite (170 tests: unit + integration against real
    PostgreSQL 16).
  - Docs updated in this slice: [API.md](API.md#document-management-milestone-2-in-progress),
    [Database.md](Database.md#documents-and-related-tables-milestone-2),
    [Deployment.md](Deployment.md#backups) (uploads volume backup is now real, plus
    reverse-proxy body-size-limit guidance),
    [docs/modules/DocumentManagement.md](modules/DocumentManagement.md),
    [DecisionLog.md](DecisionLog.md#2026-07-26-document-upload-request-body-size-cap-version-number-locking-and-upload-policy-extension-validation),
    `.env.example`, `docker-compose.yml` (`UPLOADS_DIR`).
- **Milestone 2 — document approval and rejection workflow** (backend slice):
  - `document_approvals` table
    (`backend/alembic/versions/ea4516740593_add_document_approvals.py`) and four
    new endpoints — `POST .../submit-for-approval` (any active user),
    `POST .../approve`/`.../reject` (admin only), `POST /documents/{id}/obsolete`
    (admin only, whole-document retirement) — per
    [API.md](API.md#document-management-milestone-2-in-progress). Migration
    verified with a real upgrade → downgrade → upgrade cycle.
  - State machine: `draft` → `in_review` → `approved` (supersedes the previous
    current version → `obsolete`) or `rejected` (terminal for that version);
    `documents.status` is a service-maintained cache that becomes and stays
    `approved` once any version has ever been approved, per
    [docs/modules/DocumentManagement.md](modules/DocumentManagement.md#workflow).
  - **Independent security/tenant-isolation review** (a fresh agent with no prior
    session context) found and fixed two issues before this slice was committed:
    1. A non-admin action (submit-for-approval or reject) could silently un-retire
       an admin-retired document, since neither checked the document's current
       status before writing to it. Fixed by skipping that write when the document
       is already `obsolete`; approve (itself admin-only) deliberately keeps the
       ability to revive a retired document as a legitimate admin decision.
    2. A TOCTOU race in approve/reject (unlike the row-locking already used for
       document numbering and version-number allocation) could let two concurrent
       transactions on the same document both pass their state-machine guard,
       producing two simultaneously-"approved" versions or duplicate approval
       records. Fixed with a shared `_lock_document` helper (`SELECT ... FOR
       UPDATE`, deduplicating a copy of the same lock already used for version-
       number allocation) acquired before reading any version's state.
    Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-26-document-approval-workflow-a-status-cache-integrity-bug-and-a-toctou-race).
  - 188 backend tests passing (up from 170): 13 new unit tests (state transitions,
    the immutable approval record, supersession, the retire-status regression
    tests added after the review) and 5 new integration tests (the full
    approve/supersede flow through the real HTTP API, admin-only guards, the
    required-comment `422`, an `in_review`-state `409`, cross-org `404`s for all
    four workflow endpoints).
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (79 source
    files), full `pytest` suite (188 tests: unit + integration against real
    PostgreSQL 16).
  - Docs updated in this slice: [API.md](API.md#document-management-milestone-2-in-progress),
    [Database.md](Database.md#documents-and-related-tables-milestone-2),
    [docs/modules/DocumentManagement.md](modules/DocumentManagement.md),
    [DecisionLog.md](DecisionLog.md#2026-07-26-document-approval-workflow-a-status-cache-integrity-bug-and-a-toctou-race).
- **Milestone 2 — document acknowledgements** (backend slice):
  - `document_acknowledgements` table
    (`backend/alembic/versions/b8a145cc3e28_add_document_acknowledgements.py`) and
    two new endpoints — `POST .../acknowledge` (any active user, self-only,
    idempotent) and `GET .../acknowledgements` (any active user, paginated list of
    who has acknowledged and when) — per
    [API.md](API.md#document-management-milestone-2-in-progress). Migration
    verified with a real upgrade → downgrade → upgrade cycle.
  - `acknowledged_by_id` is always `current_user.id`; the acknowledge request body
    is empty, so there is no field a client could use to acknowledge on someone
    else's behalf. Re-acknowledging the same version is idempotent (returns the
    existing row via a unique-constraint-aware read-then-fallback-on-`IntegrityError`
    pattern), never a duplicate row or an error.
  - **Independent security/tenant-isolation review** (a fresh agent with no prior
    session context) found **no issues** in this slice — self-only actor
    provenance, idempotency without duplicate rows, any-user list visibility,
    404-not-403 cross-org scoping, and immutability (no update/delete route) were
    all verified as correctly implemented and already test-covered.
  - 196 backend tests passing (up from 188): 5 new unit tests (actor/timestamp
    recording, idempotency, cross-org `404`, listing multiple acknowledgers) and 3
    new integration tests (idempotent-and-listable round trip through the real
    HTTP API, a non-admin member acknowledging, cross-org `404` for both
    endpoints).
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (81 source
    files), full `pytest` suite (196 tests: unit + integration against real
    PostgreSQL 16).
  - Docs updated in this slice: [API.md](API.md#document-management-milestone-2-in-progress),
    [Database.md](Database.md#documents-and-related-tables-milestone-2),
    [docs/modules/DocumentManagement.md](modules/DocumentManagement.md).
- **Milestone 2 — document search, filtering, and version comparison** (backend
  slice):
  - `GET /api/v1/documents` gained `?search=` (case-insensitive substring across
    `title`/`number`) and `?tag=` (exact tag name, joined through
    `document_tag_links`/`document_tags`), combinable with the existing
    `category_id`/`status`/`owner_id` filters, per
    [API.md](API.md#document-management-milestone-2-in-progress).
  - `GET /api/v1/documents/{id}/versions/{a}/compare/{b}` (any active user): a
    practical comparison — version-level metadata always, plus a `difflib`
    unified line diff when both versions are text-based (`text/plain`/`text/csv`)
    and within a size cap, or just a `checksum_changed` boolean otherwise. File
    reads go through the same server-side `resolve_path`/`storage_key` mechanism
    as download/preview.
  - **Independent security/tenant-isolation review** (a fresh agent with no prior
    session context) found no SQL-injection, path-traversal, or tenant-isolation
    defects, but flagged and this slice fixed three lower-severity issues before
    being committed:
    1. Unbounded in-memory text diffing (two ~50 MB text files held fully in
       memory per comparison request, from any active user). Fixed with a new
       5 MB `MAX_TEXT_DIFF_BYTES` cap — above it, or for non-text content types,
       the comparison falls back to checksum-only.
    2. An unhandled `FileNotFoundError` if a version's file was unexpectedly
       missing from storage. Fixed with a new `VersionFileMissingError`, mapped
       to a generic `500` with the real error logged server-side only.
    3. (Defense in depth, not currently exploitable) the tag-name join didn't
       itself scope `DocumentTag` by `organisation_id`, relying solely on the
       write-time invariant that a tag can only link to a document in its own
       organisation. Fixed by adding the redundant scoping predicate directly to
       the join.
    Also added a test-coverage gap the review identified: comparing two versions
    belonging to two different documents within the same organisation (not just a
    different organisation) correctly `404`s.
    Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-26-document-searchfiltering-and-version-comparison-a-text-diff-size-cap-and-defensive-tag-scoping).
  - 209 backend tests passing (up from 196): 10 new unit tests (search/tag
    filtering and their combination, text-diff generation, binary
    checksum-changed reporting, unchanged-content reporting, cross-org and
    cross-document `404`s, the size-cap fallback, the missing-file error) and 4
    new integration tests (combined search+tag filtering, a full text-diff
    round trip through the real HTTP API confirming `storage_key` is never
    exposed, cross-org `404` for compare).
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (82 source
    files), full `pytest` suite (209 tests: unit + integration against real
    PostgreSQL 16).
  - Docs updated in this slice: [API.md](API.md#document-management-milestone-2-in-progress),
    [Database.md](Database.md#documents-and-related-tables-milestone-2),
    [docs/modules/DocumentManagement.md](modules/DocumentManagement.md),
    [DecisionLog.md](DecisionLog.md#2026-07-26-document-searchfiltering-and-version-comparison-a-text-diff-size-cap-and-defensive-tag-scoping).
- **Milestone 2 — Document Management frontend**: adds the typed Document Management
  client and authenticated routes for the document register, category/tag
  administration, and document detail: search and all backend filters (including
  owner), complete category/tag/owner option loading without a fixed-result
  truncation, metadata editing, admin-confirmed soft delete/retirement, version
  upload/download/preview, workflow actions, acknowledgements, and version
  comparison. Async request-generation guards prevent older document-list/detail/
  acknowledgement/preview/comparison responses from overwriting newer state; preview
  MIME checks, sandboxed PDF frames, image rendering, and delayed object-URL
  revocation harden browser file handling. Category editing excludes descendants in
  the UI and the backend now rejects category-tree cycles even if a client bypasses
  that UX.
  - A follow-up independent-review pass on this same frontend slice found and fixed
    a further set of edge cases, all test-first: (1) a genuine TOCTOU race in the
    category-cycle check itself — two concurrent reciprocal reparentings (A's parent
    set to B, B's parent set to A) could each pass `_assert_no_category_cycle`
    before the other committed, together creating the very cycle neither update
    alone would have passed; fixed with a new `_lock_category_tree` per-organisation
    row lock (`backend/app/modules/documents/service.py`, mirroring the existing
    `_lock_document` pattern), regression-covered by a real-PostgreSQL concurrent-
    request integration test. (2) `DocumentDetailPage` and `VersionComparePanel` now
    fully reset every document-scoped piece of UI state (actions, errors, pending
    flags, the edit-details form, expanded acknowledgements, an open preview and its
    object URL, comparison selections/results) and invalidate in-flight requests
    whenever the route `:id` (or, for the panel, the `documentId` prop) changes —
    the component instance is reused across a navigation to a different document,
    so state and in-flight requests scoped to the previous one could otherwise leak
    into the next. (3) The categories/tags/owners option-loading effects in
    `DocumentsPage` and `DocumentDetailPage`, and `DocumentCategoriesPage`'s own
    `loadAll`, gained the same monotonic request-id guard already used elsewhere,
    making them robust to React StrictMode's simulated double-invoke on mount. (4)
    `DocumentsPage`'s post-create refresh no longer calls a `loadPage` closure
    captured at click time (which could carry stale filter values if the filters
    changed while the create request was in flight) — it instead bumps a
    `refreshVersion` counter so the effect re-runs with the render's current, live
    filters. Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-28-document-category-tree-toctou-race-and-frontend-async-state-edge-cases).
  - Frontend gates pass: `lint`, `format:check`, strict `typecheck`, 194 tests across
    19 files, production `build`.
  - Docs updated in this slice: this file, [TODO.md](TODO.md),
    [docs/modules/DocumentManagement.md](modules/DocumentManagement.md),
    [DecisionLog.md](DecisionLog.md#2026-07-28-document-category-tree-toctou-race-and-frontend-async-state-edge-cases).
- **Milestone 2 — final closeout verification** (2026-07-28, this batch): every
  outstanding item from
  [the plan's acceptance criteria](../.hermes/plans/2026-07-26-milestone-2-document-management.md#acceptance-criteria)
  verified against a clean checkout:
  - Full gate re-run: `ruff format --check`, `ruff check`, `mypy --strict` (82
    source files), full `pytest` (150 unit + 64 real-PostgreSQL integration tests,
    all passing — a disposable PostgreSQL 16 Docker container, not the shared dev
    database, so no `TEST_DATABASE_URL` was needed from the host); `npm run lint`,
    `format:check`, `typecheck`, `test` (194 tests across 19 files), `build`.
  - A real upgrade → downgrade → upgrade cycle for the complete six-revision
    migration chain, run against a disposable PostgreSQL 16 database, confirming
    every `downgrade()` is correct and the seed data/schema are both right after the
    final upgrade.
  - `pip-audit` and `npm audit` re-run: same findings as already documented under
    "Known bugs" below (same packages/versions, `starlette`/`pytest` on the backend
    and dev-tooling/`react-router` on the frontend) — no dependency change made or
    required.
  - A real, browser-driven `docker compose up --build` smoke test (headless
    Chromium via a temporary, uncommitted Playwright script outside the repository,
    matching the Milestone 1 closeout precedent — no committed dependency added):
    the bootstrap admin logged in, created a category and a tag, created a document
    using both, uploaded a version, submitted it for approval, approved it as admin,
    acknowledged it, viewed the "who acknowledged" list, previewed it inline,
    downloaded it (content verified byte-for-byte), uploaded a second version,
    compared the two versions (correctly reported as binary-content-changed), and
    retired the document — all with no browser console/page errors. `docker compose
    down` (no `-v`) then `up` (no `--build`) brought the stack back healthy with the
    bootstrap admin, the category, the tag, the document, both versions, the
    acknowledgement, and — read back through a fresh download in the browser — the
    uploaded file's own bytes on the `openqms_uploads` volume all still present and
    correct, proving real file persistence, not just database rows. Acknowledged as
    the admin account in this run rather than a separate member account; every
    member-vs-admin permission boundary is already independently covered by the
    backend unit/integration suites. Verified with the backend host port temporarily
    remapped to `18000` in a local, uncommitted override, for the same
    pre-existing host-port-8000-conflict reason recorded in the Milestone 0/1 Docker
    smoke test notes — the committed `docker-compose.yml` is unaffected.
  - No new defects found during this closeout pass — everything above passed on
    first execution.
  - Docs updated in this slice: this file, [TODO.md](TODO.md), and the
    [Milestone 2 plan](../.hermes/plans/2026-07-26-milestone-2-document-management.md)'s
    acceptance-criteria checkboxes and status line.

**Milestone 2 (Document Management) is complete.**

- **Milestone 3 — Suppliers backend** (schema, certifications, performance records):
  - Suppliers module (`backend/app/modules/suppliers/`): `suppliers`,
    `supplier_certifications`, `supplier_performance_records` tables
    (`backend/alembic/versions/d47b9e2c1a05_add_suppliers_certifications_and_.py`),
    router mounted at `/api/v1/suppliers`, per
    [API.md](API.md#suppliers-module-milestone-3) and
    [docs/modules/Suppliers.md](modules/Suppliers.md). Every operation requires only
    authentication (any active user), scoped to the caller's own organisation, per
    the Milestone 3 plan's design decision 2 (Suppliers is collaborative reference
    data, not admin-gated like Document Management's categories/tags).
  - `company_id` (on suppliers) and `certificate_document_id` (on certifications) are
    validated against the People and Document Management modules' own service
    layers respectively — never their models directly, per the module-isolation
    rule — and `404` (never a cross-organisation leak) if not in the caller's
    organisation. A new `list_company_ids_matching_name` helper was added to
    `backend/app/modules/people/service.py` for this (Suppliers' company-name
    `search` filter needs it without importing the `Company` model directly).
  - `GET /api/v1/suppliers/certifications/expiring?within_days=` reads a new
    `supplier_certification_reminder_window_days` `configuration` row (seeded by
    the migration, default 30 days), per design decision 5 — read-only; no
    notification is actually sent (no notification infrastructure exists yet).
  - Migration verified with a real upgrade → downgrade → upgrade cycle against a
    disposable local PostgreSQL 16 database, in addition to the integration suite
    running `alembic upgrade head` itself.
  - 236 backend tests passing (up from 209 at Milestone 2 closeout): 13 new unit
    tests (organisation scoping, cross-module `company_id`/`certificate_document_id`
    validation, the certification-expiry window calculation with both the
    configured-default and explicit-`within_days` cases) and 8 new integration
    tests against real PostgreSQL (full CRUD round trip, cross-organisation `404`s
    for suppliers/certifications/performance, the expiring-certifications endpoint
    scoped correctly per organisation, append-only performance-record ordering,
    the authentication requirement). All written test-first (RED confirmed against
    the already-drafted-but-uncommitted service/schema/model code from an
    interrupted prior session, then GREEN against the new router/migration/tests
    added this batch).
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (91 source
    files), full `pytest` suite (236 tests: unit + integration against real
    PostgreSQL 16).
  - Docs updated in this slice: [API.md](API.md#suppliers-module-milestone-3),
    [Database.md](Database.md#suppliers-and-related-tables-milestone-3),
    [docs/modules/Suppliers.md](modules/Suppliers.md) (`Status: Implemented
    (backend)`).
- **Milestone 3 — Products backend** (categories, products, document/supplier links):
  - Products module (`backend/app/modules/products/`): `product_categories`,
    `products`, `product_documents`, `product_supplier_links` tables
    (`backend/alembic/versions/a6c2d94f7e13_add_product_categories_products_and_.py`),
    router mounted at `/api/v1/product-categories` and `/api/v1/products`, per
    [API.md](API.md#products-module-milestone-3) and
    [docs/modules/Products.md](modules/Products.md). Built after Suppliers within
    this same milestone (per the plan's design decision 1), since
    `product_supplier_links` references `suppliers.id`. Every operation requires
    only authentication (any active user), matching Suppliers/People's precedent,
    per design decision 2.
  - `part_number` is unique per organisation, enforced at the service layer with a
    clean `409` (`_assert_part_number_available` in
    `backend/app/modules/products/service.py`), matching `document_tags.name`'s
    existing precedent, backed by a DB-level `UniqueConstraint` as defence in depth.
    Product category deletion is guarded (`409`) while any product still references
    it, matching `document_categories`' existing guard.
  - `category_id` is validated within the Products module itself;
    `document_id` (on product-document links) and `supplier_id` (on
    product-supplier links) are validated against the Document Management and
    Suppliers modules' own service layers respectively — never their models
    directly, per the module-isolation rule — and `404` (never a cross-organisation
    leak) if not in the caller's organisation. Duplicate links (`(product_id,
    document_id, relationship_type)` or `(product_id, supplier_id)`) are rejected
    with a clean `409`, not a raw `IntegrityError`.
  - Migration verified with a real upgrade → downgrade → upgrade cycle against a
    disposable local PostgreSQL 16 database — both individually (one revision at a
    time) and together (both new Milestone 3 revisions in one downgrade/upgrade
    pass) — in addition to the integration suite running `alembic upgrade head`
    itself.
  - 268 backend tests passing (up from 236 after the Suppliers backend slice): 32
    new unit tests (organisation scoping, the `part_number` conflict `409` including
    the same-part-number-different-organisation non-conflict case, the category
    in-use `409`, cross-module `document_id`/`supplier_id` validation, duplicate-link
    rejection, a document linked under two different relationship types) and 12 new
    integration tests against real PostgreSQL (full CRUD round trips for categories/
    products/both link types, cross-organisation `404`s, the `part_number` `409`
    through the real HTTP API, the category delete guard, the authentication
    requirement). All written test-first (RED confirmed against the already-planned
    but not-yet-written router/migration/tests, then GREEN).
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (99 source
    files), full `pytest` suite (268 tests: unit + integration against real
    PostgreSQL 16).
  - Docs updated in this slice: [API.md](API.md#products-module-milestone-3),
    [Database.md](Database.md#products-and-related-tables-milestone-3),
    [docs/modules/Products.md](modules/Products.md) (`Status: Implemented
    (backend)`).
- **Milestone 3 — Suppliers frontend**: `frontend/src/modules/suppliers/`: typed
  `api.ts`/`types.ts` client matching `docs/API.md#suppliers-module-milestone-3`,
  `SuppliersPage.tsx` (search, approval-status/risk-rating/preferred filters, and a
  create form that selects an existing company — with a "Create a company first"
  link to `/companies` when none exist yet, matching Document Management's
  link-out-to-category-admin precedent), and `SupplierDetailPage.tsx` (metadata edit,
  certifications add/edit/delete with an expiry-highlighted row state, and an
  append-only performance-record list with an add form). Mounted at `/suppliers` and
  `/suppliers/:id` in `frontend/src/app/App.tsx`, with a new "Suppliers" nav link in
  `frontend/src/app/Layout.tsx` visible to every authenticated user (no admin gate,
  matching the backend's design decision 2). A new
  `.supplier-certification--expiring` style
  (`frontend/src/shared/theme/theme.css`) highlights a certification row within 30
  days of (or past) its `expiry_date` with a border, not colour alone — the row also
  carries an explicit "(expiring soon)" text label for the same reason.
  - 25 new frontend tests (219 total, up from 194 at Milestone 2 closeout — no
    frontend changes were made during the Suppliers/Products backend-only slices
    above), across 3 new test files, written test-first. Coverage includes:
    list/search/filter, the empty-companies "create a company first" prompt, create,
    pagination, `<StrictMode>` mount-safety regressions for both pages, metadata
    edit, certification add/edit/delete, the expiry-highlight rendering, and
    append-only performance-record creation.
  - Gates pass: `npm run lint`, `format:check` (Prettier), `typecheck` (strict),
    `test` (219 tests across 22 files), `build`.
  - Docs updated in this slice: this file, [TODO.md](TODO.md),
    [docs/modules/Suppliers.md](modules/Suppliers.md) (`Status: Implemented`).
- **Milestone 3 — Products frontend**: `frontend/src/modules/products/`: typed
  `api.ts`/`types.ts` client matching `docs/API.md#products-module-milestone-3`,
  `ProductsPage.tsx` (search, category/type filters, create form, with a link to
  category administration), `ProductCategoriesPage.tsx` (flat create/list/edit/
  delete, mirroring `CompaniesPage`'s simple-CRUD shape rather than Document
  Management's tree pattern, since product categories are flat per the schema), and
  `ProductDetailPage.tsx` (metadata edit; linked-document management — search
  Document Management records by title/number, then attach with a relationship
  type, or unlink; linked-supplier management — attach an existing supplier with an
  `is_preferred` flag, or unlink). Mounted at `/products`, `/products/categories`,
  and `/products/:id`, with a new "Products" nav link visible to every
  authenticated user (no admin gate, matching the backend's design decision 2).
  - 28 new frontend tests (247 total, up from 219 after the Suppliers frontend
    slice), across 4 new test files, written test-first. Coverage includes:
    category admin create/edit/delete (including the in-use `409` shown inline),
    product list/search/filter/create/pagination, the category-administration
    link, `<StrictMode>` mount-safety regressions for all three pages, metadata
    edit, document search-then-link and unlink, and supplier link/unlink.
  - Gates pass: `npm run lint`, `format:check` (Prettier), `typecheck` (strict),
    `test` (247 tests across 26 files), `build`.
  - Docs updated in this slice: this file, [TODO.md](TODO.md),
    [docs/modules/Products.md](modules/Products.md) (`Status: Implemented`).
- **Milestone 3 — final closeout verification** (2026-07-29, this batch): every
  outstanding item from
  [the plan's acceptance criteria](../.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md#acceptance-criteria)
  verified against the live repository, not just re-asserted from a prior session's
  uncommitted draft notes:
  - Full gate re-run: `ruff format --check`, `ruff check`, `mypy --strict` (99 source
    files), full `pytest` (274 tests: unit + integration against real PostgreSQL 16,
    the pre-existing `openqms-dev-postgres` dev database — up from 268 at the end of
    the Products backend slice, +6 from the TOCTOU fix below); `npm run lint`,
    `format:check`, `typecheck` (strict), `test` (247 tests across 26 files), `build`.
  - A real upgrade → downgrade → upgrade cycle for the complete eight-revision
    migration chain (Milestones 0–3), run against a disposable PostgreSQL 16
    container created and torn down for this check alone, confirming every
    `downgrade()` is correct and the seed configuration rows (including the
    Milestone 3 `supplier_certification_reminder_window_days`) are present and
    correct after the final upgrade.
  - `pip-audit` and `npm audit` re-run and independently confirmed (not merely
    copied from a prior draft): `pip-audit` reports the same `starlette==0.46.2`/
    `pytest==8.3.5` advisories (10 findings total, unchanged); `npm audit` reports
    the same 14 findings (3 moderate, 10 high, 1 critical), same packages/versions.
    No new dependency was added by Milestone 3, so both re-runs are re-confirmations
    of the pre-existing, already-documented deferrals below, not new findings.
  - **Independent security/tenant-isolation review** (a fresh agent with no prior
    session context, reading the actual Suppliers/Products code and tests) found no
    cross-organisation leaks, no client-controlled `organisation_id`, and no
    path-traversal issues, but did find one real concurrency defect, fixed test-first
    in this batch: three check-then-insert sequences in
    `app/modules/products/service.py` (`part_number` uniqueness in
    `create_product`/`update_product`, and the duplicate-link checks in
    `create_product_document_link`/`create_product_supplier_link`) had no row lock
    and no `IntegrityError` handling, so a losing concurrent request would surface a
    raw `500` instead of the documented `409` — the same TOCTOU class already fixed
    for Document Management's version numbering, acknowledgement idempotency, and
    category-tree cycle check, reintroduced here in three new places. Fixed by
    catching `IntegrityError` around each commit and mapping it to the same domain
    conflict exception the normal check-path already raises. Two lower-severity,
    pre-existing observations were verified and recorded but not changed:
    `delete_category`'s unlocked count-then-delete shape (shared with Document
    Management, and not a data-integrity risk since the FK rejects the delete rather
    than silently corrupting data) and `list_company_ids_matching_name`'s missing
    pagination limit (bounded by the caller's own organisation size). Full reasoning
    in [DecisionLog.md](DecisionLog.md#2026-07-29-milestone-3-closeout-products-check-then-insert-races-mapped-to-clean-conflicts).
  - 6 new backend tests from the fix above (274 total): three real-concurrency
    `asyncio.gather` integration tests (kept as documentation of intended behaviour,
    but — consistent with the same scheduler-dependency caveat already recorded for
    the Document Management category-tree TOCTOU regression test — not a reliable
    deterministic reproduction of the race) and three deterministic unit tests that
    monkeypatch the relevant availability check to a no-op, forcing the code down
    the `IntegrityError`-handling path directly.
  - A real, browser-driven `docker compose up --build` smoke test (headless
    Chromium via a temporary, uncommitted Playwright script outside the repository,
    matching the Milestone 0/1/2 closeout precedent — no committed dependency
    added): the bootstrap admin logged in, created a company and a supplier linked
    to it, added a certification and a performance record to the supplier, created a
    product category, created a product in that category, created a document and
    linked it to the product (then unlinked it), linked the supplier to the
    product, edited the product's metadata, and deleted the certification — all
    with no browser console/page errors. `docker compose down` (no `-v`) then `up`
    (no `--build`) brought the stack back healthy with the supplier, its
    (now-empty) certification list, its performance record, the product category,
    the product with its edited description and linked supplier, and the unlinked
    document correctly still absent — all verified through the browser again after
    the restart, not just the database directly. Verified with the backend and
    frontend host ports temporarily remapped to `18000`/`15173` via a local,
    uncommitted `docker-compose.override.yml` (using the Compose `!override` merge
    tag, since plain list-merge would otherwise concatenate rather than replace the
    `ports` key), for the same pre-existing host-port-8000-conflict reason recorded
    in every prior milestone's Docker smoke test notes — the committed
    `docker-compose.yml` is unaffected, and the override file was deleted after the
    test rather than committed.
  - Docs updated in this slice: this file, [TODO.md](TODO.md),
    [DecisionLog.md](DecisionLog.md#2026-07-29-milestone-3-closeout-products-check-then-insert-races-mapped-to-clean-conflicts),
    and the [Milestone 3 plan](../.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md)'s
    acceptance-criteria checkboxes and status line.

**Milestone 3 (Products and Suppliers) is complete.**

- **Milestone 4 — NCR schema, numbering, CRUD, and the transition workflow**
  (backend slice): NCR module (`backend/app/modules/ncr/`): `ncrs`,
  `ncr_status_history` tables
  (`backend/alembic/versions/12394296d0cf_add_ncrs_and_ncr_status_history.py`),
  router mounted at `/api/v1/ncr`, per [API.md](API.md#ncr-module-milestone-4-in-progress)
  and [docs/modules/NCR.md](modules/NCR.md). Every operation requires only
  authentication (any active user) except deletion, which is admin-only soft
  delete, per the plan's design decision 2.
  - `product_id`/`supplier_id`/`raised_by_id` are validated against the Products,
    Suppliers, and People modules' own service layers respectively — never their
    models directly, per the module-isolation rule — and `404` (never a
    cross-organisation leak) if not in the caller's organisation. The
    `type`/`supplier_id` invariant (supplier NCRs must have a `supplier_id`,
    internal NCRs must not) is enforced at the Pydantic schema layer, mirroring
    the People module's `is_employee`/`company_id` precedent.
  - `number` is server-generated from a new `ncr_numbering_scheme` configuration
    row holding two independent prefix/sequence pairs (`NCR-0001`, `NCR-0002`, ...
    for internal; `SNCR-0001`, ... for supplier), per design decision 6.
  - The workflow (`open` → `investigate` → `containment` → `corrective_action` →
    `verification` → `closed`) only allows moving to exactly the next status —
    no skipping stages, no moving backward, no transitioning once closed — enforced
    in a locked transaction (`_lock_ncr`, mirroring
    `documents.service._lock_document`) that also writes an immutable
    `ncr_status_history` row. The close-blocked-while-actions-open guard from the
    module doc is deferred to the `ncr_actions` slice, since that table doesn't
    exist yet.
  - Migration verified with a real upgrade → downgrade → upgrade cycle against a
    disposable local PostgreSQL 16 database, in addition to the integration suite
    running `alembic upgrade head` itself.
  - **Independent security/tenant-isolation review** (a fresh agent with no prior
    session context) found no cross-organisation leaks, client-controlled
    `organisation_id`, or module-isolation violations, but found and this slice
    fixed test-first two issues before being committed:
    1. `_lock_ncr`'s row lock was acquired *after* `get_ncr`'s
       `deleted_at.is_(None)` filter had already run, so a concurrent admin delete
       committing in that window could leave a transition (or metadata update)
       proceeding against — and adding status-history rows to — an NCR that is now
       soft-deleted. Fixed by having `delete_ncr` acquire the same lock, and having
       `transition_ncr`/`update_ncr` re-check `deleted_at` immediately after
       locking.
    2. `ncrs.number` had no DB-level uniqueness backstop, unlike every other
       server-generated-number table in this codebase (`documents.number` →
       `uq_documents_org_number`). No exploitable duplicate was found — the
       numbering lock is held for the whole creation transaction — but the
       missing defence-in-depth constraint was added
       (`uq_ncrs_org_number`), edited into the still-uncommitted migration rather
       than added as a second one.
    Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-29-ncr-schemacrudworkflow-slice-a-soft-deletetransition-race-and-a-missing-number-uniqueness-backstop).
  - 33 new backend tests (307 total, up from 274 at Milestone 3 closeout): 19 unit
    tests (numbering per-type sequencing, the invariant, cross-module validation,
    the full transition sequence and its rejections, soft delete, the two
    deterministic soft-delete-race regression tests, and the DB-level
    number-uniqueness test) and 14 integration tests against real PostgreSQL (full
    CRUD round trip, the `422` invariant, cross-organisation `404`s, the full
    transition sequence through the real HTTP API, admin-only delete (`403` for a
    member), and two real-concurrency race tests kept as documentation of intended
    behaviour, not a guaranteed deterministic reproduction — same
    scheduler-dependency caveat already recorded for this style of test in
    [DecisionLog.md](DecisionLog.md#2026-07-28-document-category-tree-toctou-race-and-frontend-async-state-edge-cases)).
    All written test-first.
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (108 source
    files), full `pytest` suite (307 tests: unit + integration against real
    PostgreSQL 16).
  - Docs updated in this slice: [API.md](API.md#ncr-module-milestone-4-in-progress),
    [Database.md](Database.md#ncr-and-related-tables-milestone-4-in-progress),
    [docs/modules/NCR.md](modules/NCR.md) (`Status: Implemented
    (schema/CRUD/workflow only)`),
    [DecisionLog.md](DecisionLog.md#2026-07-29-ncr-schemacrudworkflow-slice-a-soft-deletetransition-race-and-a-missing-number-uniqueness-backstop).
- **Milestone 4 — NCR actions** (backend slice, 2026-07-30): `ncr_actions` table
  (`backend/alembic/versions/d1b578c4df71_add_ncr_actions.py`), containment/
  corrective/preventive actions with an optional `owner_id` (validated against
  People, never queried directly) and `due_date`, managed via
  `POST/GET /api/v1/ncr/{id}/actions` and `PATCH /api/v1/ncr/actions/{id}` (full
  update, not nested under a specific NCR id, matching the plan's shape but still
  scoped to the caller's organisation via a join through `ncrs`). The
  close-blocked-while-actions-open guard (design decision 4) is now enforced in
  `transition_ncr`: transitioning to `closed` is rejected (`409`) while any of the
  NCR's actions are still `open`.
  - Migration verified with a real upgrade → downgrade → upgrade cycle against a
    disposable local PostgreSQL 16 database.
  - **Independent security/tenant-isolation review** (a fresh agent with no prior
    session context) found no cross-organisation leaks, owner validation gaps, or
    reassignment bypasses, but found a real concurrency defect, fixed test-first
    before being committed: `create_action`/`update_action` never took the same
    per-NCR row lock (`_lock_ncr`) `transition_ncr`'s close guard already locks
    before counting open actions, so nothing serialised an action mutation against
    a concurrent close — a completed action could be reopened at the same moment
    an NCR closed with zero open actions counted, leaving the NCR `closed` with an
    action simultaneously `open`. Fixed by having both functions take the same
    lock. Validating that fix surfaced a second-order gap: once correctly
    serialised, whichever request loses the race sees the winner's already-
    committed result — for a reopen losing to a close, that meant reopening an
    action on an already-`closed` NCR, which nothing was stopping (not a race at
    that point, just a missing rule). Fixed with a new `NcrActionsFrozenError`
    (`409`): a closed NCR's actions can no longer be added to or edited at all,
    extending design decision 4's spirit. Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-30-ncr-actions-slice-a-close-guard-lock-gap-and-a-new-frozen-actions-rule).
  - 19 new backend tests (326 total, up from 307): 14 unit tests (defaults,
    cross-org/owner validation, two lock-spy regression tests proving
    `create_action`/`update_action` actually acquire `_lock_ncr`, the
    close-blocked-while-open guard and its "ignores other NCRs' actions" edge
    case, and two frozen-actions regression tests) and 5 integration tests against
    real PostgreSQL (the full action lifecycle through the real HTTP API,
    cross-org `404`s, the closing-blocked-then-unblocked flow, and a
    real-concurrency reopen-vs-close race kept as documentation of intended
    behaviour — same scheduler-dependency caveat as every other test in this
    style, but re-run repeatedly and confirmed non-flaky after the frozen-actions
    fix). All written test-first. This slice also fixed a cross-file test-hygiene
    gap it exposed: `test_people.py`, `test_products.py`, and `test_suppliers.py`
    now also delete leftover `ncrs` rows for the shared default organisation
    before deleting the People/Products/Suppliers rows those NCRs reference,
    since `ncrs` now carries foreign keys into all three and a leftover NCR row
    was blocking those other test files' own cleanup.
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (109 source
    files), full `pytest` suite (326 tests: unit + integration against real
    PostgreSQL 16), re-run twice end-to-end with no flakiness.
  - Docs updated in this slice: [API.md](API.md#ncr-module-milestone-4-in-progress),
    [Database.md](Database.md#ncr-and-related-tables-milestone-4-in-progress),
    [docs/modules/NCR.md](modules/NCR.md) (`Status: Implemented
    (schema/CRUD/workflow/actions only)`),
    [DecisionLog.md](DecisionLog.md#2026-07-30-ncr-actions-slice-a-close-guard-lock-gap-and-a-new-frozen-actions-rule).
- **Milestone 4 — NCR investigation tools** (backend slice, 2026-07-30):
  `ncr_investigation_tools` table
  (`backend/alembic/versions/2df37403d75c_add_ncr_investigation_tools.py`), one
  evolving JSONB worksheet per `(ncr_id, tool_type)` for the four structured aids
  (`five_why`/`fishbone`/`eight_d`/`ten_d`), managed via
  `GET/PUT /api/v1/ncr/{id}/tools/{tool_type}` (design decision 7). `PUT`
  creates-or-replaces rather than requiring a separate create/update
  distinction, using the same idempotent-write pattern as
  `documents.service.acknowledge_document_version`. `GET` for a tool that has
  never been saved returns a default empty payload (`data: {}`, `id: null`)
  rather than `404` — "not started" is a normal state for an optional aid;
  only a nonexistent/cross-org NCR itself `404`s, and an invalid `tool_type`
  is rejected with `422` by FastAPI's own enum path-parameter validation.
  - Migration verified with a real upgrade → downgrade → upgrade cycle against a
    disposable local PostgreSQL 16 database.
  - **Independent security/tenant-isolation review** (a fresh agent with no
    prior session context) found no cross-organisation leaks, `organisation_id`
    provenance issues, or TOCTOU races in the upsert's create-or-replace logic,
    but found one real gap, fixed test-first before being committed: this slice
    had no equivalent to the `ncr_actions` slice's frozen-once-closed rule, so a
    closed NCR's investigation worksheet could still be silently rewritten
    after closure. Fixed with a new `NcrInvestigationToolFrozenError` (`409`),
    exactly mirroring `NcrActionsFrozenError`, raised only by the `PUT`
    (upsert) path — reads stay unfrozen, since a closed NCR's worksheets must
    remain readable (needed by the future PDF export slice). A second,
    informational-only observation — the `data` JSONB column has no dedicated
    size cap beyond the global request-body-size middleware — was verified as
    matching `configuration.value`'s existing precedent, not a new gap, and left
    unchanged. Full reasoning in
    [DecisionLog.md](DecisionLog.md#2026-07-30-ncr-investigation-tools-slice-extending-the-frozen-once-closed-rule).
  - 13 new backend tests (339 total, up from 326 after the actions slice): 7
    unit tests (not-started returns `None`, cross-org `404`,
    create-then-replace, tool-type independence, cross-org upsert `404`, the
    frozen-rewrite-rejected regression test, and the still-readable-when-closed
    regression test) and 6 integration tests against real PostgreSQL (the
    default-payload response, cross-org `404`, the `422` invalid-`tool_type`
    case, create-then-replace through the real HTTP API including verifying a
    different `tool_type` on the same NCR stays independent, cross-org upsert
    `404`, and the closed-NCR rewrite-rejected-but-still-readable flow). All
    written test-first.
  - Gates pass: `ruff format --check`, `ruff check`, `mypy --strict` (110 source
    files), full `pytest` suite (339 tests: unit + integration against real
    PostgreSQL 16). Note: the full combined unit+integration suite showed
    intermittent, non-reproducible `test_documents.py` failures under this
    session's Windows/asyncpg environment when run immediately back-to-back
    several times in a row — confirmed, by repeated isolated re-runs, to be
    pre-existing test-infrastructure flakiness (connection/engine teardown
    timing under load across 113 integration tests each creating and disposing
    their own engine) unrelated to this slice's code: `pytest tests/integration`
    run alone passed 113/113 cleanly on two separate occasions, and the full
    suite subsequently passed 339/339 cleanly on retry with no code changes.
    Recorded here rather than silently ignored; see "Known bugs" below.
  - Docs updated in this slice: [API.md](API.md#ncr-module-milestone-4-in-progress),
    [Database.md](Database.md#ncr-and-related-tables-milestone-4-in-progress),
    [docs/modules/NCR.md](modules/NCR.md) (`Status: Implemented
    (schema/CRUD/workflow/actions/investigation tools only)`),
    [DecisionLog.md](DecisionLog.md#2026-07-30-ncr-investigation-tools-slice-extending-the-frozen-once-closed-rule).
- **Milestone 4 — NCR attachments and supplier NCR history** (backend slice,
  2026-07-30): `ncr_attachments` table
  (`backend/alembic/versions/5fe9edf6d2c5_add_ncr_attachments.py`), letting a
  Document Management record be attached to an NCR as supporting evidence, via
  `GET/POST /api/v1/ncr/{id}/attachments` and
  `DELETE /api/v1/ncr/{id}/attachments/{attachment_id}`; and a read-only
  `GET /api/v1/suppliers/{id}/ncr-history` endpoint listing the NCRs linked to
  a supplier.
  - `document_id` is validated via `documents.service.get_document` (never a
    direct query against `documents.models.Document`), enforcing both
    existence and same-organisation ownership, per the module-isolation rule.
    The Suppliers `ncr-history` endpoint reuses `ncr.service.list_ncrs` the
    same way, rather than querying `Ncr` directly.
  - `create_attachment`/`delete_attachment` take the same `_lock_ncr` row lock
    and closed-NCR `409` guard as actions/investigation tools
    (`NcrAttachmentsFrozenError`), applied proactively in this slice from the
    start rather than found reactively by a review, unlike the prior two
    slices. Duplicate `(ncr_id, document_id)` attachments are rejected `409`,
    including under concurrent requests via an `IntegrityError` fallback
    matching `documents.service.acknowledge_document_version`'s pattern.
  - Migration verified with a real upgrade → downgrade → upgrade cycle against
    a disposable local PostgreSQL 16 database.
  - **Independent security/tenant-isolation review** (a fresh agent with no
    prior session context) found no issues: tenant isolation, module
    isolation, the frozen-once-closed rule, concurrency locking, duplicate
    handling, `document_id` validation, auth on every new endpoint, and
    bounded `limit`/`offset` on both new list endpoints were all confirmed
    correctly implemented and covered by tests, with no gaps identified.
  - 15 new backend tests (354 total, up from 339 after the investigation-tools
    slice): unit tests (`test_ncr_service.py`) covering the attachment
    lifecycle, cross-org NCR/document rejection, duplicate rejection, and the
    closed-NCR frozen rule for both create and delete; integration tests
    (`test_ncr.py`) covering the same guarantees against real PostgreSQL
    through the HTTP API, plus the two supplier-history tests (scoped listing,
    cross-org `404`).
  - While verifying this slice, found and fixed a cross-file integration-test
    cleanup fragility (not a production-code bug): the shared, persistent dev
    Postgres database's `context` fixtures in each `tests/integration/test_*.py`
    file reset only that file's own module's rows for the default organisation
    at fixture setup, relying on later-alphabetical files' setup to clean up
    earlier files' cross-referencing leftovers. Adding `ncrs`/`ncr_attachments`
    FKs into `people`/`products`/`suppliers`/`documents` broke this chain
    repeatedly as new cross-module references were added. Fixed by making
    `test_ncr.py`'s own fixture fully self-contained (cleans up every
    cross-module table its own tests create, including `Document`, in both its
    setup and its `org_b` teardown, rather than relying on other files) and by
    adding the missing `Document` cleanup to `test_documents.py`'s fixture, so
    `ncr_attachments.document_id` (which has no `ON DELETE`) never blocks a
    later file's cleanup. Full backend gates re-verified clean after the fix:
    `ruff format --check`, `ruff check`, `mypy --strict`, 236 unit tests, and
    118 integration tests against real PostgreSQL, all passing with 0
    errors/failures on a full-suite run (previously intermittent
    `test_documents.py` flakiness under full-suite load, documented in "Known
    bugs" below, was also observed once during this verification and
    reproduced as pre-existing, not caused by this slice — confirmed by an
    immediately-following clean full-suite re-run).
  - Docs updated in this slice: [API.md](API.md#ncr-module-milestone-4-in-progress),
    [Database.md](Database.md#ncr-and-related-tables-milestone-4-in-progress),
    [docs/modules/NCR.md](modules/NCR.md) (`Status: Implemented
    (schema/CRUD/workflow/actions/investigation
    tools/attachments/supplier history only)`).

## Work in progress

Milestone 4 (NCR): the `ncrs`/`ncr_status_history`/`ncr_actions`/
`ncr_investigation_tools`/`ncr_attachments` schema, CRUD, transition workflow,
actions, investigation tools, attachments, and the Suppliers `ncr-history`
endpoint are implemented and tested (see above). Not yet done: PDF export and
the frontend. Plan:
[.hermes/plans/2026-07-29-milestone-4-ncr.md](../.hermes/plans/2026-07-29-milestone-4-ncr.md).

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
Re-verified at Milestone 3 closeout (2026-07-29): same 14 findings (3 moderate, 10
high, 1 critical), same packages/versions; Milestone 3 added no new frontend
dependency.

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
FastAPI/pytest version bump. Re-verified at Milestone 2 closeout (2026-07-28): same
`fastapi==0.115.14`/`starlette==0.46.2`/`pytest==8.3.5` versions, more CVE IDs now
recorded against the same unchanged `starlette` version (`pip-audit` lists 7 distinct
advisories against it rather than fewer previously), but the underlying constraint —
`fastapi==0.115.14` pins `starlette<0.47.0`, and every fix version is `>=0.47.0` — is
unchanged, so this remains the same accepted, unproven-jump-out-of-scope deferral, not
a new or worsened finding. Re-verified at Milestone 3 closeout (2026-07-29): same
`fastapi==0.115.14`/`starlette==0.46.2`/`pytest==8.3.5` versions (`pip-audit` now
lists 10 CVE IDs across both packages combined rather than 7, all against the same
unchanged versions); Milestone 3 added no new backend dependency.

## Next recommended tasks

Implement Milestone 4 per the committed plan, starting with the `ncrs`/
`ncr_status_history` schema, numbering, CRUD, and the transition workflow (the
plan's suggested commit 2), then actions, investigation tools, attachments and
supplier NCR history, PDF export, frontend, then closeout — test-first, in small
independently-committable vertical slices, following the same pattern used for
Milestones 1–3.

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

None. The previous session-local Node execution restriction no longer applies;
Node/npm and every documented frontend gate ran successfully on 2026-07-28.
The stack was chosen per the product specification's own
preference (FastAPI + SQLAlchemy 2/Alembic + PostgreSQL, React/TypeScript/Vite)
with reasoning recorded in [DecisionLog.md](DecisionLog.md).

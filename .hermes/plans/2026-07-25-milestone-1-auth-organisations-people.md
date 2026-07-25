# Milestone 1 — Authentication, Organisations, People

**Status:** Planned; implementation starting this batch.
**Date planned:** 2026-07-25

## Purpose

Turn the Milestone 0 platform foundation into a system real users can log into and
use, per [Roadmap.md](../../docs/Roadmap.md#m1-authentication-organisations-people)
and TODO Tasks 11–13 in [docs/TODO.md](../../docs/TODO.md). Three vertical slices,
built in dependency order:

1. JWT authentication (user accounts, Argon2id password hashing, login/logout,
   `Depends()`-based current-user resolution, organisation scoping, a safe bootstrap
   admin mechanism).
2. Organisation-scoped user management (admin-only create/list/deactivate, roles).
3. The People module (employees, customers, suppliers, multiple contacts per
   customer/supplier), per [docs/modules/People.md](../../docs/modules/People.md).

Background reading: [Architecture.md](../../docs/Architecture.md),
[Database.md](../../docs/Database.md), [API.md](../../docs/API.md),
[CodingStandards.md](../../docs/CodingStandards.md),
[Contributing.md](../../docs/Contributing.md),
[docs/modules/People.md](../../docs/modules/People.md).

## In scope

### 1. Authentication

- **`users` table** (organisation-scoped): `id` (UUID PK), `organisation_id` (FK,
  not null), `email` (text, not null), `hashed_password` (text, not null),
  `full_name` (text, not null), `role` (PostgreSQL ENUM `admin` / `member` — fixed by
  domain per [Database.md](../../docs/Database.md#naming-conventions), not a
  `configuration` row), `is_active` (bool, default `true`), `token_version` (int,
  default `0` — see revocation strategy below), `created_at`/`updated_at`. Unique
  constraint on (`organisation_id`, `email`) — the schema already supports a user
  belonging to more than one organisation in a future hosted mode without rework, but
  Milestone 1 keeps one user row per organisation, matching
  [API.md](../../docs/API.md#authentication)'s "one organisation per token" design.
- **Password hashing:** Argon2id via `argon2-cffi` directly (not `passlib`, which is
  unmaintained and has had compatibility breaks with newer `argon2-cffi` releases —
  recorded as a new DecisionLog entry). Passwords are never logged or returned in any
  response.
- **JWT access tokens** via `PyJWT`, HS256, signed with `JWT_SECRET_KEY` (new required
  env var, no default — the app must fail to start without one, so a real secret is
  always required). Claims: `sub` (user id), `org` (organisation id), `role`, `ver`
  (the user's `token_version` at issue time), `exp`, `iat`. Default expiry 60 minutes,
  configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Logout / revocation strategy:** no refresh tokens and no server-side token
  blocklist table in Milestone 1 (both are unnecessary complexity for a short-lived
  access-token-only design). Instead, `POST /api/v1/auth/logout` increments the
  calling user's `token_version`, which immediately invalidates every previously
  issued token for that user (the current one and any others) because
  `get_current_user` rejects any token whose `ver` claim doesn't match the user's
  current `token_version`. This is coarse (all-sessions logout, not per-device) but
  simple, correct, and requires no additional infrastructure. Recorded as a
  DecisionLog entry with the trade-off explicit.
- **`Depends()`-based current-user resolution**: `get_current_user` (decodes the
  Bearer token, loads the user by `sub` + `org`, checks `is_active` and `ver` match,
  raises `401` otherwise) and `get_current_admin` (wraps `get_current_user`, raises
  `403` if `role != admin`). Both live in `app/core/security_deps.py` (or similar) so
  every later module can depend on them.
- **Organisation scoping**: every authenticated request carries exactly one
  organisation (from the token, never from client-supplied input); every service
  method that touches a tenant-scoped table takes `organisation_id` from the resolved
  current user, not from a request parameter.
- **Bootstrap admin, no committed secrets**: `app/core/bootstrap.py` runs once at
  backend startup (called from the FastAPI app's startup path, after migrations have
  applied). If the seeded organisation has zero users: create one admin using
  `BOOTSTRAP_ADMIN_EMAIL` (new env var, required for the bootstrap to run — if unset,
  bootstrap is skipped and a warning is logged) and `BOOTSTRAP_ADMIN_PASSWORD` (new
  env var; if unset, a cryptographically random 24-character password is generated
  with `secrets.token_urlsafe` and logged **once**, at `WARNING` level, with explicit
  instructions to log in and rotate it — never written to any file, never stored
  anywhere but the hashed column). If any user already exists, bootstrap is a no-op
  (idempotent across restarts). `.env.example` documents both variables with empty/
  placeholder values, never a real credential.
- **Endpoints** (`/api/v1/auth`, new reserved prefix already listed in
  [API.md](../../docs/API.md#module-endpoint-prefixes-reserved-not-yet-implemented)):
  - `POST /api/v1/auth/login` — body `{email, password}` → `200 {access_token,
    token_type: "bearer", user: {id, email, full_name, role, organisation_id}}`, or
    `401` for wrong credentials or inactive user (identical error message/shape for
    both, so login failure never reveals whether an account exists or is merely
    disabled).
  - `POST /api/v1/auth/logout` — requires auth; increments `token_version`; `204`.
  - `GET /api/v1/auth/me` — requires auth; returns the current user's profile.

### 2. User management

- New module `app/modules/users/` — router mounted at `/api/v1/users`, **admin-only**
  for every operation (list included — account administration is not a member-level
  capability in Milestone 1).
  - `POST /api/v1/users` — create a user in the admin's own organisation
    (`email`, `full_name`, `password`, `role`). `409` on duplicate email within the
    organisation.
  - `GET /api/v1/users` — paginated list (offset/limit per
    [API.md](../../docs/API.md#pagination)), scoped to the admin's organisation only.
  - `PATCH /api/v1/users/{id}` — partial update: `is_active` (deactivate/reactivate),
    `role`, `full_name`. Guards: an admin cannot deactivate or demote themselves via
    this endpoint (prevents accidental self-lockout — must be done by another admin),
    and the last remaining active admin in an organisation cannot be deactivated or
    demoted (prevents total organisation lockout). Both guards return `409`.
  - Cross-organisation access to a user id outside the caller's organisation returns
    `404` (never `403`), so the endpoint never confirms another organisation's user
    IDs exist.
- No hard delete of users (matches the "deactivate", not "delete", language in
  TODO Task 12 and the spec's audit-trail-friendly posture); `is_active = false` is
  the only removal mechanism.

### 3. People module

Implements [docs/modules/People.md](../../docs/modules/People.md) exactly as planned
there:

- **`companies` table**: `id`, `organisation_id`, `name`, `type` (ENUM `customer` /
  `supplier` / `other` — fixed by domain), `address`, `phone`, `general_email`,
  `notes`, `created_by_id` (FK → `users.id`, nullable), `updated_by_id` (FK →
  `users.id`, nullable), `created_at`/`updated_at`. `created_by_id`/`updated_by_id`
  follow the convention already documented in
  [Database.md](../../docs/Database.md#naming-conventions) ("added when auth lands in
  Milestone 1").
- **`people` table**: `id`, `organisation_id`, `company_id` (nullable FK →
  `companies.id`), `first_name`, `last_name`, `email` (nullable — not everyone has
  one), `phone`, `role`, `department`, `notes`, `is_employee` (bool),
  `created_by_id`, `updated_by_id`, `created_at`/`updated_at`.
- **Validation invariant** (service + Pydantic layer, not a DB constraint — mixed
  employee/contact modelling per the module doc): `is_employee` is `True` if and only
  if `company_id` is `None`. Enforced in the schema validator so the API rejects a
  contradictory combination with `422` before it reaches the service.
- **Endpoints** under `/api/v1/people` and `/api/v1/companies` (both prefixes already
  reserved in [API.md](../../docs/API.md)), all requiring authentication (any active
  user in the organisation, not admin-only — People is a shared directory, not an
  admin function):
  - `GET/POST /api/v1/companies`, `GET/PATCH/DELETE /api/v1/companies/{id}`.
  - `GET /api/v1/companies/{id}/people` — contacts for one company.
  - `GET/POST /api/v1/people`, `GET/PATCH/DELETE /api/v1/people/{id}`.
  - `GET /api/v1/people?search=` — name/email/role substring search (case-insensitive
    `ILIKE` on PostgreSQL).
  - `DELETE /api/v1/companies/{id}` returns `409` if the company still has any
    `people` rows referencing it (protects referential integrity; the operator must
    reassign or delete contacts first). Per
    [Database.md](../../docs/Database.md#soft-delete-and-audit-trail), soft delete is
    explicitly deferred until Document Management (M2) needs it — People rows hard
    delete, matching the "purely operational/lookup tables may hard-delete" carve-out.
  - All list/get/patch/delete operations are organisation-scoped; a request for
    another organisation's `company_id`/`person_id` returns `404`.
- Creator/owner attribution (`created_by_id`) is set from the resolved current user
  on create; `updated_by_id` is set on every update.

## Security assumptions and hard acceptance criteria

These are treated as non-negotiable, verified explicitly (see "Verification" below),
not just implied by the design:

- No endpoint leaks whether a resource exists in another organisation (`404`, not
  `403`, for cross-org lookups by ID).
- No endpoint leaks whether an email/account exists via differing error messages
  between "wrong password" and "no such user" and "inactive user" on login.
- Passwords are never stored, logged, or returned in plaintext anywhere (hashed
  column only; Pydantic response schemas never include `hashed_password`).
- JWTs are validated for signature, expiry, and `token_version` match on every
  request; an expired, tampered, or revoked (logged-out) token is rejected with `401`.
- Inactive users cannot authenticate (login `401`) and cannot use an already-issued
  token (`get_current_user` re-checks `is_active` on every request, not just at
  login).
- `JWT_SECRET_KEY` has no default and the app refuses to start without one (no silent
  weak-secret fallback).
- No secrets (JWT secret, bootstrap admin password, database password) are ever
  committed; `.env.example` carries only placeholders, per the existing pattern.
- Admin-only endpoints (`/api/v1/users/*`, and admin-only fields on it) reject
  non-admin callers with `403`.

## Test strategy

- **Backend unit tests** (`backend/tests/unit/`, SQLite where portable): password
  hashing round-trip, JWT encode/decode (valid, expired, tampered signature, wrong
  `ver`), Pydantic schema validation (People's `is_employee`/`company_id` invariant,
  email format), service-layer logic reachable without PostgreSQL-only features.
- **Backend integration tests** (`backend/tests/integration/`, real PostgreSQL,
  following the existing `test_database_baseline.py` pattern of running
  `alembic upgrade head` then exercising the app via `httpx.AsyncClient` against
  `ASGITransport`): full login/logout/me flow; inactive-user login rejection;
  expired/invalid-token rejection; user management CRUD including the
  self-deactivation and last-admin guards; People CRUD including the
  `is_employee`/`company_id` invariant, the `companies` delete-with-contacts guard,
  and — critically — cross-organisation isolation (a second seeded organisation and
  user, asserting `404` for cross-org IDs) for both users and People endpoints.
- **Frontend** (Vitest + React Testing Library): login form (success, invalid
  credentials, loading/error states), auth context/protected-route behaviour, user
  management list/create/deactivate flows (mocked API), People companies/contacts
  list/create flows (mocked API) — following the existing `HealthStatus.test.tsx`
  pattern of mocking the typed API client, not `fetch` directly.
- All new behaviour is written test-first (RED confirmed, then GREEN), per
  [Contributing.md](../../docs/Contributing.md#test-first-workflow-red-green-refactor).

## Migration and rollback strategy

- Three forward-only Alembic migrations (one per slice, matching the commit
  boundaries below): `users` table; `companies` + `people` tables. Each is reviewed by
  hand after autogeneration (per [Database.md](../../docs/Database.md#orm-and-migrations)),
  each implements a best-effort `downgrade()` (`drop_table`, in reverse FK order).
- Verified locally with a real upgrade → downgrade → upgrade cycle against PostgreSQL
  before being considered done, in addition to the integration tests that run
  `upgrade head` per test session.
- No destructive migration touches the Milestone 0 `organisations`/`configuration`
  tables. The bootstrap admin is created by application code at startup, not by a
  migration, so no credential material ever appears in a migration file or the
  Alembic version history.

## Out of scope (explicitly deferred)

- Multi-organisation login / a user belonging to more than one organisation (future
  SaaS — see [FutureIdeas.md](../../docs/FutureIdeas.md)).
- Refresh tokens, per-device session tracking/listing, "log out other sessions"
  granularity finer than all-sessions.
- Password reset / forgot-password email flow (no email sending infrastructure exists
  yet; out of scope until a module needs it).
- Soft delete / audit log for People records (deferred to Document Management, M2,
  per [Database.md](../../docs/Database.md#soft-delete-and-audit-trail)).
- Company/person import (CSV/vCard) — noted as a People "future improvement".
- Row-level security enforcement in PostgreSQL (defence-in-depth item tracked in
  [FutureIdeas.md](../../docs/FutureIdeas.md); application-level `organisation_id`
  filtering is the Milestone 1 mechanism).

## Suggested commit boundaries

1. `docs: plan Milestone 1 (auth, organisations, people) before implementation` — this
   plan, `CurrentStatus.md`, `TODO.md` updated to "in progress".
2. `feat: add JWT authentication with Argon2id hashing and bootstrap admin` — `users`
   table + migration, security core, auth module (login/logout/me), current-user
   dependencies, bootstrap mechanism, backend tests, `API.md`/`Database.md`/
   `DecisionLog.md` updates.
3. `feat: add organisation-scoped user management` — users module (admin CRUD),
   backend tests, doc updates.
4. `feat: add People module (employees, customers, suppliers, contacts)` —
   `companies`/`people` tables + migration, module backend, tests,
   `docs/modules/People.md` updated to `Status: Implemented`.
5. `feat: add authentication UI` — frontend routing, auth context, login screen,
   protected routes, frontend tests.
6. `feat: add user management UI` — frontend users screens, tests.
7. `feat: add People module UI` — frontend companies/people screens, tests.
8. `chore: verify Milestone 1 end-to-end via Docker Compose` — any fixes found during
   the full smoke test, `Docker.md`/`Deployment.md` updates if needed.
9. `docs: mark Milestone 1 implemented` — close out `CurrentStatus.md`, `TODO.md`,
   this plan's checkboxes.

Smaller/differently-grouped commits are acceptable as long as each is a coherent,
working, tested unit, per [Contributing.md](../../docs/Contributing.md).

## Acceptance criteria

- [ ] `users`, `companies`, `people` tables exist via reviewed Alembic migrations,
      each verified with a real upgrade → downgrade → upgrade cycle against
      PostgreSQL.
- [ ] Bootstrap admin mechanism creates exactly one admin user on first startup with
      no committed credential, is idempotent on restart, and is covered by a test.
- [ ] Login, logout (token revocation via `token_version`), and `GET /me` work
      end-to-end against real PostgreSQL, with passing tests for success, wrong
      password, inactive user, and expired/invalid/revoked tokens.
- [ ] User management (`/api/v1/users`) supports create/list/deactivate, is
      admin-only, enforces the self-deactivation and last-admin guards, and is
      organisation-scoped (`404` cross-org), all covered by tests.
- [ ] People module (`/api/v1/people`, `/api/v1/companies`) implements the schema and
      endpoints in [docs/modules/People.md](../../docs/modules/People.md), enforces
      the `is_employee`/`company_id` invariant and the companies-with-contacts delete
      guard, is organisation-scoped (`404` cross-org), and attributes
      `created_by_id`/`updated_by_id`, all covered by tests.
- [ ] Frontend: login screen, protected routing, logout; admin user-management
      screens; People companies/contacts screens — all calling real backend endpoints
      through the typed API client convention, covered by Vitest tests.
- [ ] All commands in
      [CodingStandards.md](../../docs/CodingStandards.md#commands-established-in-milestone-0-referenced-by-every-later-batch)
      pass: `ruff check`, `ruff format --check`, `mypy` (strict), `pytest` (unit +
      integration), `npm run lint`, `format:check`, `typecheck`, `test`, `build`.
- [ ] `docker compose up --build` smoke test: bootstrap admin can log in through the
      browser UI, create and deactivate a user, create a company and contacts, and
      all of it survives a `docker compose down` / `up` restart (no `-v`).
- [ ] Every hard security acceptance criterion above ("Security assumptions") verified
      by a passing test, not just asserted in this document.
- [ ] `docs/API.md`, `docs/Database.md`, `docs/modules/People.md`,
      `docs/DecisionLog.md`, `docs/CurrentStatus.md`, `docs/TODO.md` updated in the
      same commits as the behaviour they describe.

## Next milestone after this one

Milestone 2 — Document Management. See
[Roadmap.md](../../docs/Roadmap.md#m2-document-management).

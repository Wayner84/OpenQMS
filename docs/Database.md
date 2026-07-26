# Database

This document defines the database engine, migration workflow, and schema
conventions for openQMS. Milestone 0 implements the baseline described here; every
later module must continue to follow this contract. See
[DecisionLog.md](DecisionLog.md) for why these choices were made.

## Engines

- **Production / Docker: PostgreSQL** (a recent stable major version, pinned in
  `docker-compose.yml`). This is the only engine self-hosted deployments run.
- **Local development and fast unit tests: SQLite** is permitted, using an on-disk or
  in-memory database via SQLAlchemy's `sqlite+aiosqlite` driver.
- **Policy:** any test that exercises a PostgreSQL-only feature (`JSONB` operators,
  `ON CONFLICT` specifics, full-text search, etc.) must run as an integration test
  against real PostgreSQL (via the `db` Compose service or a disposable test
  container), never against SQLite. Unit tests that only exercise ORM-level logic
  reachable identically on both engines may use SQLite for speed. This split is
  enforced by directory: `backend/tests/unit/` may use SQLite; `backend/tests/
  integration/` must use PostgreSQL.

## ORM and migrations

- SQLAlchemy 2.0 declarative models using typed `Mapped[]` / `mapped_column()` syntax
  — no untyped `Column()` declarations in new code.
- Alembic manages all schema changes. Workflow:
  1. Change the SQLAlchemy model(s).
  2. Run `alembic revision --autogenerate -m "<reason>"` to draft a migration.
  3. **Manually review** the generated migration — autogenerate does not reliably
     detect column type changes, renames, or data migrations. Adjust by hand as
     needed, including a data migration where a schema change requires one.
  4. Run `alembic upgrade head` locally (and let the `backend` container run it on
     startup — see [Docker.md](Docker.md)) to verify it applies cleanly.
  5. Commit the migration file together with the model change and any doc updates in
     the same commit, per the project's [Contributing.md](Contributing.md) workflow.
- Migrations are never edited after being merged; a mistake is fixed by a new,
  forward-only migration.
- Downgrades (`alembic downgrade`) are implemented on a best-effort basis; PostgreSQL
  volume backups (see [Deployment.md](Deployment.md)) are the primary recovery path
  for destructive mistakes, not migration downgrades.

## Naming conventions

- Tables: `snake_case`, plural nouns (`documents`, `ncr_records`, `calibration_events`).
- Columns: `snake_case`.
- Primary key column: `id`, type UUID (see below).
- Foreign key columns: `<referenced_table_singular>_id`, e.g. `organisation_id`,
  `document_id`.
- Timestamps: every table includes `created_at` and `updated_at`
  (`timestamptz`/`TIMESTAMP WITH TIME ZONE`, set server-side, `updated_at` maintained
  by an ORM-level `onupdate`). Tables that need it also carry `created_by_id` /
  `updated_by_id` referencing the acting user, added when auth lands in Milestone 1.
- Enumerations (status fields, workflow states) are implemented as PostgreSQL
  `ENUM` types where the set of values is truly fixed by the domain (e.g. an NCR's
  fixed workflow stage names), and as a database-driven lookup table where the spec
  calls for configurability (e.g. document/NCR numbering prefixes, risk matrices —
  see "Business configuration" below). When in doubt, prefer the configurable lookup
  table, per the spec's cross-cutting data-driven-configuration requirement.
- Migration file names: Alembic's default revision hash prefix plus a short slug, e.g.
  `592fe625cdd5_add_organisations_table.py`.

## Primary key strategy

All new tables use a UUID primary key (SQLAlchemy 2.0 `Uuid` column type, Python
`uuid.uuid4` default, stored as native `uuid` in PostgreSQL and as `CHAR(32)` in
SQLite). Rationale and trade-offs are recorded in
[DecisionLog.md](DecisionLog.md#2026-07-25-primary-key-strategy).

## Multi-tenancy baseline

Every tenant-scoped table (i.e. every table except genuinely global, cross-instance
metadata such as an Alembic version table) carries a non-nullable `organisation_id`
foreign key to `organisations.id`. Milestone 0 introduces:

### `organisations` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `name` | text, not null | Display name, e.g. "Default Organisation" |
| `slug` | text, unique, not null | URL/identifier-safe short name |
| `created_at` / `updated_at` | timestamptz | |

Milestone 0 seeds exactly one row (via the initial Alembic migration) representing the
self-hosted instance's own organisation. No UI or API for creating additional
organisations exists yet — that is deferred until hosted/SaaS work is scheduled (see
[FutureIdeas.md](FutureIdeas.md)); the table exists now purely so every later
tenant-scoped table has something correct to reference from day one.

### `configuration` table

Proves the "business configuration is database-driven" cross-cutting requirement end
to end in Milestone 0, without yet having a real business rule (like document
numbering) to attach it to:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `organisation_id` | UUID, FK → `organisations.id`, not null | |
| `key` | text, not null | e.g. `"instance.display_name"` |
| `value` | JSONB, not null | Structured value; shape depends on `key` |
| `created_at` / `updated_at` | timestamptz | |

Unique constraint on (`organisation_id`, `key`). Later modules add their own typed
configuration (e.g. an NCR module's `ncr_numbering_scheme` row) using this same
pattern rather than hard-coding prefixes, intervals, or thresholds in code.

### Implemented migration and verification

The baseline is implemented by
`backend/alembic/versions/592fe625cdd5_create_organisations_and_configuration_.py`.
`backend/tests/integration/test_database_baseline.py` verifies it against real
PostgreSQL, including exact-one-row seeding after repeated upgrades, JSONB storage,
and the readiness endpoint. SQLite unit tests cover portable ORM constraints only.

### `users` table (Milestone 1)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `organisation_id` | UUID, FK → `organisations.id`, not null | |
| `email` | text, not null | Unique per (`organisation_id`, `email`) — see below |
| `hashed_password` | text, not null | Argon2id, never plaintext (see [DecisionLog.md](DecisionLog.md)) |
| `full_name` | text, not null | |
| `role` | native PostgreSQL ENUM (`admin`, `member`) | Fixed by domain, not a `configuration` row |
| `is_active` | boolean, not null, default `true` | Deactivation, not deletion — no hard delete of users |
| `token_version` | integer, not null, default `0` | Implements logout/all-sessions revocation — see DecisionLog |
| `created_at` / `updated_at` | timestamptz | |

Unique constraint on (`organisation_id`, `email`). Login resolves a user by email
alone (not scoped by organisation), because Milestone 1 has exactly one organisation
in practice — see `backend/app/modules/auth/service.py` and the
[Milestone 1 plan](../.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md).
Implemented by `backend/alembic/versions/bace347a5fca_add_users_table.py`; no
credential data is ever seeded by a migration — the bootstrap admin is created by
application code at startup (`backend/app/core/bootstrap.py`) instead, per
[DecisionLog.md](DecisionLog.md).

### `companies` and `people` tables (Milestone 1)

Implements the People module ([docs/modules/People.md](modules/People.md)) — a
shared directory of employees, customers, suppliers, and contacts. Implemented by
`backend/alembic/versions/f151a2c68c12_add_companies_and_people_tables.py`.

`companies`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `organisation_id` | UUID, FK → `organisations.id`, not null | |
| `name` | text, not null | |
| `type` | native PostgreSQL ENUM (`customer`, `supplier`, `other`) | Fixed by domain, default `other` |
| `address` / `phone` / `general_email` / `notes` | nullable | |
| `created_by_id` / `updated_by_id` | UUID, FK → `users.id`, nullable | Attribution — set from the authenticated caller |
| `created_at` / `updated_at` | timestamptz | |

`people`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `organisation_id` | UUID, FK → `organisations.id`, not null | |
| `company_id` | UUID, FK → `companies.id`, nullable | Null = employee; populated = contact at that company |
| `first_name` / `last_name` | text, not null | |
| `email` / `phone` / `role` / `department` / `notes` | nullable | |
| `is_employee` | boolean, not null, default `false` | Must agree with `company_id` — see invariant below |
| `created_by_id` / `updated_by_id` | UUID, FK → `users.id`, nullable | |
| `created_at` / `updated_at` | timestamptz | |

**Invariant**: `is_employee` is `true` if and only if `company_id` is `null`.
Enforced by a Pydantic validator (`backend/app/modules/people/schemas.py`), not a DB
constraint — the model layer permits both fields to vary independently so unit tests
can exercise ORM behaviour directly, but every write through the API is rejected
with `422` if the two disagree. A `companies` row cannot be deleted while any
`people` row still references it (`409`); per
[the carve-out below](#soft-delete-and-audit-trail), both tables hard-delete.

### Documents and related tables (Milestone 2)

Implements the core schema of the Document Management module
([docs/modules/DocumentManagement.md](modules/DocumentManagement.md)) — see
[.hermes/plans/2026-07-26-milestone-2-document-management.md](../.hermes/plans/2026-07-26-milestone-2-document-management.md)
for full reasoning. Implemented by
`backend/alembic/versions/8dc9425047ca_add_document_categories_tags_documents_.py`.
The approval workflow (`document_approvals`), acknowledgements
(`document_acknowledgements`), and version file upload/download/preview are not
implemented yet — later Milestone 2 commits.

`document_categories`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `organisation_id` | UUID, FK → `organisations.id`, not null | |
| `name` | text, not null | |
| `parent_category_id` | UUID, FK → `document_categories.id`, nullable | Self-referencing, for a category tree |
| `created_at` / `updated_at` | timestamptz | |

`document_tags`: `id`, `organisation_id`, `name` (unique per organisation),
`created_at`/`updated_at`. Free-form, admin-created labels.

`document_tag_links`: `document_id`, `tag_id` (composite PK, both FKs) — a plain
many-to-many join table between `documents` and `document_tags`.

`documents`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `organisation_id` | UUID, FK → `organisations.id`, not null | |
| `category_id` | UUID, FK → `document_categories.id`, nullable | |
| `number` | text, not null | **Server-generated**, never client-supplied — see "Configurable document numbering" below. Unique per (`organisation_id`, `number`) |
| `title` | text, not null | |
| `owner_id` | UUID, FK → `people.id`, nullable | An organisational assignment, not an API actor — see the Milestone 2 plan's design decision 1 for why this differs from `document_approvals`/`document_acknowledgements` below, which reference `users.id` instead |
| `status` | native ENUM (`draft`/`in_review`/`approved`/`obsolete`) | Service-maintained cache of the document's overall state, derived from its versions' workflow stage |
| `current_version_id` | UUID, FK → `document_versions.id`, nullable | Added with `use_alter=True` (see the migration's docstring) to resolve the circular reference with `document_versions.document_id` |
| `deleted_at` | timestamptz, nullable | Soft delete — see "Soft delete and audit trail" below |
| `created_by_id` / `updated_by_id` | UUID, FK → `users.id`, nullable | |
| `created_at` / `updated_at` | timestamptz | |

`document_versions`: `id`, `document_id` (FK, not null), `version_number` (integer,
sequential per document, not user-supplied), `storage_key` (text, not null —
server-generated; never exposed over the API, never derived from client input),
`original_filename` (text, not null — display only, never used to build a
filesystem path), `content_type`, `size_bytes`, `checksum_sha256`, `change_summary`
(nullable), `status` (native ENUM `draft`/`in_review`/`approved`/`rejected`/
`obsolete`), `created_by_id` (FK → `users.id`, nullable), `created_at`. Immutable
after creation except `status`; no `updated_at`. Not yet reachable through any
upload endpoint in this slice — the table exists so `documents.current_version_id`
has somewhere to point once upload lands.

#### Configurable document numbering

A `configuration` row per organisation, key `document_numbering_scheme`, value
`{"prefix": "DOC", "separator": "-", "padding": 4, "next_sequence": 1}` — seeded by
the same migration for the existing default organisation. `number` is generated as
`f"{prefix}{separator}{next_sequence:0{padding}d}"` (default: `DOC-0001`,
`DOC-0002`, ...), reading the row with `SELECT ... FOR UPDATE` under PostgreSQL so
concurrent document creation can't allocate the same number twice (a no-op under
SQLite, which has no row-level locking and is single-writer for the unit tests that
use it). See `backend/app/modules/documents/numbering.py`. A second seeded row,
key `document_upload_policy`
(`{"allowed_extensions": [...], "max_size_mb": 50}`), is not consumed by any code
yet — it is seeded now, ready for the upload slice.

## Soft delete and audit trail

Milestone 0 deferred this until "the first module that needs it (Document
Management, Milestone 2)"; Milestone 2 implements the narrowly-needed half now:
`documents.deleted_at` (nullable timestamptz) is set instead of a hard delete, and
every list/get path excludes rows where it is non-null. Purely operational/lookup
tables (`document_categories`, `document_tags`) continue to hard-delete, matching
People's existing precedent.

A generic, cross-module, append-only `audit_log` table (originally sketched
alongside soft delete here) is **deliberately not built** in Milestone 2 — see
[DecisionLog.md](DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table)
for the reasoning (in short: `document_versions`, and the `document_approvals`/
`document_acknowledgements` tables added in a later Milestone 2 slice, already form
an immutable, actor-and-timestamp-stamped trail for everything that matters in
document control; a generic instrumentation layer for every table's mutations is a
materially larger, separate piece of work).

## Connection and session management

- `backend/app/core/db.py` creates a single async SQLAlchemy `Engine` from the
  `DATABASE_URL` environment variable and an `async_sessionmaker`.
- Routers depend on a `get_session` FastAPI dependency that yields an `AsyncSession`
  scoped to one request and closes it afterward; no session is ever shared across
  requests.
- Services receive the session via dependency injection; they do not create their own
  engine or session.

## Related documents

- [DecisionLog.md](DecisionLog.md) — reasoning for engine, ORM, PK and multi-tenancy
  choices.
- [Architecture.md](Architecture.md) — how the database fits the layered backend.
- [API.md](API.md) — how database state is exposed over HTTP.
- [Docker.md](Docker.md) — how PostgreSQL runs and persists data in Compose.

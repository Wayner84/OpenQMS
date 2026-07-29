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

Implements the full schema of the Document Management module built so far
([docs/modules/DocumentManagement.md](modules/DocumentManagement.md)) — see
[.hermes/plans/2026-07-26-milestone-2-document-management.md](../.hermes/plans/2026-07-26-milestone-2-document-management.md)
for full reasoning. Implemented by
`backend/alembic/versions/8dc9425047ca_add_document_categories_tags_documents_.py`
(categories/tags/documents/versions),
`backend/alembic/versions/ea4516740593_add_document_approvals.py`
(`document_approvals`), and
`backend/alembic/versions/b8a145cc3e28_add_document_acknowledgements.py`
(`document_acknowledgements`). Version file upload/download/preview, the
approval/rejection workflow, and acknowledgements are all implemented — see
[API.md](API.md#document-management-milestone-2-in-progress) and
[DecisionLog.md](DecisionLog.md#2026-07-26-document-upload-request-body-size-cap-version-number-locking-and-upload-policy-extension-validation) /
[DecisionLog.md](DecisionLog.md#2026-07-26-document-approval-workflow-a-status-cache-integrity-bug-and-a-toctou-race)
for the storage security posture and the fixes an independent review required
before the upload and workflow slices were committed (the acknowledgements slice's
own independent review found no issues).

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
sequential per document, allocated under a `SELECT ... FOR UPDATE` lock on the
parent `documents` row so concurrent uploads to the same document can't race to the
same number), `storage_key` (text, not null — server-generated; never exposed over
the API, never derived from client input), `original_filename` (text, not null —
sanitised at upload time: directory components and non-printable/quote characters
stripped, so it's safe for both display and the download `Content-Disposition`
header, but still never used to build a filesystem path), `content_type` (derived
server-side from the validated extension, never the client's declared
`Content-Type`), `size_bytes`, `checksum_sha256`, `change_summary` (nullable),
`status` (native ENUM `draft`/`in_review`/`approved`/`rejected`/`obsolete`),
`created_by_id` (FK → `users.id`, nullable), `created_at`. Immutable after creation
except `status`; no `updated_at`.

`document_approvals`: `id`, `document_version_id` (FK → `document_versions.id`,
not null), `approver_id` (FK → `users.id`, not null — see decision 1 above),
`decision` (native ENUM `approved`/`rejected`), `comments` (nullable at the DB
layer; required by the service layer when `decision=rejected`), `decided_at`
(timestamptz, not null). Immutable after creation — no update/delete path exists.
Every mutation of `documents.status`/`current_version_id` or a
`document_versions.status` outside of upload/soft-delete now goes through a
shared `_lock_document` helper (`SELECT ... FOR UPDATE` on the parent `documents`
row, a no-op on SQLite) acquired *before* reading the target version's state, so
two concurrent workflow transitions on the same document serialise correctly —
see
[DecisionLog.md](DecisionLog.md#2026-07-26-document-approval-workflow-a-status-cache-integrity-bug-and-a-toctou-race)
for the race this closes.

`document_acknowledgements`: `id`, `document_version_id` (FK →
`document_versions.id`, not null), `acknowledged_by_id` (FK → `users.id`, not
null — same reasoning as `document_approvals.approver_id`), `acknowledged_at`
(timestamptz, not null). Unique on (`document_version_id`, `acknowledged_by_id`)
— re-acknowledging is idempotent (returns the existing row), enforced both by
this DB constraint and, defensively, by the service layer catching the resulting
`IntegrityError` under a genuine write-write race. Immutable after creation — no
update/delete path exists. An independent security review found no issues in
this slice.

#### Search, filtering, and version comparison

`GET /api/v1/documents` supports `search` (ILIKE across `title`/`number`) and
`tag` (an exact-name join through `document_tag_links`/`document_tags`, itself
defensively scoped by `organisation_id` even though the write path already
guarantees a tag can only link to a document in its own organisation) alongside
the existing `category_id`/`status`/`owner_id` exact filters — see
[API.md](API.md#document-management-milestone-2-in-progress).
`GET .../versions/{a}/compare/{b}` reads both versions' files directly through
the same server-side `resolve_path`/`storage_key` mechanism used by download/
preview (never a raw path) and diffs them with Python's stdlib `difflib` when
both are text-based and at or under a 5 MB cap (`MAX_TEXT_DIFF_BYTES` in
`app/modules/documents/service.py`) — above that, or for any other content type,
only a checksum-changed boolean is reported. See
[DecisionLog.md](DecisionLog.md#2026-07-26-document-searchfiltering-and-version-comparison-a-text-diff-size-cap-and-defensive-tag-scoping)
for the size cap, the defensive tag-join scoping, and a missing-file error path
an independent review added to this slice.

#### Upload policy

A second `configuration` row per organisation, key `document_upload_policy`, value
`{"allowed_extensions": [...], "max_size_mb": 50}` — seeded by the same migration.
Read on every upload (`app/modules/documents/upload_policy.py`); any configured
extension the backend has no `Content-Type` mapping for is silently dropped (with a
logged warning), so a misconfigured policy degrades gracefully rather than crashing
uploads. Files are stored under the `openqms_uploads` Docker volume (reserved since
Milestone 0), at
`{organisation_id}/{document_id}/{server-generated UUID}{validated extension}` —
see [Deployment.md](Deployment.md#backups) for why this volume must now be backed
up alongside the database.

#### Configurable document numbering

A `configuration` row per organisation, key `document_numbering_scheme`, value
`{"prefix": "DOC", "separator": "-", "padding": 4, "next_sequence": 1}` — seeded by
the same migration for the existing default organisation. `number` is generated as
`f"{prefix}{separator}{next_sequence:0{padding}d}"` (default: `DOC-0001`,
`DOC-0002`, ...), reading the row with `SELECT ... FOR UPDATE` under PostgreSQL so
concurrent document creation can't allocate the same number twice (a no-op under
SQLite, which has no row-level locking and is single-writer for the unit tests that
use it). See `backend/app/modules/documents/numbering.py`. The second seeded row,
key `document_upload_policy`, is consumed by the upload endpoint — see "Upload
policy" below.

### Suppliers and related tables (Milestone 3)

Per [docs/modules/Suppliers.md](modules/Suppliers.md) and the
[Milestone 3 plan](../.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md).
All three tables carry `organisation_id`.

- **`suppliers`** — `company_id` (FK → `companies.id`, not null; name/address/
  contact data lives on the shared `companies` row, not duplicated here, matching
  the module's stated design), `approval_status` (native enum `approved`/`pending`/
  `suspended`, default `pending`), `risk_rating` (nullable native enum `low`/
  `medium`/`high` — a plain operator-set field, not an auto-computed score; the
  shared risk-scoring engine research question, TODO Task 37, is unresolved and
  deliberately not answered here), `is_preferred` (boolean, default `false`),
  `notes`, `created_by_id`/`updated_by_id`, `created_at`/`updated_at`. Hard delete
  (unlike `documents`): a supplier carries no audit-significant history of its own
  beyond its certifications/performance records, which cascade
  (`ON DELETE CASCADE`) — matching the existing `companies`/`people` hard-delete
  precedent, not a new one.
- **`supplier_certifications`** — `supplier_id` (FK, cascade delete),
  `certification_type` (free text, not an enum — an open-ended, operator-defined
  list), `certificate_document_id` (nullable FK → `documents.id`), `issued_date`/
  `expiry_date` (nullable dates), `created_at`/`updated_at`.
- **`supplier_performance_records`** — `supplier_id` (FK, cascade delete), `period`
  (free text, e.g. `"2026-Q3"`), `score` (numeric, operator-entered — same reasoning
  as `risk_rating` above), `notes`, `created_by_id`, `created_at`. Append-only from
  the API's perspective (no update/delete route), matching `document_versions`/
  `document_approvals`'s existing immutable-history pattern.

#### Certification expiry reminder window

A `configuration` row per organisation, key
`supplier_certification_reminder_window_days`, value `{"days": 30}` — seeded by the
suppliers migration for the existing default organisation. Read (never seeded on
read; a missing row falls back to the built-in default) by
`GET /api/v1/suppliers/certifications/expiring` via
`backend/app/modules/suppliers/reminder_config.py`. Actually sending a reminder is
out of scope for this milestone — no notification/email infrastructure exists yet;
this row only drives the read-only "expiring soon" list endpoint.

### Products and related tables (Milestone 3)

Per [docs/modules/Products.md](modules/Products.md) and the
[Milestone 3 plan](../.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md).
All four tables carry `organisation_id` except the two link tables, which are scoped
transitively through their parent `product_id`.

- **`product_categories`** — flat (non-hierarchical), unlike Document Management's
  tree-shaped `document_categories`: `name`, `created_at`/`updated_at`.
- **`products`** — `part_number` (text, not null; unique per organisation via
  `UniqueConstraint(organisation_id, part_number)` as a DB-level backstop, but the
  clean `409` on conflict is enforced at the service layer first, matching
  `document_tags.name`'s existing precedent — not a raw `IntegrityError` leaking to
  the client), `description`, `revision` (default `"A"`), `category_id` (nullable FK
  → `product_categories.id`), `type` (native enum `internal`/`purchased`/
  `assembly`/`component`), `manufacturing_notes`, `created_by_id`/`updated_by_id`,
  `created_at`/`updated_at`. Hard delete, matching `suppliers`' precedent — a product
  record itself has no workflow/approval history to preserve.
- **`product_documents`** — `product_id` (FK, cascade delete), `document_id` (FK →
  `documents.id`, not null), `relationship_type` (native enum `drawing`/
  `specification`/`cad`). Composite uniqueness on `(product_id, document_id,
  relationship_type)` — the same document can be linked under more than one
  relationship type, but not twice under the identical type.
- **`product_supplier_links`** — `product_id` (FK, cascade delete), `supplier_id`
  (FK → `suppliers.id`, not null), `is_preferred` (boolean, default `false`).
  Composite uniqueness on `(product_id, supplier_id)`.

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

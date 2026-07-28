# Milestone 2 — Document Management

**Status:** In progress — implementation is complete through the Document Management
frontend; Docker/browser/security verification and Milestone 2 closeout remain.
**Date planned:** 2026-07-26

## Purpose

Build core QMS document control on top of the completed Milestone 1 platform (auth,
organisations, People), per
[Roadmap.md](../../docs/Roadmap.md#m2-document-management),
[docs/modules/DocumentManagement.md](../../docs/modules/DocumentManagement.md), and
TODO Task 14 in [docs/TODO.md](../../docs/TODO.md): categories, tags, documents,
immutable versioned files, configurable numbering, an approval/rejection workflow,
electronic acknowledgement, search/filtering, permissions, secure upload/download/
preview, and practical version comparison.

Background reading: [Architecture.md](../../docs/Architecture.md),
[Database.md](../../docs/Database.md), [API.md](../../docs/API.md),
[CodingStandards.md](../../docs/CodingStandards.md),
[Contributing.md](../../docs/Contributing.md),
[docs/modules/DocumentManagement.md](../../docs/modules/DocumentManagement.md), and
the completed
[Milestone 1 plan](2026-07-25-milestone-1-auth-organisations-people.md) for the
established conventions this milestone continues (organisation scoping via
`CurrentUser`, `created_by_id`/`updated_by_id` attribution, the pagination envelope,
`404`-not-`403` for cross-organisation lookups, offset/limit pagination).

## Design decisions made in this plan (refining the "Planned" module doc)

[docs/modules/DocumentManagement.md](../../docs/modules/DocumentManagement.md) was
written before Milestone 1 existed and sketches the schema at a high level (marked
`Status: Planned`). Three points are refined here, the same way the Milestone 1 plan
refined the People module doc's invariant-enforcement detail:

1. **`document_approvals.approver_id` and `document_acknowledgements`'s actor
   reference `users.id`, not `people.id`.** The module doc originally sketched both
   as referencing `people`. But approving and acknowledging are actions performed by
   an *authenticated caller* through the API — the system must attribute them to the
   verified `current_user`, not to an arbitrary `people` row (Milestone 1 added no
   link between a `users` row and a `people` row, and adding one is out of scope here
   — see "Out of scope" below). Using `users.id` matches the attribution pattern
   already established for `created_by_id`/`updated_by_id` on `companies`/`people`
   themselves, and keeps "who did this" audit trail unambiguous and unforgeable.
   `documents.owner_id` still references `people.id` as originally planned: ownership
   is an organisational assignment (who this document belongs to for business
   purposes), not an action performed through the API, so it can validly reference
   someone without a login. [docs/modules/DocumentManagement.md](../../docs/modules/DocumentManagement.md)
   is updated to match in the same commit that implements it.
2. **A generic, cross-module `audit_log` table (mentioned as a future companion to
   soft delete in [Database.md](../../docs/Database.md#soft-delete-and-audit-trail))
   is explicitly deferred, not built in this milestone**, even though that note ties
   its introduction to "the first module that needs it (Document Management,
   Milestone 2)". Reasoning recorded as a new [DecisionLog.md](../../docs/DecisionLog.md)
   entry in the first implementation commit: `document_versions`,
   `document_approvals`, and `document_acknowledgements` are themselves immutable,
   actor-and-timestamp-stamped audit records for everything that matters in document
   control (who uploaded what, who approved/rejected with what comment, who
   acknowledged and when) — a separate generic audit table would duplicate that
   information without adding real value yet, and building a cross-cutting
   instrumentation layer for *every* table's mutations is a materially larger,
   separate piece of work than this milestone's vertical slice. `documents.deleted_at`
   (soft delete) **is** implemented now, since that part is directly needed and
   narrowly scoped.
3. **Document numbering is organisation-wide, not per-category.** The spec requires
   configurable numbering (prefix, padding) but does not require per-category
   sequences. Per-category or per-document-type numbering is noted as a future
   improvement, not built speculatively now.

## In scope

### 1. Schema

All new tables carry `organisation_id` per
[Database.md](../../docs/Database.md#multi-tenancy-baseline). UUID primary keys,
`created_at`/`updated_at` timestamptz per the established convention.

- **`document_categories`** — `id`, `organisation_id`, `name`, `parent_category_id`
  (nullable, self-referencing FK, for a category tree), `created_at`/`updated_at`.
- **`document_tags`** — `id`, `organisation_id`, `name` (unique per organisation).
- **`document_tag_links`** — `document_id`, `tag_id` (composite PK, both FKs) — plain
  many-to-many join table, no extra columns.
- **`documents`** — `id`, `organisation_id`, `category_id` (nullable FK), `number`
  (text, server-generated — see numbering below, never client-supplied), `title`
  (text, not null), `owner_id` (nullable FK → `people.id` — see decision 1 above),
  `status` (native enum `draft`/`in_review`/`approved`/`obsolete` — service-maintained,
  mirrors the current/latest version's workflow stage; see "Workflow" below),
  `current_version_id` (nullable FK → `document_versions.id`, added with
  `use_alter=True` to resolve the circular reference between `documents` and
  `document_versions`), `deleted_at` (nullable timestamptz — soft delete, per
  [Database.md](../../docs/Database.md#soft-delete-and-audit-trail)), `created_by_id`/
  `updated_by_id` (nullable FK → `users.id`), `created_at`/`updated_at`.
- **`document_versions`** — `id`, `document_id` (FK, not null), `version_number`
  (integer, not null — sequential per document starting at 1, immutable, not
  user-supplied), `storage_key` (text, not null — server-generated relative path
  under the uploads volume; **never** the client's filename, never exposed as a raw
  filesystem path over the API), `original_filename` (text, not null — sanitised for
  *display* only, never used to build a filesystem path), `content_type` (text, not
  null — the type this backend determined the file to be, not blindly trusted from
  the client), `size_bytes` (bigint, not null), `checksum_sha256` (text, not null),
  `change_summary` (nullable text), `status` (native enum `draft`/`in_review`/
  `approved`/`rejected`/`obsolete`), `created_by_id` (nullable FK → `users.id`),
  `created_at`. No `updated_at` — a version row's file-identifying columns are
  immutable after creation; only `status` transitions (via the workflow endpoints
  below, which have their own timestamped `document_approvals` trail).
- **`document_approvals`** — `id`, `document_version_id` (FK, not null), `approver_id`
  (FK → `users.id`, not null — see decision 1), `decision` (native enum `approved`/
  `rejected`), `comments` (nullable text, required by the service layer — not the DB
  — when `decision=rejected`), `decided_at` (timestamptz, not null).
- **`document_acknowledgements`** — `id`, `document_version_id` (FK, not null),
  `acknowledged_by_id` (FK → `users.id`, not null — see decision 1),
  `acknowledged_at` (timestamptz, not null). Unique constraint on
  (`document_version_id`, `acknowledged_by_id`) — one acknowledgement per user per
  version; re-acknowledging is idempotent (returns the existing row), not an error.

### 2. Configurable numbering

A `configuration` row per organisation, key `document_numbering_scheme`, value
`{"prefix": "DOC", "separator": "-", "padding": 4, "next_sequence": 1}` — seeded by a
data migration for the existing default organisation (matching the Milestone 0
seeding pattern), never hard-coded in application code. `create_document` generates
`number` as `f"{prefix}{separator}{next_sequence:0{padding}d}"`, then increments
`next_sequence` in the same transaction, reading the configuration row with
`SELECT ... FOR UPDATE` to serialise concurrent creations safely under PostgreSQL. If
the configuration row is ever missing (should not happen after the seed migration),
the service falls back to a conservative built-in default rather than erroring, and
logs a warning.

### 3. Upload policy (also configuration-driven)

A second seeded `configuration` row, key `document_upload_policy`, value
`{"allowed_extensions": [".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg",
".txt", ".csv"], "max_size_mb": 50}`. Read on every upload; an operator can widen or
narrow it without a deployment. A conservative built-in default is used if the row is
missing.

### 4. Storage and upload/download/preview security

New `backend/app/modules/documents/storage.py`. Files live under the existing
`openqms_uploads` Docker volume (mounted at `/app/uploads`, reserved but unused since
Milestone 0 — see [Docker.md](../../docs/Docker.md#volumes)), configurable via a new
`UPLOADS_DIR` setting (default `/app/uploads`, per `backend/app/core/config.py`'s
existing `Settings` pattern).

Treating every upload as hostile, per this milestone's explicit brief:

- **Server-generated storage names only.** `storage_key` is built entirely from
  server-side identifiers (`{organisation_id}/{document_id}/{uuid4().hex}{ext}`) —
  the client's filename is stored only in `original_filename` for display/download
  purposes and never used to construct a path. This makes path traversal structurally
  impossible (no client input ever becomes a path segment), not just filtered.
- **Type validation is not just the client's `Content-Type` header.** The file
  extension is checked against the configured allow-list, and the file's first bytes
  are checked against a small built-in magic-byte table for the types that have a
  reliable signature (`%PDF` for PDF, `PK\x03\x04` for the Office Open XML/zip-based
  formats, `\x89PNG`/`\xff\xd8\xff` for PNG/JPEG); a mismatch is rejected `422`
  before any bytes are written to disk. Plain-text formats (`.txt`, `.csv`) have no
  reliable signature and are accepted on extension + size alone. This is a
  stdlib-only check (no new dependency, no `libmagic` system package) — sufficient
  for the fixed set of office/PDF/image formats this module supports; not a
  substitute for full content/antivirus scanning, which is out of scope (see below).
- **Size is enforced while streaming**, not after buffering the whole file into
  memory: the upload handler reads in bounded chunks and aborts with `413` the
  moment the configured `max_size_mb` is exceeded, so an oversized upload cannot
  exhaust server memory.
- **No static file mount.** Uploaded files are never served by a `StaticFiles` mount
  or any URL that maps directly to a filesystem path. The only ways to read a file's
  bytes back are the authenticated `download` and `preview` endpoints, which resolve
  `storage_key` → real path server-side after re-verifying the caller's organisation
  owns the parent document — an organisation can never read another organisation's
  file even with a guessed/leaked `storage_key`, because the lookup is always by
  `(document_id, version_id)` scoped to `current_user.organisation_id`, never by
  `storage_key` directly.
- **Download** (`GET .../download`) streams the file as `Content-Disposition:
  attachment` with a sanitised `original_filename` (control characters and `"`
  stripped, to prevent header injection). **Preview** (`GET .../preview`) streams
  `inline` only for previewable content types (PDF and the supported image types);
  any other type returns `415` with a message pointing at `download` instead — the
  frontend never attempts to render a non-previewable type inline.
- **Immutability**: no endpoint ever overwrites a `document_versions` row's file —
  every new upload is a new version with a new `storage_key`. A soft-deleted
  document's files are retained on disk (not deleted), matching the "no hard delete
  of audit-significant data" posture — see [Deployment.md](../../docs/Deployment.md#backups)
  for why the uploads volume must be backed up alongside the database.

### 5. Workflow (state machine)

`document_versions.status`: `draft` → `in_review` → `approved` (or `rejected`, which
is terminal for that specific version — QMS revision history is never silently
reset; a rejected version stays visibly rejected and a new version must be created to
try again) → `obsolete` (a version is marked `obsolete` automatically the moment a
*later* version of the same document is approved, since only one version can be
"current" at a time).

`documents.status` is a service-maintained cache of the document's overall state, not
a separate independent machine: `approved` once any version has ever been approved
(stays `approved` across later version supersessions, since there is always a current
approved version); `in_review` if the latest version is awaiting a decision and none
has ever been approved yet; `draft` otherwise; `obsolete` only via the explicit
whole-document retirement action below (independent of version state — retiring a
document doesn't touch its versions' own statuses).

Endpoints (all under `/api/v1/documents`, all requiring `Authorization: Bearer` for
an **active user** in the organisation unless noted "admin"):

- `POST /api/v1/documents/{id}/versions/{version_id}/submit-for-approval` — any
  active user; `draft` → `in_review`.
- `POST /api/v1/documents/{id}/versions/{version_id}/approve` — **admin only**;
  `in_review` → `approved`; supersedes the previous current version (→ `obsolete`);
  updates `documents.current_version_id`/`status`; records a `document_approvals` row.
- `POST /api/v1/documents/{id}/versions/{version_id}/reject` — **admin only**;
  `in_review` → `rejected`; `comments` required; records a `document_approvals` row.
- `POST /api/v1/documents/{id}/obsolete` — **admin only**; retires the whole document
  (`documents.status` → `obsolete`) regardless of version state.

### 6. Permissions summary

Following the precedent already set by People (shared, low-friction collaboration)
vs. user management (admin-gated, high-trust) in Milestone 1 — and because Milestone 1
introduced no role beyond `admin`/`member` to build a richer approver/reviewer role
model on top of:

| Action | Who |
|---|---|
| List/search/view documents, categories, tags | any active user |
| Create/edit a document's metadata, add a new version, submit for approval | any active user |
| Acknowledge a version | any active user (self only) |
| Create/edit/delete a category or tag | **admin** |
| Approve / reject a version | **admin** |
| Retire (obsolete) a whole document | **admin** |
| Soft-delete a document | **admin** |

Every guard is enforced server-side in the service layer from `current_user`, never
from client-supplied input — matching the non-negotiable "never trust client-side
authorization" rule. A richer configurable-approver-role model (e.g., a
"document controller" role, category-specific approvers) is noted as a future
improvement, not built here — it would need a role/permission model this milestone
has no reason to invent speculatively.

### 7. Search and filtering

`GET /api/v1/documents?search=&category_id=&tag=&status=&owner_id=&limit=&offset=`
per [API.md](../../docs/API.md#filtering-and-search)'s documented convention
(query parameters matching field names for exact filters). `search` is a
case-insensitive substring match (`ILIKE`) across `title` and `number`. `tag` filters
by tag name via a join through `document_tag_links`/`document_tags`. Soft-deleted
documents (`deleted_at IS NOT NULL`) are excluded from every list/get by default, with
no "show deleted" escape hatch in this milestone (not required by the spec; the
files/rows are retained for later admin tooling, not exposed via API yet).

### 8. PDF preview and version comparison

- **Preview**: no new backend PDF-rendering dependency. The backend only needs to
  stream bytes with the right `Content-Type`/`Content-Disposition`; the browser's
  native PDF viewer renders the response. The frontend fetches the preview endpoint
  through the existing typed, authenticated API client (not a bare `<iframe src=...>`,
  which would carry no `Authorization` header), turns the response into a
  `Blob`/object URL, and renders that in an `<iframe>`/`<img>`.
- **Comparison** (`GET /api/v1/documents/{id}/versions/{a}/compare/{b}`): a
  **practical**, not speculative, comparison — metadata diff (title/category/owner at
  time of each version's creation is not tracked per-version, so this compares the
  version-level fields: `change_summary`, `size_bytes`, `checksum_sha256`, uploader,
  `created_at`, `status`) plus a line-level unified text diff (Python's stdlib
  `difflib`) when **both** versions have a text-based content type (`text/plain`,
  `text/csv`); for any other content type (PDF, Office formats, images), the response
  reports whether the checksum changed ("binary content changed"/"unchanged") without
  attempting a structured diff. Richer structured diffing (e.g., PDF text extraction)
  is recorded as a future improvement, matching
  [docs/modules/DocumentManagement.md](../../docs/modules/DocumentManagement.md#future-improvements)'s
  existing "Richer version-comparison" entry.

### 9. Frontend

`frontend/src/modules/documents/`, following the People/Users module conventions
(typed `api.ts`/`types.ts`, feature components, `mountedRef`-guarded effects per
[CodingStandards.md](../../docs/CodingStandards.md#frontend-react-typescript),
`.data-table-wrapper` for responsive tables, `getErrorDetail` for surfacing backend
guard messages):

- `DocumentsPage.tsx` — searchable/filterable list (search box, category/tag/status
  filters, pagination), showing number/title/category/status/owner.
  `CategoriesPage.tsx` and a tag-management affordance (admin-only, matching
  `UsersPage`'s admin-gated pattern) reachable from it.
- `DocumentDetailPage.tsx` — document metadata, version history table, upload-new-
  version form, workflow action buttons (submit/approve/reject — shown only where
  the current user's role and the version's state make the action valid, always
  re-enforced server-side), acknowledgement button/status, a "who has acknowledged"
  list, download links, and a preview panel (inline for previewable types, a
  "Download to view" message otherwise).
- `VersionComparePage.tsx` (or an in-page panel) — select two versions, render the
  metadata diff and, when applicable, the text diff.
- Accessible/responsive states: loading, empty ("No documents yet"), error (`role="alert"`
  inline messages via `getErrorDetail`), and the `<StrictMode>`-safe `mountedRef`
  pattern on every effect that sets state after an `await`, per the Milestone 1
  closeout fix.

## Security assumptions and hard acceptance criteria

Non-negotiable, verified by passing tests, not just asserted:

- No endpoint leaks whether a document/category/tag/version exists in another
  organisation (`404`, never `403`, for cross-org lookups by ID) — same convention as
  Milestone 1.
- No client-supplied path, filename, or storage key is ever used to read/write a file
  on disk; every file access is resolved via `(organisation_id, document_id,
  version_id)` looked up from the database, never from a raw path in the request.
- Uploaded file type is validated by extension **and** content signature (where one
  exists), not by trusting the client's declared `Content-Type`.
- Upload size is bounded and enforced while streaming, not after full buffering.
- Every workflow/permission guard (approve/reject/retire/delete = admin;
  category/tag mutation = admin; everything else = any active user) is enforced
  server-side regardless of what the frontend renders or hides.
- A document's `organisation_id` is always taken from `current_user`, never from a
  request body/query parameter.
- Soft-deleted documents are excluded from every list/read path available to normal
  API consumers.
- `document_versions` rows and their files are never mutated or overwritten after
  creation — only `status` transitions.

## Test strategy

- **Backend unit tests** (`backend/tests/unit/`, SQLite where portable): numbering
  generation logic, upload-policy validation (extension allow-list, magic-byte checks,
  size enforcement — using in-memory byte streams, no real disk I/O required for most
  cases), workflow state-transition guards, version-comparison diff logic
  (text-vs-binary branches), service-layer organisation scoping.
- **Backend integration tests** (`backend/tests/integration/`, real PostgreSQL,
  `httpx.AsyncClient` against `ASGITransport`, following the existing pattern):
  full document lifecycle (create → upload version → submit → approve → supersede →
  acknowledge) against real Postgres; cross-organisation `404`s for documents,
  categories, tags, versions; the numbering sequence advancing correctly under the
  real DB; a rejected-version path; the retire-document action; download/preview
  actually streaming real bytes with correct headers; a path-traversal attempt
  (crafted `original_filename` like `../../etc/passwd`) proven **not** to escape the
  uploads directory; an oversized-upload `413`; a wrong-magic-bytes-for-extension
  upload `422`; admin-only guards rejecting a member with `403`.
- **Frontend** (Vitest + React Testing Library, mocking the typed API client per the
  established pattern): document list/search/filter, upload flow, workflow action
  buttons appearing/behaving correctly per role and version state, acknowledgement
  flow, preview rendering (mocked blob), comparison view, `<StrictMode>`-wrapped
  mount-safety regression tests for every new page, per
  [CodingStandards.md](../../docs/CodingStandards.md#frontend-react-typescript).
- All new behaviour written test-first (RED confirmed, then GREEN), per
  [Contributing.md](../../docs/Contributing.md#test-first-workflow-red-green-refactor).

## Migration and rollback strategy

Three reviewed Alembic migrations, matching the vertical-slice commit boundaries
below, each with a correct `downgrade()` and each verified with a real upgrade →
downgrade → upgrade cycle against PostgreSQL before being considered done (in
addition to the integration suite running `upgrade head` per session):

1. `document_categories`, `document_tags`, `document_tag_links`, `documents`
   (including `deleted_at`, `current_version_id` added via `use_alter=True`),
   `document_versions` — plus a data migration seeding the
   `document_numbering_scheme` and `document_upload_policy` configuration rows for
   the existing default organisation.
2. `document_approvals`.
3. `document_acknowledgements`.

No destructive migration touches any Milestone 0/1 table.

## Out of scope (explicitly deferred)

- Electronic signatures and ISO compliance assistance — already noted as future in
  [docs/modules/DocumentManagement.md](../../docs/modules/DocumentManagement.md) and
  [FutureIdeas.md](../../docs/FutureIdeas.md); not touched by this milestone.
- A generic, cross-module `audit_log` table — see design decision 2 above.
- A `users` ↔ `people` linkage column — not needed once approvals/acknowledgements
  attribute to `users.id` directly (design decision 1 above); may be revisited if a
  future module needs it.
- A configurable approver/reviewer role model beyond the existing admin/member roles.
- Per-category or per-document-type numbering sequences (organisation-wide numbering
  only, per design decision 3).
- Antivirus/deep content scanning of uploads (magic-byte + extension + size validation
  only, per "Storage and upload/download/preview security" above).
- Structured/semantic PDF diffing (text diff only for text-based content types; a
  binary changed/unchanged signal otherwise).
- Document "undelete" / an admin view of soft-deleted documents.
- Any SaaS/multi-organisation feature — out of scope for the whole project until
  scheduled, per [CLAUDE.md](../../CLAUDE.md).

## Suggested commit boundaries

1. `docs: plan Milestone 2 (Document Management) before implementation` — this plan,
   `CurrentStatus.md`, `TODO.md` updated to "in progress".
2. `feat: add document categories, tags, documents and versions with configurable numbering` —
   migration 1, models, schemas, service, router for categories/tags/documents/
   versions (create/list/get/update/delete-soft), configuration-driven numbering,
   backend tests, `API.md`/`Database.md`/`DecisionLog.md`/module doc updates.
3. `feat: add document upload, download, and preview with hostile-input handling` —
   storage module, upload/download/preview endpoints, upload-policy configuration,
   backend tests (including the hostile-input cases), doc updates.
4. `feat: add document approval and rejection workflow` — migration 2, workflow
   endpoints, state-machine guards, tests, doc updates.
5. `feat: add document acknowledgements` — migration 3, acknowledge/list-acknowledgements
   endpoints, tests, doc updates.
6. `feat: add document search, filtering, and version comparison` — search/filter
   query params, compare endpoint, tests, doc updates.
7. `feat: add Document Management frontend` — typed client, list/detail/compare
   pages, categories/tags admin UI, tests.
8. `chore: verify Milestone 2 end-to-end via Docker Compose` — any fixes found during
   the full smoke test, `Docker.md`/`Deployment.md` updates (backup procedure for
   uploads, now that file storage is real).
9. `docs: mark Milestone 2 implemented` — close out `CurrentStatus.md`, `TODO.md`,
   this plan's checkboxes.

Smaller/differently-grouped commits are acceptable as long as each is a coherent,
working, tested unit, per [Contributing.md](../../docs/Contributing.md).

## Acceptance criteria

- [ ] `document_categories`, `document_tags`, `document_tag_links`, `documents`,
      `document_versions`, `document_approvals`, `document_acknowledgements` exist via
      reviewed Alembic migrations, each verified with a real upgrade → downgrade →
      upgrade cycle against PostgreSQL.
- [ ] Document numbering and upload policy are read from the `configuration` table
      (organisation-scoped, seeded by migration), not hard-coded; numbering is
      concurrency-safe under real PostgreSQL.
- [ ] Full workflow (draft → in_review → approved/rejected, supersession → obsolete,
      whole-document retirement) works end-to-end against real PostgreSQL, permission
      guards enforced server-side, all covered by tests.
- [ ] Acknowledgement recording and listing work end-to-end, idempotent on repeat,
      covered by tests.
- [ ] Search/filtering (`search`, `category_id`, `tag`, `status`, `owner_id`) works
      against real PostgreSQL, covered by tests.
- [ ] Upload/download/preview are secure: server-generated storage names, extension +
      magic-byte + size validation, no static file mount, no path ever escapes the
      uploads directory, organisation-scoped file access — every claim proven by a
      passing hostile-input test, not just asserted.
- [ ] Version comparison returns a practical metadata + (text-or-binary-appropriate)
      diff, covered by tests.
- [x] Frontend: document list/search/filter, upload, workflow actions, acknowledgement,
      preview, comparison, categories/tags admin UI — all calling real backend
      endpoints through the typed API client, covered by Vitest tests, accessible and
      responsive.
- [ ] All commands in
      [CodingStandards.md](../../docs/CodingStandards.md#commands-established-in-milestone-0-referenced-by-every-later-batch)
      pass: `ruff check`, `ruff format --check`, `mypy` (strict), `pytest` (unit +
      integration), `npm run lint`, `format:check`, `typecheck`, `test`, `build`.
- [ ] Dependency audits (`pip-audit`, `npm audit`) re-run; no new findings beyond
      already-documented deferrals, or new findings triaged and recorded.
- [ ] An independent security/tenant-isolation review (fresh reviewer, no prior
      session context) of the actual code and tests, findings fixed or explicitly
      deferred with reasoning.
- [ ] `docker compose up --build` smoke test, browser-driven: create a category and
      tag, create a document, upload a version, submit for approval, approve as
      admin, acknowledge as a member, preview and download the file, compare two
      versions — all surviving a `docker compose down`/`up` restart (no `-v`),
      including the uploaded file itself (proving the `openqms_uploads` volume
      persists real file bytes, not just database rows).
- [ ] `docs/API.md`, `docs/Database.md`, `docs/Architecture.md` (if needed),
      `docs/Docker.md`/`docs/Deployment.md` (uploads backup detail),
      `docs/modules/DocumentManagement.md`, `docs/DecisionLog.md`,
      `docs/CurrentStatus.md`, `docs/TODO.md` updated in the same commits as the
      behaviour they describe.

## Next milestone after this one

Milestone 3 — Products and Suppliers. See
[Roadmap.md](../../docs/Roadmap.md#m3-products-and-suppliers).

# API

REST conventions for the openQMS backend. Milestone 0 implements the health and
readiness endpoints; this is the contract every later module must follow. See
[Architecture.md](Architecture.md) for how the API fits the layered backend and
[DecisionLog.md](DecisionLog.md) for why URL path versioning was chosen.

## Versioning

All endpoints are mounted under `/api/v1/`. Each module owns one `APIRouter` with its
own prefix, aggregated into the versioned router in `backend/app/api/v1/router.py`,
e.g. `/api/v1/documents`, `/api/v1/ncr`. A future breaking change would be introduced
as `/api/v2/...` alongside the still-running `v1`, not as an in-place break.

## Interactive documentation

FastAPI's automatic OpenAPI schema is exposed at `/api/v1/openapi.json`, with
interactive docs at `/docs` (Swagger UI) and `/redoc` (ReDoc) in non-production
environments. This is the authoritative, always-current contract; this document
describes conventions the schema itself does not capture (error shape, pagination,
auth headers).

## Request/response conventions

- All request and response bodies are JSON (`application/json`).
- Every request body and response body is defined by an explicit Pydantic schema in
  the owning module's `schemas.py` — no ad hoc dict responses.
- Field names are `snake_case`, matching the database columns they represent, to keep
  the mapping between API, schema, and schema-generated TypeScript types obvious.
- Timestamps are ISO 8601 with timezone (`2026-07-25T12:00:00Z`).
- UUIDs are serialised as their canonical hyphenated string form.

## Error format

Errors use a consistent JSON body regardless of status code:

```json
{
  "detail": "Human-readable summary of what went wrong.",
  "errors": [
    { "field": "email", "message": "value is not a valid email address" }
  ]
}
```

`errors` is present for `422` validation failures (FastAPI/Pydantic's default
validation error shape is normalised into this format via a shared exception handler
in `backend/app/core/errors.py`) and omitted otherwise. Standard HTTP status codes are
used throughout: `400` bad request, `401` unauthenticated, `403` forbidden, `404` not
found, `409` conflict, `422` validation error, `500` unhandled server error. Backend
code never leaks stack traces or internal exception text to the client in `500`
responses; those are logged server-side only.

## Pagination

List endpoints use offset/limit query parameters with a consistent envelope:

```
GET /api/v1/<resource>?limit=50&offset=0
```

```json
{
  "items": [ /* ... */ ],
  "total": 137,
  "limit": 50,
  "offset": 0
}
```

`limit` defaults to 50 and is capped (server-enforced maximum, e.g. 200) to prevent
accidentally unbounded queries. Cursor-based pagination is deferred until a table's
scale actually needs it (tracked in [FutureIdeas.md](FutureIdeas.md)); offset/limit is
sufficient for Milestone 0 and the first modules.

## Filtering and search

Deferred beyond Milestone 0. When modules add filtering (the spec requires "powerful
filtering and saved filters" across the product), the convention will be query
parameters matching field names for exact filters (e.g. `?status=open`) with a
documented, per-endpoint list of filterable fields in that module's docs
(`docs/modules/<Module>.md`) — not a generic/opaque query language, to keep endpoints
simple and typed.

## Authentication

Implemented in Milestone 1: JWT bearer tokens (`Authorization: Bearer <token>`)
issued on login, validated per-request via the `get_current_user` FastAPI dependency
(`backend/app/core/deps.py`), which resolves the current user and their organisation
from the token — never from client-supplied input. A user belongs to exactly one
organisation per token (see the multi-tenancy decision in
[DecisionLog.md](DecisionLog.md)); multi-organisation login is future SaaS work (see
[FutureIdeas.md](FutureIdeas.md)).

Full design reasoning (password hashing, token claims, the logout/revocation
strategy, the bootstrap admin mechanism) is recorded in
[DecisionLog.md](DecisionLog.md#2026-07-25-authentication-password-hashing-and-token-revocation-strategy)
and the
[Milestone 1 plan](../.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#1-authentication).

### `POST /api/v1/auth/login`

Request:
```json
{ "email": "user@example.com", "password": "..." }
```

Response `200`:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": "...", "organisation_id": "...", "email": "...",
    "full_name": "...", "role": "admin", "is_active": true
  }
}
```

Response `401` for wrong password, unknown email, or an inactive user — always the
same body (`{"detail": "Incorrect email or password"}`), so the response never
reveals which of the three occurred.

### `POST /api/v1/auth/logout`

Requires `Authorization: Bearer <token>`. Increments the calling user's
`token_version`, immediately invalidating every access token issued to that user so
far (all sessions, not just the current one — see the DecisionLog entry for the
trade-off). Response `204`.

### `GET /api/v1/auth/me`

Requires `Authorization: Bearer <token>`. Returns the authenticated user's own
profile (same shape as the `user` object in the login response). `401` if the token
is missing, invalid, expired, revoked, or the user is inactive.

## User management (Milestone 1)

Under `/api/v1/users`, all requiring `Authorization: Bearer <token>` for an **admin**
role — every operation here is admin-only, including listing. Non-admin callers get
`403`. Full design in
[the Milestone 1 plan](../.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#2-user-management).

### `POST /api/v1/users`

Create a user in the admin's own organisation.

Request: `{ "email": "...", "full_name": "...", "password": "...", "role": "member" }`
(`role` defaults to `"member"`). Response `201` with the same user shape as
`GET /api/v1/auth/me`. `409` if the email already exists in this organisation.

### `GET /api/v1/users`

Paginated list (`?limit=&offset=`, per [pagination](#pagination)) of users in the
admin's own organisation only — never another organisation's users.

### `PATCH /api/v1/users/{id}`

Partial update: any of `full_name`, `role`, `is_active`. `404` if `id` doesn't exist
in the admin's own organisation (never reveals whether it exists elsewhere). `409` if
the update would let an admin deactivate or demote themselves, or would leave the
organisation with zero active admins — see the Milestone 1 plan's
[user management section](../.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#2-user-management)
for why these guards exist.

## People module (Milestone 1)

Under `/api/v1/people` and `/api/v1/companies`, both requiring
`Authorization: Bearer <token>` for any **active user** in the organisation — People
is a shared directory, not an admin-only function (unlike user management above).
Full design in
[the Milestone 1 plan](../.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#3-people-module)
and [docs/modules/People.md](modules/People.md).

### `POST /api/v1/companies` / `PATCH /api/v1/companies/{id}`

Request: `{ "name": "...", "type": "customer"|"supplier"|"other", "address": "...",
"phone": "...", "general_email": "...", "notes": "..." }` (`type` defaults to
`"other"`; only `name` is required). Response `201`/`200` with the company, including
`created_by_id`/`updated_by_id` set from the authenticated caller.

### `GET /api/v1/companies` / `GET /api/v1/companies/{id}`

Paginated list (per [pagination](#pagination)) or single fetch, scoped to the
caller's own organisation. `404` for another organisation's `id`.

### `DELETE /api/v1/companies/{id}`

`204` on success. `404` if not in the caller's organisation. `409` if any `people`
row still references it — the caller must reassign or delete those contacts first.

### `GET /api/v1/companies/{id}/people`

Paginated list of contacts (`people` rows) for one company. `404` if the company
isn't in the caller's own organisation.

### `POST /api/v1/people` / `PATCH /api/v1/people/{id}`

Request: `{ "company_id": "..."|null, "first_name": "...", "last_name": "...",
"email": "...", "phone": "...", "role": "...", "department": "...", "notes": "...",
"is_employee": true|false }`. `422` if `is_employee` and `company_id` are
contradictory (an employee cannot have a `company_id`; a contact must have one).
`404` if `company_id` is set but doesn't exist in the caller's own organisation.
Response includes `created_by_id`/`updated_by_id`.

### `GET /api/v1/people` / `GET /api/v1/people/{id}`

Paginated list or single fetch, scoped to the caller's own organisation. `404` for
another organisation's `id`. List supports `?company_id=`, `?is_employee=`,
`?department=` exact filters and `?search=` (case-insensitive substring match across
`first_name`/`last_name`/`email`/`role`).

### `DELETE /api/v1/people/{id}`

`204` on success (hard delete — see
[Database.md](Database.md#soft-delete-and-audit-trail)). `404` if not in the caller's
own organisation.

## Document Management (Milestone 2, in progress)

Under `/api/v1/document-categories`, `/api/v1/document-tags`, and
`/api/v1/documents`, all requiring `Authorization: Bearer <token>`. Per the
Milestone 2 plan's
["Permissions summary"](../.hermes/plans/2026-07-26-milestone-2-document-management.md#6-permissions-summary):
listing/viewing and document create/edit are open to any active user;
category/tag mutation and document deletion are admin-only. Version upload/download/
preview and the approval/acknowledgement workflow are not implemented yet — this
section covers only the core schema slice built so far.

### `POST /api/v1/document-categories` / `PATCH /api/v1/document-categories/{id}` — **admin only**

Request: `{ "name": "...", "parent_category_id": "..."|null }`. `404` if
`parent_category_id` is set but not in the caller's own organisation.

### `GET /api/v1/document-categories` / `GET /api/v1/document-categories/{id}`

Paginated list or single fetch (any active user), scoped to the caller's own
organisation. `404` for another organisation's `id`.

### `DELETE /api/v1/document-categories/{id}` — **admin only**

`204` on success. `409` if the category still has child categories or is referenced
by a (non-deleted) document.

### `POST /api/v1/document-tags` — **admin only**

Request: `{ "name": "..." }`. `409` if a tag with that name already exists in the
organisation.

### `GET /api/v1/document-tags?search=`

Paginated, optionally name-substring-filtered list (any active user).

### `DELETE /api/v1/document-tags/{id}` — **admin only**

`204` on success. Cascades: removes the tag from every document that referenced it
(tags are lightweight free-form labels, not referential-integrity-critical like
categories — no "still in use" guard).

### `POST /api/v1/documents` / `PATCH /api/v1/documents/{id}`

Request: `{ "title": "...", "category_id": "..."|null, "owner_id": "..."|null,
"tag_ids": ["..."] }`. `number` is never client-supplied — always generated
server-side from the organisation's `document_numbering_scheme` configuration row
(default `DOC-0001`, `DOC-0002`, ...; see
[Database.md](Database.md#documents-and-related-tables-milestone-2)). `404` if
`category_id`, `owner_id` (validated against the People module), or any `tag_ids`
entry doesn't exist in the caller's own organisation. Response `201`/`200` includes
`status` (`draft` initially), `current_version_id` (`null` until a version is
approved — not yet reachable in this slice), and the resolved `tags` array.

### `GET /api/v1/documents` / `GET /api/v1/documents/{id}`

Paginated list or single fetch, scoped to the caller's own organisation, excluding
soft-deleted documents. `404` for another organisation's `id` or a soft-deleted
document. List supports `?category_id=`, `?status=`, `?owner_id=` exact filters,
`?search=` (case-insensitive substring match across `title`/`number`), and `?tag=`
(exact tag name, joined through `document_tag_links`/`document_tags`, scoped to the
caller's own organisation) — all combinable.

### `DELETE /api/v1/documents/{id}` — **admin only**

`204` on success. Soft delete (`deleted_at`) — the row and any version files are
retained, never hard-deleted, per
[Database.md](Database.md#soft-delete-and-audit-trail).

### `GET /api/v1/documents/{id}/versions`

Paginated list of a document's versions (any active user), newest first. `404` if the
document doesn't exist in the caller's own organisation.

### `POST /api/v1/documents/{id}/versions`

Upload a new, immutable version (any active user — not admin-only; the approval
workflow, not this endpoint, is the QMS control gate). `multipart/form-data`: `file`
(required), `change_summary` (optional text field). `version_number` is assigned
sequentially per document, server-side. Full security posture — server-generated
storage names, extension + magic-byte + streamed-size validation, a request-body
size cap ahead of any parsing — in
[the Milestone 2 plan](../.hermes/plans/2026-07-26-milestone-2-document-management.md#4-storage-and-uploaddownloadpreview-security)
and
[DecisionLog.md](DecisionLog.md#2026-07-26-document-upload-request-body-size-cap-version-number-locking-and-upload-policy-extension-validation).
`404` if the document doesn't exist in the caller's own organisation. `422` if the
file's extension isn't in the organisation's configured allow-list, or its content
doesn't match its extension's expected signature. `413` if it exceeds the
organisation's configured `max_size_mb` (checked while streaming) or the global
`MAX_REQUEST_BODY_MB` request-body cap (checked before the body is read).

### `GET /api/v1/documents/{id}/versions/{version_id}/download`

Streams the version's file as `Content-Disposition: attachment` (any active user).
`404` if the document or version doesn't exist in the caller's own organisation —
resolved only via `(document_id, version_id)` scoped to the caller's organisation,
never a raw path or `storage_key` (never present in any response body).

### `GET /api/v1/documents/{id}/versions/{version_id}/preview`

Streams the version's file `inline` (any active user) for previewable content types
only (`application/pdf`, `image/png`, `image/jpeg`, as determined server-side from
the validated upload extension — never the client's declared `Content-Type`). `415`
for any other content type, with a message pointing at `download` instead. Same
`404` scoping as download.

### `POST /api/v1/documents/{id}/versions/{version_id}/submit-for-approval`

Any active user. `draft` → `in_review`. `404` if the document/version doesn't
exist in the caller's own organisation. `409` if the version isn't currently
`draft`.

### `POST /api/v1/documents/{id}/versions/{version_id}/approve` — **admin only**

Request: `{ "comments": "..."|null }`. `in_review` → `approved`; supersedes the
document's previous current version (→ `obsolete`);
`documents.current_version_id`/`status` updated; records a `document_approvals`
row (`approver_id` from the authenticated caller, never client-supplied). `404` if
the document/version doesn't exist in the caller's own organisation. `409` if the
version isn't currently `in_review`. Approving a version of a previously-retired
(`obsolete`) document is allowed — treated as a deliberate admin decision to
revive it.

### `POST /api/v1/documents/{id}/versions/{version_id}/reject` — **admin only**

Request: `{ "comments": "..." }` (required — `422` if blank). `in_review` →
`rejected` (terminal for that version; a new version must be created to try
again); records a `document_approvals` row. Same `404`/`409` scoping as approve.
Never changes a retired document's status back to `draft`/`in_review`.

### `POST /api/v1/documents/{id}/obsolete` — **admin only**

Retires the whole document (`documents.status` → `obsolete`), independent of its
versions' own statuses. `404` if the document doesn't exist in the caller's own
organisation.

### `POST /api/v1/documents/{id}/versions/{version_id}/acknowledge`

Any active user. Records that the caller ("I have read and understood this
document") has acknowledged this version. `acknowledged_by_id` is always
`current_user.id` — the request body is empty; there is no field a client could
use to acknowledge on someone else's behalf. Idempotent: acknowledging the same
version twice returns the original record (`200`), not an error. `404` if the
document/version doesn't exist in the caller's own organisation.

### `GET /api/v1/documents/{id}/versions/{version_id}/acknowledgements`

Paginated list of who has acknowledged this version, and when (any active user —
informational visibility, matching this module's shared-directory trust model).
Same `404` scoping as acknowledge.

### `GET /api/v1/documents/{id}/versions/{a}/compare/{b}`

Any active user. A practical comparison: version-level metadata for both versions
always; additionally a unified line diff (`text_diff`, one line per array entry)
when both versions have a text-based content type (`text/plain`/`text/csv`) **and**
both are at or under a 5 MB diff-size cap — above that, or for any other content
type (PDF, Office formats, images), `text_diff` is `null` and only
`checksum_changed` (whether the file content differs) is reported; no structured
PDF/Office diffing. `404` if either version doesn't exist in the caller's own
organisation, or doesn't belong to document `{id}` specifically (a version from a
different document in the same organisation also `404`s, not just a different
organisation's). `500` (logged server-side, generic message to the client) if a
version's file is unexpectedly missing from storage.

## Health and readiness endpoints (Milestone 0)

These are the only endpoints Milestone 0 implements:

### `GET /api/v1/health`

Liveness probe. Does not touch the database. Always returns quickly.

Response `200`:
```json
{ "status": "ok" }
```

### `GET /api/v1/health/ready`

Readiness probe. Executes a trivial query (`SELECT 1`) against the database to
confirm connectivity.

Response `200` (ready):
```json
{ "status": "ready", "database": "ok" }
```

Response `503` (database unreachable):
```json
{ "status": "not_ready", "database": "error" }
```

## Module endpoint prefixes

`/api/v1/auth`, `/api/v1/users`, `/api/v1/people`, `/api/v1/companies`,
`/api/v1/document-categories`, `/api/v1/document-tags`, and `/api/v1/documents` are
implemented (see "Authentication", "User management", "People module", and "Document
Management" above). The rest are reserved prefixes for future modules, so routing
collisions are avoided as modules land per the [Roadmap](Roadmap.md). Each will get
full documentation in its `docs/modules/<Module>.md` "Planned APIs" section as it is
implemented:

| Prefix | Module |
|---|---|
| `/api/v1/auth` | Authentication (Milestone 1) — implemented |
| `/api/v1/users` | User management (Milestone 1) — implemented |
| `/api/v1/people`, `/api/v1/companies` | People (Milestone 1) — implemented |
| `/api/v1/documents`, `/api/v1/document-categories`, `/api/v1/document-tags` | Document Management (Milestone 2) — in progress |
| `/api/v1/products` | Products |
| `/api/v1/suppliers` | Suppliers |
| `/api/v1/ncr` | NCR |
| `/api/v1/calibration` | Calibration and Asset Management |
| `/api/v1/maintenance` | Maintenance |
| `/api/v1/fair` | FAIR |
| `/api/v1/spc` | SPC |
| `/api/v1/hse/guidance` | Health and Safety: Government Guidance |
| `/api/v1/hse/audits` | Health and Safety: Audits |
| `/api/v1/hse/incidents` | Health and Safety: Incident Reporting |
| `/api/v1/hse/risk-assessments` | Health and Safety: Risk Assessments |

## Related documents

- [Architecture.md](Architecture.md) — layered backend and module boundaries.
- [Database.md](Database.md) — how these endpoints read/write data.
- [docs/modules/](modules/) — per-module planned API details.

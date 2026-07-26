# Document Management

**Status: In Progress.** [Milestone 2](../Roadmap.md#m2-document-management) is
underway — see [docs/CurrentStatus.md](../CurrentStatus.md) and the
[Milestone 2 plan](../../.hermes/plans/2026-07-26-milestone-2-document-management.md)
for exactly what is and isn't implemented yet. Implemented so far: categories, tags,
documents (metadata CRUD, soft delete), configurable server-generated numbering,
secure version file upload/download/preview, the approval/rejection workflow, and
electronic acknowledgement. Not yet implemented: search/filtering, version
comparison, and the frontend.

## Purpose

Core QMS document control: SOPs, work instructions, forms, policies and other
controlled documents, with revision history, approval workflow, change history,
permissions, electronic acknowledgement, search, categories, tags, PDF preview,
version comparison and configurable numbering, per
[ProductSpecification.md](../ProductSpecification.md#document-management). Future:
electronic signatures and ISO compliance assistance (see
[FutureIdeas.md](../FutureIdeas.md)).

## Database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).
Full column detail: [Database.md](../Database.md#documents-and-related-tables-milestone-2).

- **`document_categories`** — implemented. `id`, `organisation_id`, `name`,
  `parent_category_id` (nullable, self-referencing, for a category tree).
- **`document_tags`** / **`document_tag_links`** — implemented. Free-form tagging,
  many-to-many.
- **`documents`** — implemented. `id`, `organisation_id`, `category_id`, `number`
  (generated from a configurable numbering scheme via the `configuration` table
  pattern — see [Database.md](../Database.md#configuration-table)), `title`,
  `current_version_id`, `status` (`draft` / `in_review` / `approved` / `obsolete`),
  `owner_id` → `people`, `deleted_at` (soft delete), `created_at`, `updated_at`.
- **`document_versions`** — implemented, including secure upload/download/preview.
  `id`, `document_id`, `version_number` (allocated under a row lock, safe under
  concurrent uploads), `storage_key` (server-generated, never exposed over the
  API), `original_filename` (sanitised at upload time), `content_type` (derived
  server-side from the validated extension, never the client's declared
  `Content-Type`), `size_bytes`, `checksum_sha256`, `change_summary`,
  `created_by_id` → `users`, `created_at`, `status`. Full history retained;
  `documents.current_version_id` will point at the latest approved version once
  the approval workflow lands.
- **`document_approvals`** — implemented. `id`, `document_version_id`,
  `approver_id` → **`users`** (not `people` — see
  [DecisionLog.md](../DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table)),
  `decision` (`approved` / `rejected`), `decided_at`, `comments` (required by the
  service layer when rejecting). Immutable after creation.
- **`document_acknowledgements`** — implemented. `id`, `document_version_id`,
  `acknowledged_by_id` → **`users`**, `acknowledged_at`. Unique per
  (`document_version_id`, `acknowledged_by_id`) — re-acknowledging is idempotent.
  Immutable after creation.

## APIs

Implemented so far, under `/api/v1/document-categories`, `/api/v1/document-tags`,
and `/api/v1/documents` — full detail:
[API.md](../API.md#document-management-milestone-2-in-progress):

- `GET/POST /api/v1/document-categories`, `GET/PATCH/DELETE /api/v1/document-categories/{id}` —
  admin-only mutation, any-active-user read.
- `GET/POST /api/v1/document-tags`, `DELETE /api/v1/document-tags/{id}` — admin-only
  mutation, any-active-user read; delete cascades (unlinks), no "in use" guard.
- `GET/POST /api/v1/documents`, `GET/PATCH /api/v1/documents/{id}` (any active user),
  `DELETE /api/v1/documents/{id}` (admin-only, soft delete) — filterable by
  `category_id`, `status`, `owner_id` today; `search`/`tag` planned for a later slice.
- `GET/POST /api/v1/documents/{id}/versions` — list (any active user) / upload a new
  version (any active user, multipart `file` + optional `change_summary`).
- `GET /api/v1/documents/{id}/versions/{version_id}/download` /
  `.../preview` — secure file download (`attachment`) / inline preview
  (PDF/PNG/JPEG only, `415` otherwise). Both any active user.
- `POST /api/v1/documents/{id}/versions/{version_id}/submit-for-approval` — any
  active user, `draft` → `in_review`.
- `POST .../approve` / `POST .../reject` — **admin only**; `in_review` →
  `approved`/`rejected`; reject requires a non-blank `comments` field.
- `POST /api/v1/documents/{id}/obsolete` — **admin only**; retires the whole
  document regardless of version state.
- `POST /api/v1/documents/{id}/versions/{version_id}/acknowledge` — any active
  user, self-only, idempotent.
- `GET /api/v1/documents/{id}/versions/{version_id}/acknowledgements` — any
  active user; who has acknowledged, and when.

Not yet implemented (planned, per the
[Milestone 2 plan](../../.hermes/plans/2026-07-26-milestone-2-document-management.md)):

- `GET /api/v1/documents/{id}/versions/{a}/compare/{b}` — version comparison.
- `GET /api/v1/documents?search=&tag=` — full search across title, number, tags.

## Workflow

Draft → In Review → Approved (published, becomes `current_version_id`) → Obsolete
(superseded when a later version is approved). A document cannot be published without
at least one recorded approval; change history and prior versions are retained, never
overwritten, matching the spec's "revision history" and "change history" requirements.
`documents.status` is a service-maintained cache: it becomes and *stays* `approved`
the moment any version is ever approved, even while a later revision is separately
drafted/reviewed/rejected; `in_review`/`draft` only apply before that first approval
ever happens. Retiring a whole document (`obsolete`) is independent of version state
and, once set, is never silently reversed by an ordinary submit/reject action — only
a deliberate admin approval can revive a retired document. Every workflow mutation is
serialised per-document via a row lock, so two concurrent transitions on the same
document can't race into an inconsistent state — see
[DecisionLog.md](../DecisionLog.md#2026-07-26-document-approval-workflow-a-status-cache-integrity-bug-and-a-toctou-race)
for the bugs an independent review found and fixed here.

## Relationships to other modules

Per [ProductSpecification.md](../ProductSpecification.md#module-relationships),
"Documents link to all appropriate domain records" — Document Management is
referenced **from** other modules rather than referencing them:

- [Calibration and Asset Management](CalibrationAndAssetManagement.md) — calibration
  certificates are stored as documents.
- [Products](Products.md) — drawings, CAD files, and specifications are documents.
- [NCR](NCR.md) — attachments and exported reports.
- [FAIR](FAIR.md) — imported drawings and generated AS9102 forms.
- [Health and Safety: Audits](HealthAndSafetyAudits.md) — audit photos.
- A document's `owner_id` references [People](People.md) (an organisational
  assignment). Approvers and acknowledging staff reference `users` directly —
  they are actions performed by an authenticated caller, not a `people`
  assignment; see
  [DecisionLog.md](../DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table).

## Future improvements

- Electronic signatures (see [FutureIdeas.md](../FutureIdeas.md); legal/compliance
  research needed first, tracked in [TODO.md](../TODO.md)).
- ISO compliance assistance.
- Richer version-comparison (structured diff, not just side-by-side).

## Known issues / status

In progress. Categories, tags, documents (metadata), configurable numbering, secure
version upload/download/preview, the approval/rejection workflow, and electronic
acknowledgement are all implemented and tested (unit + integration against real
PostgreSQL). Independent security/tenant-isolation reviews were run for the upload,
workflow, and acknowledgement slices; the first two each found and fixed real issues
before being committed — a request-body size cap, a version-numbering race, and
upload-policy extension validation for the upload slice; a status-cache integrity
bug (a non-admin action could silently un-retire a document) and a related TOCTOU
race for the workflow slice. The acknowledgement slice's review found no issues. See
[DecisionLog.md](../DecisionLog.md#2026-07-26-document-upload-request-body-size-cap-version-number-locking-and-upload-policy-extension-validation)
and
[DecisionLog.md](../DecisionLog.md#2026-07-26-document-approval-workflow-a-status-cache-integrity-bug-and-a-toctou-race).
No UI exists yet. Search and version comparison are not implemented — see the
[Milestone 2 plan](../../.hermes/plans/2026-07-26-milestone-2-document-management.md)
for the remaining slices.

## Related documents

- [Roadmap.md](../Roadmap.md#m2-document-management)
- [Database.md](../Database.md#configuration-table)
- [API.md](../API.md)

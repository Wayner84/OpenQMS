# Document Management

**Status: In Progress.** [Milestone 2](../Roadmap.md#m2-document-management) is
underway — see [docs/CurrentStatus.md](../CurrentStatus.md) and the
[Milestone 2 plan](../../.hermes/plans/2026-07-26-milestone-2-document-management.md)
for exactly what is and isn't implemented yet. Implemented so far: categories, tags,
documents (metadata CRUD, soft delete), and configurable server-generated numbering.
Not yet implemented: version file upload/download/preview, the approval/rejection
workflow, acknowledgements, search/filtering, version comparison, and the frontend.

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
- **`document_versions`** — table implemented (schema only; no upload endpoint yet).
  `id`, `document_id`, `version_number`, `storage_key` (server-generated, never
  exposed over the API), `original_filename`, `content_type`, `size_bytes`,
  `checksum_sha256`, `change_summary`, `created_by_id` → `users`, `created_at`,
  `status`. Full history retained; `documents.current_version_id` will point at the
  latest approved version once upload/approval land.
- **`document_approvals`** — not yet implemented. Planned: `id`,
  `document_version_id`, `approver_id` → **`users`** (not `people` — see
  [DecisionLog.md](../DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table)),
  `decision` (`approved` / `rejected`), `decided_at`, `comments`.
- **`document_acknowledgements`** — not yet implemented. Planned: `id`,
  `document_version_id`, `acknowledged_by_id` → **`users`**, `acknowledged_at`.

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
- `GET /api/v1/documents/{id}/versions` — always empty in this slice.

Not yet implemented (planned, per the
[Milestone 2 plan](../../.hermes/plans/2026-07-26-milestone-2-document-management.md)):

- `POST /api/v1/documents/{id}/versions` — upload a new version (draft).
- `POST /api/v1/documents/{id}/versions/{version_id}/submit-for-approval`,
  `POST .../approve`, `POST .../reject` — approval workflow transitions.
- `GET /api/v1/documents/{id}/versions/{a}/compare/{b}` — version comparison.
- `POST /api/v1/documents/{id}/versions/{version_id}/acknowledge` — record an
  acknowledgement for the current user.
- `GET /api/v1/documents/{id}/versions/{version_id}/download` /
  `.../preview` — secure file download / PDF/image inline preview.
- `GET /api/v1/documents?search=&tag=` — full search across title, number, tags.

## Workflow

Draft → In Review → Approved (published, becomes `current_version_id`) → Obsolete
(superseded when a later version is approved). A document cannot be published without
at least one recorded approval; change history and prior versions are retained, never
overwritten, matching the spec's "revision history" and "change history" requirements.

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
- Approvers and acknowledging staff reference [People](People.md).

## Future improvements

- Electronic signatures (see [FutureIdeas.md](../FutureIdeas.md); legal/compliance
  research needed first, tracked in [TODO.md](../TODO.md)).
- ISO compliance assistance.
- Richer version-comparison (structured diff, not just side-by-side).

## Known issues / status

In progress. Categories, tags, documents (metadata), and configurable numbering are
implemented and tested (unit + integration against real PostgreSQL, migration
verified with a real upgrade → downgrade → upgrade cycle). No UI exists yet. Version
upload/download/preview, the approval/rejection workflow, acknowledgements, search,
and version comparison are not implemented — see the
[Milestone 2 plan](../../.hermes/plans/2026-07-26-milestone-2-document-management.md)
for the remaining slices.

## Related documents

- [Roadmap.md](../Roadmap.md#m2-document-management)
- [Database.md](../Database.md#configuration-table)
- [API.md](../API.md)

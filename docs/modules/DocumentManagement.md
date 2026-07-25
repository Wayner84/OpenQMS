# Document Management

**Status: Planned.** Not yet implemented — targeted for
[Milestone 2](../Roadmap.md#m2-document-management). No code exists for this module
yet; see [docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

Core QMS document control: SOPs, work instructions, forms, policies and other
controlled documents, with revision history, approval workflow, change history,
permissions, electronic acknowledgement, search, categories, tags, PDF preview,
version comparison and configurable numbering, per
[ProductSpecification.md](../ProductSpecification.md#document-management). Future:
electronic signatures and ISO compliance assistance (see
[FutureIdeas.md](../FutureIdeas.md)).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`document_categories`** — `id`, `organisation_id`, `name`, `parent_category_id`
  (nullable, self-referencing, for a category tree).
- **`documents`** — `id`, `organisation_id`, `category_id`, `number` (generated from
  a configurable numbering scheme via the `configuration` table pattern — see
  [Database.md](../Database.md#configuration-table)), `title`, `current_version_id`,
  `status` (`draft` / `in_review` / `approved` / `obsolete`), `owner_id` → `people`,
  `created_at`, `updated_at`.
- **`document_versions`** — `id`, `document_id`, `version_label`, `file_path`,
  `change_summary`, `created_by_id` → `people`, `created_at`, `status`. Full history
  retained; `documents.current_version_id` points at the latest approved version.
- **`document_tags`** / **`document_tag_links`** — free-form tagging, many-to-many.
- **`document_approvals`** — `id`, `document_version_id`, `approver_id` → `people`,
  `decision` (`approved` / `rejected`), `decided_at`, `comments`.
- **`document_acknowledgements`** — `id`, `document_version_id`, `person_id` →
  `people`, `acknowledged_at` — electronic acknowledgement records.

## Planned APIs

Under `/api/v1/documents`:

- `GET/POST /api/v1/documents`, `GET/PATCH/DELETE /api/v1/documents/{id}` — CRUD,
  filterable by category, tag, status, owner.
- `POST /api/v1/documents/{id}/versions` — upload a new version (draft).
- `POST /api/v1/documents/{id}/versions/{version_id}/submit-for-approval`,
  `POST .../approve`, `POST .../reject` — approval workflow transitions.
- `GET /api/v1/documents/{id}/versions/{a}/compare/{b}` — version comparison.
- `POST /api/v1/documents/{id}/versions/{version_id}/acknowledge` — record an
  acknowledgement for the current user.
- `GET /api/v1/documents/{id}/versions/{version_id}/preview` — PDF preview.
- `GET /api/v1/documents?search=` — search across title, number, tags.

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

Planned only; no schema, API, or UI exists yet. Numbering scheme design depends on
the `configuration` table baseline established in
[Milestone 0](../../.hermes/plans/2026-07-25-milestone-0-foundation.md).

## Related documents

- [Roadmap.md](../Roadmap.md#m2-document-management)
- [Database.md](../Database.md#configuration-table)
- [API.md](../API.md)

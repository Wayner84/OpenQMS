# FAIR

**Status: Planned.** Not yet implemented — targeted for
[Milestone 7](../Roadmap.md#m7-fair). No code exists for this module yet; see
[docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

AS9102 First Article Inspection Reports: import PDF/image drawings, apply a grid,
recognise dimensions, automatically number balloons, store characteristics (nominal,
tolerance, measured value, result), and generate AS9102 forms, aiming for useful
commercial-tool capability with a clean UI, per
[ProductSpecification.md](../ProductSpecification.md#fair).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`fair_reports`** — `id`, `organisation_id`, `product_id` →
  [Products](Products.md), `revision`, `status` (`draft` / `complete`),
  `created_by_id` → [People](People.md), `created_at`, `updated_at`.
- **`fair_drawings`** — `id`, `fair_report_id`, `source_document_id` →
  [Document Management](DocumentManagement.md) (the imported PDF/image), `grid_config`
  (JSONB — grid dimensions/offsets applied for ballooning).
- **`fair_characteristics`** — `id`, `fair_report_id`, `balloon_number`,
  `characteristic_description`, `nominal_value`, `tolerance_plus`,
  `tolerance_minus`, `measured_value`, `result` (`pass` / `fail`),
  `measurement_method`.
- AS9102 Forms 1/2/3 are treated as **generated output** (rendered from
  `fair_reports`/`fair_characteristics` and stored back as a
  [Document Management](DocumentManagement.md) record), not a separately persisted
  table — this avoids a second source of truth for data already captured above.

## Planned APIs

Under `/api/v1/fair`:

- `GET/POST /api/v1/fair`, `GET/PATCH/DELETE /api/v1/fair/{id}` — CRUD, filterable
  by product, status.
- `POST /api/v1/fair/{id}/drawings` — import a drawing (PDF/image) and configure its
  grid.
- `GET/POST /api/v1/fair/{id}/characteristics` — manage characteristics/balloons.
- `POST /api/v1/fair/{id}/generate` — generate the AS9102 Form 1/2/3 PDF output.

## Workflow

Create a FAIR report for a product revision → import a drawing → apply a grid →
balloon characteristics (auto-numbered where dimension recognition succeeds, manual
fallback otherwise) → enter nominal/tolerance/measured values per characteristic →
generate AS9102 forms as a polished PDF.

## Relationships to other modules

- References [Products](Products.md) (the part/revision under first article
  inspection).
- Imported drawings and generated forms are [Document Management](DocumentManagement.md)
  records.
- Measured values may feed [SPC](SPC.md) studies once both modules exist (exact
  integration to be designed at implementation time — not built now).

## Future improvements

- Automatic dimension recognition/OCR from imported drawings (open research
  question — see [TODO.md](../TODO.md#research-required)).
- Automatic CMM data import for measured values (shared future item with
  [SPC](SPC.md) — see [FutureIdeas.md](../FutureIdeas.md)).

## Known issues / status

Planned only; no schema, API, or UI exists yet. The automatic dimension-recognition
approach (grid/ballooning from a raw PDF/image) is an unresolved research question
tracked in [TODO.md](../TODO.md#research-required) and should be resolved with a
research spike before implementation begins, likely landing manual/assisted
ballooning first and automatic recognition as a later improvement within this same
milestone.

## Related documents

- [Roadmap.md](../Roadmap.md#m7-fair)
- [Products.md](Products.md)
- [SPC.md](SPC.md)

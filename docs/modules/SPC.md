# SPC

**Status: Planned.** Not yet implemented — targeted for
[Milestone 8](../Roadmap.md#m8-spc). No code exists for this module yet; see
[docs/CurrentStatus.md](../CurrentStatus.md). This is one of the two "major modules"
named in the spec (with [NCR](NCR.md)).

## Purpose

Import CSV measurements and calculate Cp, Cpk, Pp, Ppk and sigma. Provide
histograms, Xbar-R, Individuals/Moving Range charts, control charts, trends and
report export. Keep it simple for daily use but powerful enough to replace Minitab
for routine SPC. Document future automatic CMM imports, per
[ProductSpecification.md](../ProductSpecification.md#spc).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`spc_studies`** — `id`, `organisation_id`, `product_id` →
  [Products](Products.md), `characteristic_name`, `subgroup_size`,
  `created_by_id` → [People](People.md), `created_at`, `updated_at`.
- **`spc_measurements`** — `id`, `spc_study_id`, `subgroup_index`, `value`,
  `measured_at`, `source` (`manual` / `csv_import` / reserved `cmm_import` for the
  future). Bulk-inserted from CSV import.
- **`spc_control_limits`** — `id`, `spc_study_id`, `limit_type` (`xbar_r` / `i_mr`),
  `ucl`, `lcl`, `centerline`, `calculated_at` — recalculated as new measurements are
  added.

## Planned APIs

Under `/api/v1/spc`:

- `GET/POST /api/v1/spc/studies`, `GET/PATCH/DELETE /api/v1/spc/studies/{id}` —
  CRUD, filterable by product.
- `POST /api/v1/spc/studies/{id}/import` — CSV measurement upload.
- `POST /api/v1/spc/studies/{id}/measurements` — manual single-measurement entry.
- `GET /api/v1/spc/studies/{id}/statistics` — Cp, Cpk, Pp, Ppk, sigma.
- `GET /api/v1/spc/studies/{id}/charts?type=histogram|xbar_r|i_mr|control` — chart
  data for rendering.
- `GET /api/v1/spc/studies/{id}/export` — report export.

## Workflow

Create a study for a product characteristic → import measurements (CSV today; manual
entry always available; CMM import reserved for the future) → statistics and control
limits are calculated → histograms, Xbar-R/I-MR and control charts are rendered from
the same underlying `spc_measurements` data → out-of-control trends are flagged →
export a report.

## Relationships to other modules

- References [Products](Products.md) (the part/characteristic being studied).
- Future integration point with [FAIR](FAIR.md) measured values (not built now).

## Future improvements

- Automatic CMM data imports — explicitly named as future scope in the product
  specification (see [FutureIdeas.md](../FutureIdeas.md)); the import format survey
  needed first is tracked in [TODO.md](../TODO.md#research-required).
- Real-time SPC from connected/networked gauges.

## Known issues / status

Planned only; no schema, API, or UI exists yet. As one of the two explicitly "major"
modules, implementation is expected to be split across several commits/batches per
[Contributing.md](../Contributing.md#branching-and-commits). CMM import format survey
should conclude before automatic CMM import is attempted (see
[TODO.md](../TODO.md#research-required)).

## Related documents

- [Roadmap.md](../Roadmap.md#m8-spc)
- [Products.md](Products.md)
- [FAIR.md](FAIR.md)

# NCR

**Status: Planned.** Not yet implemented — targeted for
[Milestone 4](../Roadmap.md#m4-ncr). No code exists for this module yet; see
[docs/CurrentStatus.md](../CurrentStatus.md). This is one of the two "major modules"
named in the spec (with [SPC](SPC.md)) and is expected to span multiple
implementation batches.

## Purpose

Internal and supplier non-conformance reporting with configurable prefixes (defaults
`NCR` and `SNCR`), the Open → Investigate → Containment → Corrective Action →
Verification → Close workflow, 5 Why/Fishbone/Ishikawa/8D/10D tools, attachments,
actions, owners, due dates and completion tracking. An NCR cannot close while actions
are open. Export incomplete NCRs with blank printable sections and completed NCRs as
polished PDF reports, per
[ProductSpecification.md](../ProductSpecification.md#ncr).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`ncrs`** — `id`, `organisation_id`, `number` (generated via the configurable
  numbering scheme — default prefix `NCR` or `SNCR` depending on `type`, stored in
  the `configuration` table per [Database.md](../Database.md#configuration-table)),
  `type` (`internal` / `supplier`), `product_id` (nullable → [Products](Products.md)),
  `supplier_id` (nullable → [Suppliers](Suppliers.md)), `status` (`open` /
  `investigate` / `containment` / `corrective_action` / `verification` / `closed`),
  `raised_by_id` → [People](People.md), `description`, `root_cause_summary`,
  `created_at`, `updated_at`, `closed_at`.
- **`ncr_actions`** — `id`, `ncr_id`, `description`, `owner_id` → `people`,
  `due_date`, `status` (`open` / `complete`), `completed_at`. The close-blocking rule
  ("an NCR cannot close while actions are open") is enforced in the service layer
  against this table.
- **`ncr_investigation_tools`** — `id`, `ncr_id`, `tool_type` (`five_why` /
  `fishbone` / `8d` / `10d`), `data` (JSONB — each tool's structure differs enough
  that a flexible column is preferred over one table per tool type).
- **`ncr_attachments`** — `id`, `ncr_id`, `document_id` →
  [Document Management](DocumentManagement.md), `description`.
- **`ncr_status_history`** — `id`, `ncr_id`, `from_status`, `to_status`,
  `changed_by_id` → `people`, `changed_at`, `comments` — full audit trail of the
  workflow.

## Planned APIs

Under `/api/v1/ncr`:

- `GET/POST /api/v1/ncr`, `GET/PATCH/DELETE /api/v1/ncr/{id}` — CRUD, filterable by
  type, status, product, supplier, owner.
- `POST /api/v1/ncr/{id}/transition` — move to the next workflow status; rejects the
  transition to `closed` with a `409` if any `ncr_actions` row for the NCR is still
  `open`.
- `GET/POST /api/v1/ncr/{id}/actions`, `PATCH /api/v1/ncr/actions/{id}` — manage
  actions.
- `GET/PUT /api/v1/ncr/{id}/tools/{tool_type}` — read/update a structured
  investigation tool's data.
- `GET/POST /api/v1/ncr/{id}/attachments` — manage attachments.
- `GET /api/v1/ncr/{id}/export?format=pdf` — export; an incomplete NCR exports with
  blank printable sections for the unfinished parts, a closed NCR exports as a
  polished, fully-populated PDF report.

## Workflow

Open → Investigate → Containment → Corrective Action → Verification → Close, one
directional status machine enforced server-side (no skipping stages), with every
transition recorded in `ncr_status_history`. Investigation tools (5 Why, Fishbone,
8D, 10D) are optional structured aids attached during the Investigate/Corrective
Action stages, not mandatory gates. Closing is blocked while any linked action is
open, per the spec's explicit rule.

## Relationships to other modules

- References [Products](Products.md) and [Suppliers](Suppliers.md) (for
  `type: supplier` NCRs — "Suppliers link to NCR" per the spec).
- Owners/raisers are [People](People.md).
- Attachments and the exported report are [Document Management](DocumentManagement.md)
  records (or generated documents stored the same way).
- Surfaced read-only on the [Suppliers](Suppliers.md) module's `ncr-history`
  endpoint.

## Future improvements

- NCR trend analytics/dashboards.
- Automatic supplier notification emails on supplier-NCR creation.
- AI-assisted root cause suggestions from historical NCR data (see
  [FutureIdeas.md](../FutureIdeas.md) — speculative, not scheduled).

## Known issues / status

Planned only; no schema, API, or UI exists yet. As the largest single module in the
roadmap, implementation is expected to be split across several commits/batches per
[Contributing.md](../Contributing.md#branching-and-commits) rather than one large
change. Depends on [People](People.md), [Products](Products.md),
[Suppliers](Suppliers.md) and [Document Management](DocumentManagement.md) existing
first (see [Roadmap.md](../Roadmap.md)).

## Related documents

- [Roadmap.md](../Roadmap.md#m4-ncr)
- [TODO.md](../TODO.md#research-required) — shared risk-scoring research item.
- [DecisionLog.md](../DecisionLog.md)

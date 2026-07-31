# NCR

**Status: Implemented (schema/CRUD/workflow/actions/investigation
tools/attachments/supplier history/PDF export only).**
[Milestone 4](../Roadmap.md#m4-ncr) is in progress — full scope, schema, API, and
design decisions in the
[Milestone 4 plan](../../.hermes/plans/2026-07-29-milestone-4-ncr.md). NCR
creation, editing, listing, admin-only soft deletion, the full transition
workflow, containment/corrective/preventive actions with owners and due dates,
the four structured investigation tools, document attachments, the Suppliers
`ncr-history` read endpoint, and PDF export (`ncrs`, `ncr_status_history`,
`ncr_actions`, `ncr_investigation_tools`, `ncr_attachments`), including the
close-blocked-while-actions-open guard and the closed-NCR
actions/tools/attachments-frozen rule, are implemented and tested, backend
only; see [docs/CurrentStatus.md](../CurrentStatus.md) for exactly what is and
isn't done yet. The frontend is not yet implemented. This is one of the two
"major modules" named in the spec (with [SPC](SPC.md)) and is expected to span
multiple implementation batches.

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
  `changed_by_id` → `users.id` (a workflow transition is an action performed by an
  authenticated API caller, attributed to `current_user` — matching the same
  `document_approvals`/`document_acknowledgements` reasoning in
  [DecisionLog.md](../DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table);
  see the
  [Milestone 4 plan](../../.hermes/plans/2026-07-29-milestone-4-ncr.md#design-decisions-made-in-this-plan-refining-the-planned-module-doc)
  for the full reasoning), `changed_at`, `comments` — full audit trail of the
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
- `GET/POST /api/v1/ncr/{id}/attachments`,
  `DELETE /api/v1/ncr/{id}/attachments/{attachment_id}` — manage attachments;
  `document_id` is validated to exist and belong to the caller's organisation
  via the Document Management module's own service layer.
- `GET /api/v1/ncr/{id}/export?format=pdf` — export via `reportlab` (design
  decision 8); an incomplete NCR exports with a placeholder for each unfinished
  part (root cause summary, investigation tools, closed date), a closed NCR
  exports as a polished, fully-populated PDF report. `422` for any `format`
  other than `pdf`; `404` for a cross-organisation NCR `{id}`.

Under `/api/v1/suppliers`:

- `GET /api/v1/suppliers/{id}/ncr-history` — read-only, paginated list of the
  NCRs linked to that supplier (`type: supplier` NCRs with `supplier_id` set).

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

`ncrs`, `ncr_status_history`, `ncr_actions`, `ncr_investigation_tools`, and
`ncr_attachments` (creation, editing, listing, admin-only soft deletion, the
full one-directional transition workflow with concurrency-safe row-locking,
containment/corrective/preventive actions with owners/due dates, the
close-blocked-while-actions-open guard, the closed-NCR
actions/tools/attachments-frozen rule, the four structured investigation tools
with create-or-replace upsert semantics, and document attachments validated
against the Document Management module's own service layer) are implemented
and tested against real PostgreSQL. The Suppliers `GET
/{supplier_id}/ncr-history` read endpoint is also implemented, reusing
`ncr.service.list_ncrs` rather than querying `Ncr` directly, per the
module-isolation rule. PDF export (`GET /api/v1/ncr/{id}/export`) is
implemented via `reportlab` (design decision 8), resolving human-readable
labels for `raised_by`/action `owner` (People), `product` (Products),
`supplier`+company (Suppliers/People), and attachment `document` (Documents)
through each module's own `service.py`, never their models directly. An
independent security review found and this slice fixed, test-first, a real
gap: user-controlled free text (NCR description, root cause summary,
investigation-tool JSON values) was interpolated unescaped into
`reportlab.platypus.Paragraph`, which parses a constrained HTML-like markup —
ordinary text containing something it read as an unterminated tag would 500
the export, and a deliberately crafted `<a href=...>`/`<font>` value could
inject a working hyperlink or styling into an official QMS report. Fixed by
escaping all four user-controlled interpolations with
`xml.sax.saxutils.escape` before they reach `Paragraph`; see
[DecisionLog.md](../DecisionLog.md#2026-07-30-ncr-pdf-export-slice-unescaped-user-text-in-reportlab-paragraph-markup).
Not yet implemented: the frontend. As the largest single module in the
roadmap, implementation is split across several commits/batches per
[Contributing.md](../Contributing.md#branching-and-commits) rather than one
large change — see the
[Milestone 4 plan](../../.hermes/plans/2026-07-29-milestone-4-ncr.md)'s
suggested commit boundaries.

## Related documents

- [Roadmap.md](../Roadmap.md#m4-ncr)
- [Milestone 4 plan](../../.hermes/plans/2026-07-29-milestone-4-ncr.md) — full
  schema, API, and design decisions for this implementation.
- [TODO.md](../TODO.md#research-required) — shared risk-scoring research item.
- [DecisionLog.md](../DecisionLog.md)

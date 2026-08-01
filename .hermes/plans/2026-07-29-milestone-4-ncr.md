# Milestone 4 — NCR

**Status:** Planned — implementation starts after this plan and its doc updates are
committed.
**Date planned:** 2026-07-29

## Purpose

Build the first major workflow module: internal and supplier non-conformance
reports (NCRs), per [Roadmap.md](../../docs/Roadmap.md#m4-ncr),
[docs/modules/NCR.md](../../docs/modules/NCR.md), and TODO Task 17 in
[docs/TODO.md](../../docs/TODO.md): configurable prefixes, the Open → Investigate →
Containment → Corrective Action → Verification → Close workflow, 5 Why/Fishbone/8D/
10D investigation tools, attachments, actions with owners/due dates, and PDF export.
Chosen fifth per the Roadmap, immediately after its dependencies (People, Products,
Suppliers, Document Management) all exist.

Background reading: [Architecture.md](../../docs/Architecture.md),
[Database.md](../../docs/Database.md), [API.md](../../docs/API.md),
[CodingStandards.md](../../docs/CodingStandards.md),
[Contributing.md](../../docs/Contributing.md), and the completed
[Milestone 3 plan](2026-07-28-milestone-3-products-and-suppliers.md) for the
established conventions this milestone continues (organisation scoping via
`CurrentUser`, `created_by_id`/`updated_by_id` attribution, the pagination envelope,
`404`-not-`403` for cross-organisation lookups, cross-module validation through the
owning module's own `service.py` — never its `models.py` directly, row-locking for
TOCTOU-prone check-then-write sequences with an `IntegrityError` belt-and-braces
catch, `fetchAllPages` for frontend option lists, request-generation guards for
async state, `mountedRef`/`<StrictMode>` regression tests).

## Design decisions made in this plan (refining the "Planned" module doc)

1. **`ncr_status_history.changed_by_id` references `users.id`, not `people.id`,
   overriding the module doc's draft.** This is the exact shape of decision already
   made for Document Management
   ([DecisionLog.md](../../docs/DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table)):
   a workflow transition is an action performed by an authenticated API caller and
   must be attributed to the verified `current_user`, not an arbitrary `people` row
   a caller could claim to be. The module doc's other person-references —
   `ncrs.raised_by_id` and `ncr_actions.owner_id` — are organisational assignments
   (who identified the issue; who is responsible for fixing it) that can validly
   name someone without a login, matching `documents.owner_id`'s precedent, so they
   keep referencing `people.id`. `ncrs`/`ncr_actions`/`ncr_investigation_tools`/
   `ncr_attachments` all additionally carry `created_by_id`/`updated_by_id` →
   `users.id` for ordinary API-call attribution, matching every other module.
2. **Permissions: any active user for everyday NCR work, matching People/Products/
   Suppliers' precedent — except deleting an NCR itself, which is admin-only.**
   Raising, viewing, transitioning, managing actions/tools/attachments is
   collaborative quality work done by whoever is involved, not an admin-gated
   taxonomy like Document Management's categories/tags. Deleting an NCR is
   different: unlike Suppliers/Products (pure reference data, hard-deletable by any
   user), an NCR is an audit-significant quality record with a full status history,
   closer in shape to a Document Management record — so deletion is a soft delete
   (`ncrs.deleted_at`), admin-only, matching `documents`' existing precedent
   ([Database.md](../../docs/Database.md#soft-delete-and-audit-trail)).
3. **The workflow is a strict one-directional sequence; a transition request names
   the target status and is rejected unless it is exactly the next status in the
   fixed sequence** (`open` → `investigate` → `containment` → `corrective_action` →
   `verification` → `closed`), per the module doc's "no skipping stages" and the
   spec's explicit ordering. No "reject and reopen" step exists in the spec for
   NCR (unlike Document Management's approve/reject) — an NCR only ever moves
   forward; correcting a mistaken transition is a future improvement, not built
   speculatively now (see "Out of scope" below).
4. **Closing is blocked (`409`) while any linked `ncr_actions` row is still `open`**,
   per the spec's explicit rule, checked in the same locked transaction as the
   transition itself (mirroring Document Management's `_lock_document` pattern) so
   a concurrent "add an open action" and "close the NCR" cannot race past each
   other.
5. **`type: supplier` NCRs require `supplier_id`; `type: internal` NCRs must not set
   it.** Mirrors the People module's `is_employee`/`company_id` invariant, enforced
   at the Pydantic schema layer with a `422`
   ([DecisionLog.md](../../docs/DecisionLog.md#2026-07-26-people-module-is_employeecompany_id-invariant-enforced-at-the-schema-layer-not-a-db-constraint)),
   not a DB constraint. `product_id` is optional for either type (an NCR is not
   always about a specific product).
6. **Numbering: one `ncr_numbering_scheme` configuration row per organisation,
   holding both prefixes.** `{"internal": {"prefix": "NCR", "separator": "-",
   "padding": 4, "next_sequence": 1}, "supplier": {"prefix": "SNCR", "separator":
   "-", "padding": 4, "next_sequence": 1}}` — two independent sequences (an
   internal and a supplier NCR can validly share the same trailing number with
   different prefixes) in one row, read/incremented with the same
   `SELECT ... FOR UPDATE` pattern as `document_numbering_scheme`
   (`backend/app/modules/documents/numbering.py`), seeded by this milestone's first
   migration. `number` is never client-supplied.
7. **Investigation tools are one row per `(ncr_id, tool_type)`, upserted via
   `PUT`, with a fixed 4-value `tool_type` enum.** The module doc's `GET/PUT
   .../tools/{tool_type}` shape implies exactly one instance of each tool per NCR;
   a `UniqueConstraint(ncr_id, tool_type)` backs that, and `PUT` creates-or-replaces
   the row's `data` rather than requiring a separate create/update distinction —
   simpler than the CRUD shape used elsewhere, and appropriate since a tool's data
   is a single evolving worksheet, not a list of independent records.
8. **PDF export uses `reportlab`, not `WeasyPrint` or a headless browser.**
   `WeasyPrint` needs native Cairo/Pango system libraries in the Docker image
   (real, but avoidable, build/runtime complexity); a headless-browser-based
   renderer is far heavier than this need justifies. `reportlab` is a pure-Python
   PDF-generation library with no native dependencies beyond what `pip`/`uv`
   already installs, sufficient for the spec's "blank printable sections for an
   incomplete NCR, polished report for a closed one" requirement, which is
   template-driven layout rather than arbitrary HTML/CSS rendering. This is a new
   backend dependency, added and `pip-audit`-checked in the slice that introduces
   it (see commit boundaries below), not upfront.
9. **`GET /api/v1/suppliers/{id}/ncr-history` is added in this milestone**, per the
   Milestone 3 plan's design decision 6, which deferred it specifically until the
   NCR schema (and `ncrs.supplier_id`) exists. Read-only, paginated, scoped to the
   caller's organisation exactly like every other Suppliers endpoint.

## In scope

### 1. Schema

All new tables carry `organisation_id` (directly, except child tables which scope
through their parent `ncr_id`) per
[Database.md](../../docs/Database.md#multi-tenancy-baseline). UUID primary keys,
`created_at`/`updated_at` timestamptz where applicable.

- **`ncrs`** — `id`, `organisation_id`, `number` (server-generated, see decision 6),
  `type` (native enum `internal`/`supplier`), `product_id` (nullable FK →
  `products.id`, validated via `app.modules.products.service.get_product`),
  `supplier_id` (nullable FK → `suppliers.id`, validated via
  `app.modules.suppliers.service.get_supplier`; required iff `type == supplier`,
  see decision 5), `status` (native enum `open`/`investigate`/`containment`/
  `corrective_action`/`verification`/`closed`, default `open`), `raised_by_id` (FK
  → `people.id`, not null, validated via
  `app.modules.people.service.get_person`), `description` (text, not null),
  `root_cause_summary` (nullable text), `created_by_id`/`updated_by_id` (FK →
  `users.id`, not null), `created_at`/`updated_at`, `closed_at` (nullable
  timestamptz, set when `status` becomes `closed`), `deleted_at` (nullable
  timestamptz, soft delete per decision 2).
- **`ncr_actions`** — `id`, `ncr_id` (FK, not null), `description` (text, not
  null), `owner_id` (nullable FK → `people.id`, validated via People's service),
  `due_date` (nullable date), `status` (native enum `open`/`complete`, default
  `open`), `completed_at` (nullable timestamptz), `created_by_id` (FK →
  `users.id`, not null), `created_at`/`updated_at`.
- **`ncr_investigation_tools`** — `id`, `ncr_id` (FK, not null), `tool_type`
  (native enum `five_why`/`fishbone`/`eight_d`/`ten_d`), `data` (JSONB, not null,
  default `{}`), `created_by_id`/`updated_by_id` (FK → `users.id`, not null),
  `created_at`/`updated_at`. `UniqueConstraint(ncr_id, tool_type)` per decision 7.
- **`ncr_attachments`** — `id`, `ncr_id` (FK, not null), `document_id` (FK →
  `documents.id`, not null, validated via
  `app.modules.documents.service.get_document`), `description` (nullable text),
  `created_by_id` (FK → `users.id`, not null), `created_at`.
  `UniqueConstraint(ncr_id, document_id)` — attaching the same document twice is a
  clean `409`, not a raw `IntegrityError`, matching the Products link-table
  precedent.
- **`ncr_status_history`** — `id`, `ncr_id` (FK, not null), `from_status`
  (nullable native enum — null for the initial entry into `open`), `to_status`
  (native enum, not null), `changed_by_id` (FK → `users.id`, not null, see
  decision 1), `changed_at` (timestamptz, not null, default now), `comments`
  (nullable text). Immutable — no update/delete route, matching
  `document_versions`/`document_approvals`' existing precedent.

### 2. APIs

Under `/api/v1/ncr`, all requiring `Authorization: Bearer <token>` for an active
user (see decision 2 — no admin gating except NCR deletion):

- `POST/GET /api/v1/ncr`, `GET/PATCH /api/v1/ncr/{id}` — CRUD (no direct `status`
  field in the `PATCH` body — status only changes via `/transition`), list
  filterable by `type`, `status`, `product_id`, `supplier_id`, `raised_by_id`, and
  `search` (substring across `number`/`description`).
- `DELETE /api/v1/ncr/{id}` — admin-only soft delete (see decision 2).
- `POST /api/v1/ncr/{id}/transition` — body `{to_status, comments?}`; `409` if
  `to_status` is not exactly the next status in the fixed sequence, or if
  transitioning to `closed` while any `ncr_actions` row for the NCR is still
  `open` (see decisions 3–4). Writes an `ncr_status_history` row in the same
  transaction.
- `GET/POST /api/v1/ncr/{id}/actions`, `PATCH /api/v1/ncr/actions/{id}` — manage
  actions; `PATCH` supports editing `description`/`owner_id`/`due_date` and
  setting `status: complete` (stamping `completed_at`); cross-org `404` on the
  parent NCR.
- `GET/PUT /api/v1/ncr/{id}/tools/{tool_type}` — read/upsert a tool's `data`;
  `422` for a `tool_type` outside the fixed 4-value enum; `GET` returns `404` only
  if the NCR itself doesn't exist in the caller's org (an NCR with no data yet for
  a given tool returns an empty/default payload, not a `404`, since "not started"
  is a normal state for an optional aid).
- `GET/POST /api/v1/ncr/{id}/attachments`,
  `DELETE /api/v1/ncr/{id}/attachments/{attachment_id}` — manage attachments;
  `404` if `document_id` isn't in the caller's own organisation; `409` on
  duplicate attachment.
- `GET /api/v1/ncr/{id}/export?format=pdf` — added in the PDF-export slice (see
  commit boundaries); an incomplete NCR (`status != closed`) exports with blank
  printable sections for the unfinished parts (investigation tools not yet filled
  in, no `closed_at`), a closed NCR exports as a fully-populated report, per
  decision 8 and the spec.
- `GET /api/v1/suppliers/{id}/ncr-history` — added in this milestone per design
  decision 9; paginated, read-only, `suppliers`-scoped.

### 3. Frontend

`frontend/src/modules/ncr/`, following established conventions (typed
`api.ts`/`types.ts`, `fetchAllPages` for option lists, request-generation guards on
every async effect, `mountedRef` + `<StrictMode>` regression tests,
`.data-table-wrapper`, `getErrorDetail`):

- `NcrsPage.tsx` — searchable/filterable list (search, type, status, product,
  supplier filters) and a create form (type, product/supplier pickers gated by
  type per decision 5, raised-by picker via the People module's typed client,
  description).
- `NcrDetailPage.tsx` — metadata edit; a workflow panel showing the current status
  and the single next-allowed transition (per decision 3, there is only ever one
  valid next status, so this is a single confirm action with an optional comment,
  not a dropdown of every status); status history list; actions list with add/
  edit/complete; the four investigation tools as tabs or sections, each a simple
  structured form matching its `data` shape; attachments list with an
  attach-existing-document flow matching Products' document-linking UX; an export
  button once the PDF-export slice exists.
- A new "NCR" nav link visible to every authenticated user (no admin gate, per
  decision 2), plus the admin-only delete action gated the same way Document
  Management's retirement/delete actions already are.
- `SupplierDetailPage.tsx` (Suppliers module) gains a read-only "NCR history"
  section once `GET /api/v1/suppliers/{id}/ncr-history` exists.

## Security assumptions and hard acceptance criteria

Non-negotiable, verified by passing tests, not just asserted — same posture as
every prior milestone:

- No endpoint leaks whether an NCR/action/tool/attachment/history row exists in
  another organisation (`404`, never `403`, for cross-org lookups by ID).
- An NCR's `organisation_id` is always taken from `current_user`, never from a
  request body/query parameter.
- `product_id`, `supplier_id`, `raised_by_id`/`owner_id` (people), and
  `document_id` are all validated as belonging to the caller's own organisation
  before being linked — never trusted as opaque client-supplied IDs.
- The workflow sequence, the close-blocked-while-actions-open rule, and the
  `type`/`supplier_id` invariant are enforced server-side, covered by tests, not
  just client-side UX.
- The transition-plus-close-guard check is race-safe under real concurrent
  requests (a row lock on the NCR, matching `_lock_document`), covered by the same
  kind of `asyncio.gather` test used for Document Management's category-tree race
  — understood as documentation of intended behaviour rather than a guaranteed
  deterministic reproduction (per the caveat already recorded in
  [DecisionLog.md](../../docs/DecisionLog.md#2026-07-28-document-category-tree-toctou-race-and-frontend-async-state-edge-cases)) —
  plus a deterministic unit test that monkeypatches the guard check to force the
  race outcome directly, per the pattern established in this milestone's own
  closeout
  ([DecisionLog.md](../../docs/DecisionLog.md#2026-07-29-milestone-3-closeout-products-check-then-insert-races-mapped-to-clean-conflicts)).
- Deleting an NCR is admin-only and re-enforced server-side regardless of what the
  client renders or hides.

## Test strategy

Same split as every prior milestone: unit tests (`backend/tests/unit/`, SQLite
where portable) for service-layer scoping, the numbering scheme, the workflow
sequence/close guard, the `type`/`supplier_id` invariant, and cross-module
validation; integration tests (`backend/tests/integration/`, real PostgreSQL,
`httpx.AsyncClient` against `ASGITransport`) for full CRUD/workflow round trips,
cross-organisation `404`s, and the concurrency race. Frontend: Vitest + React
Testing Library, mocking the typed API client, covering list/search/filter,
create/edit, the workflow panel's single-next-transition UX, actions, the four
investigation tool forms, attachment management, `<StrictMode>` mount-safety
regressions, and out-of-order-response guards. All new behaviour written
test-first (RED confirmed, then GREEN), per
[Contributing.md](../../docs/Contributing.md#test-first-workflow-red-green-refactor).

## Migration and rollback strategy

Reviewed Alembic migrations, matching the vertical-slice commit boundaries below,
each with a correct `downgrade()` and each verified with a real upgrade →
downgrade → upgrade cycle against PostgreSQL before being considered done:

1. `ncrs`, `ncr_status_history` — plus a data migration seeding the
   `ncr_numbering_scheme` configuration row for the existing default organisation.
2. `ncr_actions`.
3. `ncr_investigation_tools`.
4. `ncr_attachments`.

No destructive migration touches any Milestone 0–3 table.

## Out of scope (explicitly deferred)

- A "reject and reopen" or backward transition — the spec describes NCR as a
  strictly forward workflow, unlike Document Management's approve/reject; revisit
  only if real usage shows a need to correct a mistaken transition.
- The configurable risk-scoring engine referenced by TODO Task 37 (Research
  Required) — NCR has no risk field in the spec's NCR section itself (unlike
  Suppliers' `risk_rating`), so this doesn't block Milestone 4.
- Automatic supplier notification emails on supplier-NCR creation, NCR trend
  analytics/dashboards, AI-assisted root cause suggestions — already noted as
  "Future improvements" in [docs/modules/NCR.md](../../docs/modules/NCR.md); not
  built speculatively now.
- Any SaaS/multi-organisation feature — out of scope for the whole project until
  scheduled, per [CLAUDE.md](../../CLAUDE.md).

## Suggested commit boundaries

1. `docs: plan Milestone 4 (NCR) before implementation` — this plan,
   `CurrentStatus.md`, `TODO.md` updated to "in progress".
2. `feat: add NCR schema, numbering, CRUD, and the transition workflow` —
   migration 1, `ncrs`/`ncr_status_history` models/schemas/service/router,
   numbering, the workflow state machine and close guard (with its concurrency
   test), backend tests, doc updates.
3. `feat: add NCR actions` — migration 2, `ncr_actions`, backend tests, doc
   updates.
4. `feat: add NCR investigation tools` — migration 3, `ncr_investigation_tools`,
   backend tests, doc updates.
5. `feat: add NCR attachments and supplier NCR history` — migration 4,
   `ncr_attachments`, `GET /api/v1/suppliers/{id}/ncr-history`, backend tests, doc
   updates.
6. `feat: add NCR PDF export` — `reportlab` dependency, export endpoint, backend
   tests, doc updates.
7. `feat: add NCR frontend` — typed client, list/detail pages (metadata, workflow
   panel, actions, tools, attachments, export), Suppliers' NCR-history section,
   tests.
8. `chore: verify Milestone 4 end-to-end via Docker Compose` — real-PostgreSQL
   suite, migration cycle, dependency audits, browser-driven smoke test,
   persistence-restart check, matching the Milestone 3 closeout pattern.
9. `docs: mark Milestone 4 implemented` — close out `CurrentStatus.md`, `TODO.md`,
   this plan's checkboxes.

Smaller/differently-grouped commits are acceptable as long as each is a coherent,
working, tested unit, per [Contributing.md](../../docs/Contributing.md). Given
NCR's **XL** complexity (the largest single module in the roadmap, per
[docs/modules/NCR.md](../../docs/modules/NCR.md)), it is expected to span several
sessions; each numbered commit above is independently a complete, tested,
documented vertical slice, so work can pause after any of them with the repository
left in a truthful, working state.

## Acceptance criteria

- [x] `ncrs`, `ncr_status_history`, `ncr_actions`, `ncr_investigation_tools`,
      `ncr_attachments` exist via reviewed Alembic migrations, each verified with a
      real upgrade → downgrade → upgrade cycle against PostgreSQL.
- [x] Full NCR CRUD works end-to-end against real PostgreSQL, covered by tests.
- [x] The Open → Investigate → Containment → Corrective Action → Verification →
      Close workflow is enforced server-side (no skipping stages, no closing while
      actions are open), covered by tests including a concurrency case.
- [x] Actions, the four investigation tools, and attachments all work end-to-end
      against real PostgreSQL, covered by tests.
- [x] `type`/`supplier_id` invariant, cross-module `product_id`/`supplier_id`/
      `raised_by_id`/`owner_id`/`document_id` validation, and cross-organisation
      `404`s are all covered by tests.
- [x] PDF export produces a real PDF for both an incomplete and a closed NCR.
- [x] `GET /api/v1/suppliers/{id}/ncr-history` works end-to-end, covered by tests.
- [x] Frontend: NCR list/search/filter, create/edit, the workflow panel, actions,
      investigation tools, attachments, export, and the Suppliers NCR-history
      section — all calling real backend endpoints through typed API clients,
      covered by Vitest tests, accessible and responsive.
- [x] All commands in
      [CodingStandards.md](../../docs/CodingStandards.md#commands-established-in-milestone-0-referenced-by-every-later-batch)
      pass: `ruff check`, `ruff format --check`, `mypy` (strict), `pytest` (unit +
      integration), `npm run lint`, `format:check`, `typecheck`, `test`, `build`.
- [x] Dependency audits (`pip-audit`, `npm audit`) re-run, including the new
      `reportlab` dependency; no new findings beyond already-documented deferrals,
      or new findings triaged and recorded.
- [x] `docker compose up --build` smoke test, browser-driven: create an internal
      NCR and a supplier NCR, add an action, fill in an investigation tool, attach
      a document, walk a full transition sequence to Closed (blocked once, then
      unblocked, by an open action), export a PDF, view supplier NCR history — all
      surviving a `docker compose down`/`up` restart (no `-v`).
- [x] `docs/API.md`, `docs/Database.md`, `docs/modules/NCR.md`,
      `docs/modules/Suppliers.md` (NCR history section), `docs/DecisionLog.md`,
      `docs/CurrentStatus.md`, `docs/TODO.md` updated in the same commits as the
      behaviour they describe.

**Milestone 4 closed out 2026-07-30.** See
[docs/CurrentStatus.md](../../docs/CurrentStatus.md) for the full closeout
verification detail and
[docs/DecisionLog.md](../../docs/DecisionLog.md#2026-07-30-milestone-4-closeout-update_ncr-had-no-frozen-once-closed-guard)
for the one finding (and fix) from the closeout security review.

## Next milestone after this one

Milestone 5 — Calibration and Asset Management. See
[Roadmap.md](../../docs/Roadmap.md#m5-calibration-and-asset-management).

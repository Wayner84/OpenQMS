# Milestone 5 — Calibration and Asset Management

**Status:** Planned — not yet implemented.
**Date planned:** 2026-08-01

## Purpose

Build the Calibration and Asset Management module per
[Roadmap.md](../../docs/Roadmap.md#m5-calibration-and-asset-management),
[docs/modules/CalibrationAndAssetManagement.md](../../docs/modules/CalibrationAndAssetManagement.md),
and TODO Task 18 in [docs/TODO.md](../../docs/TODO.md): inspection/measuring
equipment and company assets, calibration schedules, certificate storage,
reminders, status, and complete equipment history. Chosen sixth, per the
Roadmap, because it depends on People (asset owners, calibration performers)
and Documents (certificates) already existing, both complete.

Background reading: [Architecture.md](../../docs/Architecture.md),
[Database.md](../../docs/Database.md), [API.md](../../docs/API.md),
[CodingStandards.md](../../docs/CodingStandards.md),
[Contributing.md](../../docs/Contributing.md), and the completed
[Milestone 4 plan](2026-07-29-milestone-4-ncr.md) for the established
conventions this milestone continues (organisation scoping via `CurrentUser`,
`created_by_id`/`updated_by_id` attribution, the pagination envelope,
`404`-not-`403` for cross-organisation lookups, offset/limit pagination,
`_lock_*`-row-locking for concurrency-sensitive writes, the configuration-table
pattern for operator-tunable values, `fetchAllPages` for frontend option lists,
request-generation guards for async state, `mountedRef`/`<StrictMode>`
regression tests, and the standing practice of running an independent
security/tenant-isolation review after each vertical slice).

## Design decisions made in this plan (refining the "Planned" module doc)

1. **Permissions: any active user, not admin-gated**, matching
   People/Products/Suppliers' precedent (design decision 2 in both the
   Milestone 3 and Milestone 4 plans). Neither the module doc nor the product
   specification calls for admin-only mutation here. All actions remain fully
   scoped to the caller's own organisation and re-enforced server-side.
2. **Calibration events and asset-maintenance-schedule updates never re-upload
   a certificate/attachment themselves.** `calibration_events.certificate_document_id`
   references an existing [Document Management](../../docs/modules/DocumentManagement.md)
   record, validated via `documents.service.get_document` (never the
   `Document` model directly, per the module-isolation rule) — the same
   attach-an-existing-document shape NCR's attachments already established,
   not a second upload pathway. The module doc's "certificate upload" phrasing
   describes the end-to-end user journey (upload the certificate via Document
   Management, then attach it here), not a calibration-owned upload endpoint.
3. **`performed_by_id` (People) and `performed_by_supplier_id` (Suppliers) are
   mutually exclusive but both optional**, enforced at the Pydantic schema
   layer (not a DB constraint), mirroring the People module's
   `is_employee`/`company_id` invariant and NCR's `type`/`supplier_id`
   invariant precedent
   ([DecisionLog.md](../../docs/DecisionLog.md#2026-07-26-people-module-is_employeecompany_id-invariant-enforced-at-the-schema-layer-not-a-db-constraint)).
   Both may be null (a historical event whose performer wasn't recorded is a
   valid, if imperfect, state — this module doesn't retroactively invent data
   that was never captured), but setting both on the same event is rejected
   `422`: a single calibration event was performed either in-house or by one
   external calibration house, never attributed to both at once.
4. **`next_due_date` is server-computed, never client-supplied, on both
   schedule tables.** `calibration_schedules.next_due_date` (and the
   equivalent on `asset_maintenance_schedules`) is recalculated by the service
   layer as `event.performed_at + interval` whenever a new calibration event
   is recorded (`interval_value`/`interval_unit` read from the asset's own
   schedule row, never hard-coded — per CLAUDE.md's "no hard-coded business
   rules" rule, this is operator-configured interval arithmetic, not an
   invented scoring formula). `calibration_events.next_due_date` is a
   point-in-time historical snapshot of what was computed at that event (part
   of "complete equipment history," per the module doc) and, once written, is
   immutable — matching `ncr_status_history`'s existing immutable-audit-trail
   precedent. There is no equivalent "maintenance event" table in this
   milestone (see decision 6) — `asset_maintenance_schedules.next_due_date` is
   instead directly PATCHable by an operator (e.g. "serviced on this date,
   next due in a year"), the simplest shape that matches what the module doc
   actually specifies.
5. **Calibration `result` never automatically changes `assets.status`.** The
   module doc's Workflow section says "the asset's status and next due date
   update" after an event — read narrowly as *next due date* updating
   automatically (decision 4) and *status* remaining an operator-controlled
   field the same way `suppliers.approval_status` is (PATCHable independently,
   not auto-derived). Inventing an automatic `result: fail` →
   `status: out_of_service` transition would be exactly the kind of
   unspecified business rule CLAUDE.md prohibits building ahead of an explicit
   requirement; an operator who fails a calibration can set the asset's status
   themselves in the same UI flow.
6. **No `asset_maintenance_events` table in this milestone.** The module doc's
   "Planned database tables" section lists only `asset_maintenance_schedules`
   (a schedule, not an event history) — unlike `calibration_events`, no
   maintenance-event history table is specified, and the ad hoc
   request-and-completion workflow that *would* naturally produce such history
   is explicitly [Maintenance](../../docs/modules/Maintenance.md)'s job
   (Milestone 6), not this module's. Inventing an events table here would
   duplicate work Milestone 6 is scoped to do properly. `asset_maintenance_schedules`
   in this milestone is therefore a single upsert-style row per asset (create
   via `POST`, update via `PATCH`), matching the module doc's singular
   `GET/POST .../maintenance-schedule` (not `.../maintenance-events`) endpoint
   shape.
7. **The "due" reminder window is a new `configuration` row**,
   `calibration_due_reminder_window_days`, read via a small
   `reminder_config.py` module mirroring `suppliers/reminder_config.py`
   exactly (same fallback-to-default-if-missing shape, same
   [Database.md](../../docs/Database.md#configuration-table) pattern) — never
   a hard-coded literal, per CLAUDE.md.
8. **`assets.asset_tag` is unique per organisation**, enforced at the service
   layer with a clean `409` on conflict (a check-then-insert `IntegrityError`
   fallback, matching `products.part_number`'s established precedent and the
   Milestone 3 closeout's TOCTOU hardening for that exact shape) — not a bare
   DB-level `UNIQUE` alone. An asset tag is the physical label an operator
   walks up and reads off equipment; duplicates within an organisation would
   make that label meaningless.
9. **`DELETE /api/v1/calibration/assets/{id}` is a soft delete (`deleted_at`),
   not a hard delete**, unlike Products/Suppliers' hard-delete precedent. An
   asset carries a "complete equipment history" of calibration events per the
   module doc — audit-significant, like `documents`/`ncrs`, not pure reference
   data like a product or supplier record. Retiring an asset uses the existing
   `status: retired` enum value, not deletion; `DELETE` is reserved for a
   genuine data-entry mistake (an asset that should never have been created),
   matching `documents`'/`ncrs`' existing soft-delete reasoning exactly.

## In scope

### 1. Schema

All new tables carry `organisation_id` per
[Database.md](../../docs/Database.md#multi-tenancy-baseline). UUID primary
keys, `created_at`/`updated_at` timestamptz where applicable,
`created_by_id`/`updated_by_id` → `users.id` per the established convention.

- **`assets`** — `id`, `organisation_id`, `asset_tag` (text, not null, unique
  per organisation — design decision 8), `name` (text, not null), `asset_type`
  (native enum `measuring_equipment` / `inspection_equipment` /
  `company_asset`), `serial_number` (nullable text), `location` (nullable
  text), `owner_id` (nullable FK → `people.id` — an organisational assignment
  that can validly name someone without a login, matching `ncrs.raised_by_id`'s
  precedent), `status` (native enum `in_service` / `out_of_service` /
  `retired`, default `in_service`), `purchase_date` (nullable date),
  `created_by_id`/`updated_by_id`, `created_at`/`updated_at`, `deleted_at`
  (nullable — soft delete, design decision 9).
- **`calibration_schedules`** — `id`, `asset_id` (FK, not null, unique — one
  schedule per asset, `UniqueConstraint(asset_id)`), `interval_value`
  (integer, not null), `interval_unit` (native enum `days` / `months` /
  `years`), `next_due_date` (nullable date — null until the first calibration
  event establishes a baseline, or an operator sets an initial due date
  directly), `created_by_id`/`updated_by_id`, `created_at`/`updated_at`.
- **`calibration_events`** — `id`, `asset_id` (FK, cascade delete), `performed_at`
  (date, not null), `performed_by_id` (nullable FK → `people.id`),
  `performed_by_supplier_id` (nullable FK → `suppliers.id` — design decision
  3), `certificate_document_id` (nullable FK → `documents.id`, no `ON DELETE`
  — matching `ncr_attachments.document_id`'s precedent, since a certificate
  being independently soft-deleted later must not silently cascade-delete
  calibration history), `result` (native enum `pass` / `fail` / `limited`),
  `next_due_date` (nullable date — the snapshot computed at this event, design
  decision 4), `notes` (nullable text), `created_by_id`, `created_at`.
  Immutable — no update/delete route, matching `ncr_status_history`'s
  precedent.
- **`asset_maintenance_schedules`** — `id`, `asset_id` (FK, not null, unique —
  `UniqueConstraint(asset_id)`), `interval_value` (integer, not null),
  `interval_unit` (native enum `days` / `months` / `years`), `next_due_date`
  (nullable date, directly settable — design decision 6),
  `created_by_id`/`updated_by_id`, `created_at`/`updated_at`.

A new `configuration` row, `calibration_due_reminder_window_days` (default
`30`), seeded for the existing default organisation in the first migration,
matching `supplier_certification_reminder_window_days`'s existing precedent
(design decision 7).

### 2. APIs

Under `/api/v1/calibration`, all requiring `Authorization: Bearer <token>` for
an **active user** (design decision 1 — no admin gating):

- `GET/POST /api/v1/calibration/assets`,
  `GET/PATCH/DELETE /api/v1/calibration/assets/{id}` — CRUD, list filterable
  by `asset_type`, `status`, `location`, and `search` (substring across
  `asset_tag`/`name`/`serial_number`). `DELETE` is admin-independent (any
  active user, matching decision 1) soft delete — design decision 9. `409` on
  a duplicate `asset_tag` within the organisation — design decision 8.
- `GET/POST /api/v1/calibration/assets/{id}/schedule` — read or create-once
  the calibration schedule; `PATCH` to change `interval_value`/`interval_unit`
  or manually set `next_due_date`. `404` for a cross-organisation asset `{id}`.
- `GET/POST /api/v1/calibration/assets/{id}/events` — record (paginated list
  of) calibration events; recording one recomputes and persists the parent
  schedule's `next_due_date` in the same transaction (design decision 4),
  row-locking the schedule the same way `documents.service._lock_document`/
  `ncr.service._lock_ncr` guard their own concurrency-sensitive updates.
  `404` if `certificate_document_id` isn't in the caller's own organisation;
  `422` if both `performed_by_id` and `performed_by_supplier_id` are set
  (design decision 3).
- `GET/POST/PATCH /api/v1/calibration/assets/{id}/maintenance-schedule` —
  create-or-update the single maintenance-schedule row per asset (design
  decision 6); `GET` returns a default empty/not-started payload if none
  exists yet, matching NCR investigation tools' "not started is a normal
  state" precedent, rather than a `404`.
- `GET /api/v1/calibration/due` — assets whose calibration or maintenance
  `next_due_date` falls within the configured (or an explicit
  `?within_days=`) reminder window (design decision 7), paginated, sorted
  soonest-due-first, scoped to the caller's organisation.

### 3. Frontend

`frontend/src/modules/calibration/`, following this codebase's established
conventions (typed `api.ts`/`types.ts`, `fetchAllPages` for option lists,
request-generation guards on every async effect, `mountedRef` +
`<StrictMode>` regression tests, `.data-table-wrapper`, `getErrorDetail`):

- `AssetsPage.tsx` — searchable/filterable list (search, type, status,
  location filters) and a create form (owner picker via the People module's
  typed client).
- `AssetDetailPage.tsx` — asset metadata/edit; calibration schedule
  view/edit; calibration event history (append-only list with an add form,
  including an attach-existing-certificate flow matching NCR attachments'
  document-search-and-select UX); maintenance schedule view/edit; a due/
  overdue indicator sourced from the same computed `next_due_date` fields
  already on the page (no separate round trip needed for the detail page
  itself — `GET /calibration/due` is for the list/dashboard view).
- A "Calibration" nav link visible to every authenticated user (no admin
  gate, per design decision 1).
- Optionally, a small "Due for calibration/maintenance" panel on `AssetsPage.tsx`
  surfacing `GET /api/v1/calibration/due` — scoped to this milestone only if
  it fits without scope creep into the dashboards/saved-filters work
  explicitly reserved for Milestone 10.

## Security assumptions and hard acceptance criteria

Non-negotiable, verified by passing tests, not just asserted — same posture as
every prior milestone:

- No endpoint leaks whether an asset/schedule/event exists in another
  organisation (`404`, never `403`, for cross-org lookups by ID).
- An asset's `organisation_id` is always taken from `current_user`, never from
  a request body/query parameter.
- `owner_id`, `performed_by_id`, `performed_by_supplier_id`, and
  `certificate_document_id` are all validated as belonging to the caller's own
  organisation before being linked — never trusted as opaque client-supplied
  IDs.
- `asset_tag` uniqueness is enforced server-side under real concurrency (a
  deterministic unit test forcing the `IntegrityError` fallback path, plus a
  best-effort real-concurrency integration test documenting intended
  behaviour, matching the Milestone 3 closeout's TOCTOU-hardening pattern).
- `next_due_date` recalculation on recording a calibration event is race-safe
  under concurrent requests via a row lock on the schedule, the same
  `_lock_*` pattern used throughout Documents/NCR.
- The `performed_by_id`/`performed_by_supplier_id` mutual-exclusivity
  invariant is enforced server-side, covered by tests, not just client-side
  UX.

## Test strategy

Same split as every prior milestone: unit tests (`backend/tests/unit/`,
SQLite where portable) for service-layer scoping, the mutual-exclusivity
invariant, the `next_due_date` recomputation arithmetic, and the reminder
window fallback; integration tests (`backend/tests/integration/`, real
PostgreSQL, `httpx.AsyncClient` against `ASGITransport`) for full CRUD round
trips, cross-organisation `404`s, the `asset_tag` conflict `409`, and the
`due` endpoint's window filtering. Frontend: Vitest + React Testing Library,
mocking the typed API client, covering list/search/filter, create/edit/soft-
delete, the schedule/event/maintenance-schedule management UI,
`<StrictMode>` mount-safety regressions, and out-of-order-response guards for
every async effect, per
[CodingStandards.md](../../docs/CodingStandards.md#frontend-react-typescript).
All new behaviour written test-first (RED confirmed, then GREEN), per
[Contributing.md](../../docs/Contributing.md#test-first-workflow-red-green-refactor).

## Migration and rollback strategy

Reviewed Alembic migrations, matching the vertical-slice commit boundaries
below, each with a correct `downgrade()` and each verified with a real
upgrade → downgrade → upgrade cycle against PostgreSQL before being
considered done:

1. `assets` — plus a data migration seeding the
   `calibration_due_reminder_window_days` configuration row for the existing
   default organisation.
2. `calibration_schedules`, `calibration_events`.
3. `asset_maintenance_schedules`.

No destructive migration touches any Milestone 0–4 table.

## Out of scope (explicitly deferred)

- Automated reminder emails as due dates approach — no email/notification
  infrastructure exists yet (same reasoning as the Milestone 3 plan's
  certification-expiry deferral); the `due` list endpoint itself is in scope.
- Barcode/QR asset tagging and mobile scanning — noted as a future
  improvement in the module doc, not built speculatively now.
- Configurable calibration interval defaults by asset type — `interval_value`/
  `interval_unit` are set per-asset by an operator in this milestone, no
  asset-type-level default template.
- An `asset_maintenance_events` history table — deferred to (and properly
  belongs in) [Maintenance](../../docs/modules/Maintenance.md), Milestone 6
  (design decision 6).
- Any SaaS/multi-organisation feature — out of scope for the whole project
  until scheduled, per [CLAUDE.md](../../CLAUDE.md).

## Suggested commit boundaries

1. `docs: plan Milestone 5 (Calibration and Asset Management) before implementation`
   — this plan, `CurrentStatus.md`, `TODO.md` updated to "in progress".
2. `feat: add assets schema and CRUD` — migration 1, `assets` model/schemas/
   service/router, backend tests, doc updates.
3. `feat: add calibration schedules and events` — migration 2,
   `calibration_schedules`/`calibration_events`, the `next_due_date`
   recomputation, backend tests, doc updates.
4. `feat: add asset maintenance schedules and the due-reminders endpoint` —
   migration 3, `asset_maintenance_schedules`, `GET /calibration/due`,
   backend tests, doc updates.
5. `feat: add Calibration and Asset Management frontend` — typed client,
   list/detail pages (metadata, schedule, events, maintenance schedule), nav
   link, tests.
6. `chore: verify Milestone 5 end-to-end via Docker Compose` — real-PostgreSQL
   suite, migration cycle, dependency audits, browser-driven smoke test,
   persistence-restart check, an independent security review, matching the
   Milestone 3/4 closeout pattern.
7. `docs: mark Milestone 5 implemented` — close out `CurrentStatus.md`,
   `TODO.md`, this plan's checkboxes.

Smaller/differently-grouped commits are acceptable as long as each is a
coherent, working, tested unit, per [Contributing.md](../../docs/Contributing.md).
Each independent security review already run per prior milestone (NCR
actions/investigation-tools/attachments/PDF-export, and the Milestone 4
closeout review that caught `update_ncr`'s missing frozen-once-closed guard)
argues for running one after each vertical slice here too, not only at final
closeout — cheaper to catch a gap the moment its sibling pattern is
established than after three more slices have had the chance to repeat it.

## Acceptance criteria

- [ ] `assets`, `calibration_schedules`, `calibration_events`,
      `asset_maintenance_schedules` exist via reviewed Alembic migrations,
      each verified with a real upgrade → downgrade → upgrade cycle against
      PostgreSQL.
- [ ] Full asset CRUD (including soft delete) works end-to-end against real
      PostgreSQL, covered by tests.
- [ ] Calibration schedules and events work end-to-end, including
      server-computed, race-safe `next_due_date` recalculation on recording
      an event, covered by tests including a concurrency case.
- [ ] Asset maintenance schedules and the `due` reminders endpoint work
      end-to-end, covered by tests.
- [ ] `asset_tag` uniqueness, the `performed_by_id`/`performed_by_supplier_id`
      mutual-exclusivity invariant, cross-module `owner_id`/`performed_by_id`/
      `performed_by_supplier_id`/`certificate_document_id` validation, and
      cross-organisation `404`s are all covered by tests.
- [ ] Frontend: asset list/search/filter, create/edit/soft-delete, calibration
      schedule/event management, maintenance schedule management — all
      calling real backend endpoints through typed API clients, covered by
      Vitest tests, accessible and responsive.
- [ ] All commands in
      [CodingStandards.md](../../docs/CodingStandards.md#commands-established-in-milestone-0-referenced-by-every-later-batch)
      pass: `ruff check`, `ruff format --check`, `mypy` (strict), `pytest`
      (unit + integration), `npm run lint`, `format:check`, `typecheck`,
      `test`, `build`.
- [ ] Dependency audits (`pip-audit`, `npm audit`) re-run; no new findings
      beyond already-documented deferrals, or new findings triaged and
      recorded.
- [ ] `docker compose up --build` smoke test, browser-driven: create an
      asset, set its calibration schedule, record a calibration event with an
      attached certificate, verify the schedule's `next_due_date` updated,
      set an asset maintenance schedule, check the `due` endpoint/UI reflects
      it, soft-delete an asset — all surviving a `docker compose down`/`up`
      restart (no `-v`).
- [ ] `docs/API.md`, `docs/Database.md`,
      `docs/modules/CalibrationAndAssetManagement.md`, `docs/DecisionLog.md`,
      `docs/CurrentStatus.md`, `docs/TODO.md` updated in the same commits as
      the behaviour they describe.

## Next milestone after this one

Milestone 6 — Maintenance. See
[Roadmap.md](../../docs/Roadmap.md#m6-maintenance).

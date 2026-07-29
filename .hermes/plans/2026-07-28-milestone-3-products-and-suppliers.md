# Milestone 3 — Products and Suppliers

**Status:** Complete — implemented and closed out. See
[CurrentStatus.md](../../docs/CurrentStatus.md) for verification detail.
**Date planned:** 2026-07-28
**Date closed out:** 2026-07-29

## Purpose

Build the two foundational reference-data modules that Milestone 4 (NCR) and the
later FAIR/SPC modules depend on, per
[Roadmap.md](../../docs/Roadmap.md#m3-products-and-suppliers),
[docs/modules/Products.md](../../docs/modules/Products.md),
[docs/modules/Suppliers.md](../../docs/modules/Suppliers.md), and TODO Tasks 15–16 in
[docs/TODO.md](../../docs/TODO.md): product/component records with drawing/spec
links, and approved-supplier records with certifications and performance history.
Chosen fourth, per the Roadmap, because NCR/FAIR/SPC all reference products, and NCR
references suppliers — building these now avoids retrofitting those relationships
later.

Background reading: [Architecture.md](../../docs/Architecture.md),
[Database.md](../../docs/Database.md), [API.md](../../docs/API.md),
[CodingStandards.md](../../docs/CodingStandards.md),
[Contributing.md](../../docs/Contributing.md), and the completed
[Milestone 2 plan](2026-07-26-milestone-2-document-management.md) for the established
conventions this milestone continues (organisation scoping via `CurrentUser`,
`created_by_id`/`updated_by_id` attribution, the pagination envelope, `404`-not-`403`
for cross-organisation lookups, offset/limit pagination, `fetchAllPages` for
frontend option lists, request-generation guards for async state, `mountedRef`/
`<StrictMode>` regression tests).

## Design decisions made in this plan (refining the "Planned" module docs)

1. **Suppliers before Products, within this milestone.** Both module docs sketch a
   `product_supplier_links` table (owned by Products) referencing `suppliers.id`.
   Building Suppliers first (it only depends on People's `companies`, already done)
   avoids a forward reference; Products' supplier-link table is added once
   `suppliers` exists. This is purely a build-order choice within the same
   milestone, not a scope change from either module doc.
2. **Permissions: any active user, matching the People module's precedent, not
   admin-gated.** Neither module doc nor the product specification calls for
   admin-only mutation here (unlike Document Management's category/tag admin
   gating, which exists because categories/tags are shared taxonomy that every
   document depends on). Products and Suppliers are collaborative reference data
   much closer in shape to People/Companies — any active user can create, edit,
   and delete (subject to the same kind of "still referenced" delete guards People
   and Document Management already use), all still scoped to the caller's own
   organisation and fully re-enforced server-side. Revisit if a future module
   surfaces a reason certain actions need to be admin-only.
3. **`suppliers.risk_rating` is a plain, operator-settable field in this milestone,
   not an auto-computed score.** TODO Task 37 ("Research Required") notes the
   configurable risk-scoring engine shared by NCR/Suppliers/Risk Assessments is an
   open research question, deliberately not resolved yet. Building a scoring
   formula now would be exactly the kind of hard-coded business rule CLAUDE.md
   prohibits, invented ahead of that research. `risk_rating` is therefore a small
   fixed enum (`low`/`medium`/`high`) an operator sets directly — useful today,
   trivially replaceable by a real scoring engine later without a breaking schema
   change (the column stays; how it's populated changes).
4. **`supplier_performance_records.score` is a plain operator-entered numeric
   value in this milestone**, for the same reason as decision 3 — no scoring
   formula invented speculatively.
5. **Certification expiry reminders (the "expiring" list endpoint) are read-only
   in this milestone.** `GET /api/v1/suppliers/certifications/expiring` returns
   certifications expiring within a configurable window (a new
   `supplier_certification_reminder_window_days` `configuration` row, per the
   established configuration-table pattern — never hard-coded), but actually
   *sending* a reminder (email, in-app notification) is out of scope: openQMS has
   no notification/email infrastructure yet, and building one speculatively for
   this one field would be exactly the "unrelated... speculative infrastructure"
   CLAUDE.md warns against. Tracked as a future improvement in both module docs
   (already noted there).
6. **`GET /api/v1/suppliers/{id}/ncr-history` is deferred to Milestone 4.** Both
   module docs describe it as a read-only join into the NCR module, which does not
   exist yet (`suppliers.md`'s own "Relationships to other modules" section
   describes NCR *linking to* Suppliers, not the reverse dependency existing yet).
   Adding a stub now that always returns an empty list would be dead code with
   nothing to test meaningfully; building the real endpoint alongside Milestone 4's
   NCR schema (which is when `ncr_records.supplier_id` will actually exist) avoids
   that. Noted in both module docs.

## In scope

### 1. Suppliers schema

All new tables carry `organisation_id` per
[Database.md](../../docs/Database.md#multi-tenancy-baseline). UUID primary keys,
`created_at`/`updated_at` timestamptz, `created_by_id`/`updated_by_id` → `users.id`
per the established convention.

- **`suppliers`** — `id`, `organisation_id`, `company_id` (FK → `companies.id`, not
  null — the supplier's name/address/contact data lives on the shared `companies`
  row per the module doc, not duplicated here; the caller-side service layer
  validates the referenced company belongs to the caller's organisation, matching
  the pattern `documents.category_id`/`owner_id` validation already uses),
  `approval_status` (native enum `approved`/`pending`/`suspended`, default
  `pending`), `risk_rating` (nullable native enum `low`/`medium`/`high` — see
  design decision 3), `is_preferred` (boolean, default `false`), `notes` (nullable
  text), `created_by_id`/`updated_by_id`, `created_at`/`updated_at`.
- **`supplier_certifications`** — `id`, `supplier_id` (FK, not null),
  `certification_type` (text, not null — free text, not an enum: the module doc
  calls this "a configurable list" and the spec names examples like ISO 9001/AS9100
  without fixing a closed set; a closed enum would need a migration for every new
  accreditation type an operator wants to track, which is the opposite of
  configurable), `certificate_document_id` (nullable FK →
  `documents.id` — see [Document Management](../../docs/modules/DocumentManagement.md)),
  `issued_date` (nullable date), `expiry_date` (nullable date), `created_at`/
  `updated_at`.
- **`supplier_performance_records`** — `id`, `supplier_id` (FK, not null), `period`
  (text, not null — e.g. `"2026-Q3"`; free text rather than a fixed period-type enum,
  since reporting cadence is an operator choice), `score` (numeric, not null — see
  design decision 4), `notes` (nullable text), `created_by_id`, `created_at`.

### 2. Products schema

- **`product_categories`** — `id`, `organisation_id`, `name`, `created_at`/
  `updated_at`. Flat (no `parent_category_id` self-reference): the module doc's
  planned-tables section describes this as a flat list (`id`, `organisation_id`,
  `name`), unlike Document Management's explicitly-tree-shaped
  `document_categories` — not a schema change from the module doc, just following
  what it already specifies.
- **`products`** — `id`, `organisation_id`, `part_number` (text, not null),
  `description` (text, not null), `revision` (text, not null, default `"A"`),
  `category_id` (nullable FK → `product_categories.id`), `type` (native enum
  `internal`/`purchased`/`assembly`/`component`), `manufacturing_notes` (nullable
  text), `created_by_id`/`updated_by_id`, `created_at`/`updated_at`. `part_number`
  is unique per organisation (a `UniqueConstraint(organisation_id, part_number)`,
  matching the uniqueness the module doc implies by calling it filterable/
  searchable as a stable identifier) — enforced at the service layer with a `409`
  on conflict, mirroring `document_tags.name`'s existing per-organisation-uniqueness
  pattern, not a hard DB-level `UNIQUE` alone (same reasoning already recorded for
  that precedent: a clean `409` with a message, not a raw `IntegrityError` leaking
  to the client).
- **`product_documents`** — `id`, `product_id` (FK, not null), `document_id` (FK →
  `documents.id`, not null), `relationship_type` (native enum `drawing`/
  `specification`/`cad`), `created_at`. Composite uniqueness on
  (`product_id`, `document_id`, `relationship_type`) — the same document can be
  linked to a product under more than one relationship type (e.g. a single PDF that
  is both a drawing and a specification) but not linked twice under the identical
  type.
- **`product_supplier_links`** — `id`, `product_id` (FK, not null), `supplier_id`
  (FK → `suppliers.id`, not null), `is_preferred` (boolean, default `false`).
  Composite uniqueness on (`product_id`, `supplier_id`).

### 3. APIs

Under `/api/v1/suppliers` and `/api/v1/products`, all requiring
`Authorization: Bearer <token>` for an **active user** in the organisation (see
design decision 2 — no admin gating in this milestone):

- `POST/GET /api/v1/suppliers`, `GET/PATCH/DELETE /api/v1/suppliers/{id}` — CRUD,
  list filterable by `approval_status`, `risk_rating`, `is_preferred`, and
  `search` (substring across the linked company's name, joined through
  `companies`). `DELETE` is a hard delete (suppliers carry no audit-significant
  child records of their own beyond certifications/performance, which cascade —
  see [Database.md](../../docs/Database.md#soft-delete-and-audit-trail)'s existing
  distinction between soft-delete-worthy and ordinary reference data; `documents`
  soft-deletes because it's the audit trail itself, `companies`/`people` hard-delete
  today and suppliers follow that same existing precedent, not a new one).
- `POST/GET /api/v1/suppliers/{id}/certifications`,
  `PATCH/DELETE /api/v1/suppliers/{id}/certifications/{certification_id}` — manage
  certifications.
- `GET /api/v1/suppliers/certifications/expiring?within_days=` — upcoming-expiry
  list (default window from the new `supplier_certification_reminder_window_days`
  configuration row if `within_days` isn't supplied).
- `POST/GET /api/v1/suppliers/{id}/performance` — record/list performance entries
  (append-only from the API's perspective — no update/delete route, matching
  `document_versions`/`document_approvals`' existing immutable-history pattern for
  the same reason: a performance record is a point-in-time entry, not a mutable
  field).
- `POST/GET /api/v1/product-categories`,
  `PATCH/DELETE /api/v1/product-categories/{id}` — CRUD; `409` deleting a category
  still referenced by a product (mirrors `document_categories`' existing guard).
- `POST/GET /api/v1/products`, `GET/PATCH/DELETE /api/v1/products/{id}` — CRUD,
  list filterable by `category_id`, `type`, and `search` (substring across
  `part_number`/`description`). `DELETE` is a hard delete (no workflow/approval
  history to preserve for a product record itself, unlike documents).
- `POST/GET /api/v1/products/{id}/documents`,
  `DELETE /api/v1/products/{id}/documents/{link_id}` — attach/list/unlink linked
  drawings/specs; `404` if `document_id` isn't in the caller's own organisation.
- `POST/GET /api/v1/products/{id}/suppliers`,
  `DELETE /api/v1/products/{id}/suppliers/{link_id}` — attach/list/unlink linked
  suppliers; `404` if `supplier_id` isn't in the caller's own organisation.

### 4. Frontend

`frontend/src/modules/suppliers/` and `frontend/src/modules/products/`, following
the Document Management module's established conventions (typed `api.ts`/`types.ts`,
`fetchAllPages` for option lists, request-generation guards on every async effect,
`mountedRef` + `<StrictMode>` regression tests, `.data-table-wrapper`,
`getErrorDetail`):

- `SuppliersPage.tsx` — searchable/filterable list (search, approval status, risk
  rating, preferred filters) and a create form (selecting an existing company via
  the People module's typed client, or linking to `CompaniesPage`'s "create a
  company first" flow the same way Document Management links out to
  `DocumentCategoriesPage`).
- `SupplierDetailPage.tsx` — supplier metadata/edit, certifications list with
  add/edit/delete and an expiry-highlighted state, performance record list with an
  add form.
- `ProductsPage.tsx` — searchable/filterable list (search, category, type filters)
  and a create form; category administration reachable from it, matching
  `DocumentCategoriesPage`'s admin-reachable-from-the-list pattern (though not
  admin-gated here — see design decision 2).
- `ProductDetailPage.tsx` — product metadata/edit, linked documents (attach an
  existing document by search, matching Document Management's typed client;
  remove a link), linked suppliers (attach/remove, showing `is_preferred`).

## Security assumptions and hard acceptance criteria

Non-negotiable, verified by passing tests, not just asserted — same posture as every
prior milestone:

- No endpoint leaks whether a supplier/product/category/certification/performance
  record exists in another organisation (`404`, never `403`, for cross-org lookups
  by ID).
- A supplier's/product's `organisation_id` is always taken from `current_user`,
  never from a request body/query parameter.
- `company_id` (suppliers), `document_id` (product/certification links),
  `category_id`, and `supplier_id` are all validated as belonging to the caller's
  own organisation before being linked — never trusted as opaque client-supplied
  IDs.
- `part_number` uniqueness and category/company "still referenced" delete guards
  are enforced server-side, covered by tests, not just client-side UX.
- Every permission guard (none of which are admin-only in this milestone — see
  design decision 2) is still scoped to an **active** authenticated user; an
  inactive or unauthenticated caller is rejected the same way every other module
  already rejects one.

## Test strategy

Same split as every prior milestone: unit tests (`backend/tests/unit/`, SQLite
where portable) for service-layer scoping, uniqueness/delete guards, and the
certification-expiry window calculation; integration tests
(`backend/tests/integration/`, real PostgreSQL, `httpx.AsyncClient` against
`ASGITransport`) for full CRUD round trips, cross-organisation `404`s, the
`part_number` conflict `409`, category/company delete guards, and the
product↔document/product↔supplier link endpoints. Frontend: Vitest + React Testing
Library, mocking the typed API client, covering list/search/filter, create/edit/
delete, the link-management UI, `<StrictMode>` mount-safety regressions, and
out-of-order-response guards for every async effect, per
[CodingStandards.md](../../docs/CodingStandards.md#frontend-react-typescript). All
new behaviour written test-first (RED confirmed, then GREEN), per
[Contributing.md](../../docs/Contributing.md#test-first-workflow-red-green-refactor).

## Migration and rollback strategy

Reviewed Alembic migrations, matching the vertical-slice commit boundaries below,
each with a correct `downgrade()` and each verified with a real upgrade → downgrade
→ upgrade cycle against PostgreSQL before being considered done:

1. `suppliers`, `supplier_certifications`, `supplier_performance_records` — plus a
   data migration seeding the `supplier_certification_reminder_window_days`
   configuration row (default value, e.g. `30` days) for the existing default
   organisation.
2. `product_categories`, `products`, `product_documents`, `product_supplier_links`.

No destructive migration touches any Milestone 0/1/2 table.

## Out of scope (explicitly deferred)

- The configurable risk/performance scoring engine — TODO Task 37 (Research
  Required); `risk_rating`/`score` are plain operator-entered fields for now (design
  decisions 3–4).
- Actually sending certification-expiry reminder notifications — no email/
  notification infrastructure exists yet (design decision 5); the expiring-list
  endpoint itself is in scope.
- `GET /api/v1/suppliers/{id}/ncr-history` — deferred to Milestone 4, when the NCR
  module (and `ncr_records.supplier_id`) actually exists (design decision 6).
- Bill-of-materials / assembly parent-child product structure, an image gallery
  beyond single document links, direct ERP integration, a self-service supplier
  portal, supplier scorecards/dashboards — all already noted as "Future
  improvements" in the module docs; not built speculatively now.
- Any SaaS/multi-organisation feature — out of scope for the whole project until
  scheduled, per [CLAUDE.md](../../CLAUDE.md).

## Suggested commit boundaries

1. `docs: plan Milestone 3 (Products and Suppliers) before implementation` — this
   plan, `CurrentStatus.md`, `TODO.md` updated to "in progress".
2. `feat: add suppliers, certifications, and performance records` — migration 1,
   models, schemas, service, router, backend tests, doc updates.
3. `feat: add products, product categories, and product-document/supplier links` —
   migration 2, models, schemas, service, router, backend tests, doc updates.
4. `feat: add Suppliers frontend` — typed client, list/detail pages, tests.
5. `feat: add Products frontend` — typed client, list/detail pages, tests.
6. `chore: verify Milestone 3 end-to-end via Docker Compose` — real-PostgreSQL
   suite, migration cycle, dependency audits, browser-driven smoke test,
   persistence-restart check, matching the Milestone 2 closeout pattern.
7. `docs: mark Milestone 3 implemented` — close out `CurrentStatus.md`, `TODO.md`,
   this plan's checkboxes.

Smaller/differently-grouped commits are acceptable as long as each is a coherent,
working, tested unit, per [Contributing.md](../../docs/Contributing.md).

## Acceptance criteria

- [x] `suppliers`, `supplier_certifications`, `supplier_performance_records`,
      `product_categories`, `products`, `product_documents`,
      `product_supplier_links` exist via reviewed Alembic migrations, each verified
      with a real upgrade → downgrade → upgrade cycle against PostgreSQL.
- [x] Full Suppliers CRUD + certifications + performance records works end-to-end
      against real PostgreSQL, covered by tests.
- [x] Full Products CRUD + category admin + document/supplier links works
      end-to-end against real PostgreSQL, covered by tests.
- [x] `part_number` uniqueness, category/company "still referenced" delete guards,
      and cross-organisation `404`s are all covered by tests.
- [x] Frontend: Suppliers and Products list/search/filter, create/edit/delete,
      certification/performance management, document/supplier link management —
      all calling real backend endpoints through typed API clients, covered by
      Vitest tests, accessible and responsive.
- [x] All commands in
      [CodingStandards.md](../../docs/CodingStandards.md#commands-established-in-milestone-0-referenced-by-every-later-batch)
      pass: `ruff check`, `ruff format --check`, `mypy` (strict), `pytest` (unit +
      integration), `npm run lint`, `format:check`, `typecheck`, `test`, `build`.
- [x] Dependency audits (`pip-audit`, `npm audit`) re-run; no new findings beyond
      already-documented deferrals, or new findings triaged and recorded.
- [x] `docker compose up --build` smoke test, browser-driven: create a supplier
      (with a certification and a performance record), create a product category,
      create a product linking that supplier and a document, edit and delete
      records — all surviving a `docker compose down`/`up` restart (no `-v`).
- [x] `docs/API.md`, `docs/Database.md`, `docs/modules/Products.md`,
      `docs/modules/Suppliers.md`, `docs/DecisionLog.md`, `docs/CurrentStatus.md`,
      `docs/TODO.md` updated in the same commits as the behaviour they describe.

## Next milestone after this one

Milestone 4 — NCR. See [Roadmap.md](../../docs/Roadmap.md#m4-ncr).

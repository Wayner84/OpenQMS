# Suppliers

**Status: Implemented.** [Milestone 3](../Roadmap.md#m3-products-and-suppliers)
is complete and closed out — see [docs/CurrentStatus.md](../CurrentStatus.md) and
the [Milestone 3 plan](../../.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md)
for full verification detail. The backend (schema, migration, CRUD,
certifications, performance records, the expiring-certifications endpoint) and the
frontend (`frontend/src/modules/suppliers/`: `SuppliersPage`/`SupplierDetailPage`)
are both implemented and tested. Built first within this milestone (before Products),
since it has no dependency on Products and Products' `product_supplier_links`
depends on it.

## Purpose

Approved supplier records: certificates, addresses, contacts, performance, NCR
history, approval status, expiry reminders, ISO and other accreditation, risk rating
and preferred supplier status, per
[ProductSpecification.md](../ProductSpecification.md#suppliers).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`suppliers`** — `id`, `organisation_id`, `company_id` → [People](People.md)
  `companies.id` (address/contact/name data lives on the shared `companies` record,
  not duplicated here), `approval_status` (`approved` / `pending` / `suspended`),
  `risk_rating`, `is_preferred` (bool), `notes`, `created_at`, `updated_at`.
- **`supplier_certifications`** — `id`, `supplier_id`, `certification_type` (e.g.
  ISO 9001, AS9100 — configurable list), `certificate_document_id` →
  [Document Management](DocumentManagement.md), `issued_date`, `expiry_date`,
  `reminder_sent_at`.
- **`supplier_performance_records`** — `id`, `supplier_id`, `period`, `score`,
  `notes` — scoring model driven by the `configuration` table pattern (see
  [Database.md](../Database.md#configuration-table)) rather than a hard-coded
  formula.

## Planned APIs

Under `/api/v1/suppliers`:

- `GET/POST /api/v1/suppliers`, `GET/PATCH/DELETE /api/v1/suppliers/{id}` — CRUD,
  filterable by approval status, risk rating, preferred flag.
- `GET/POST /api/v1/suppliers/{id}/certifications` — manage certifications;
  `GET /api/v1/suppliers/certifications/expiring` — upcoming expiry list, feeding
  reminder notifications.
- `GET/POST /api/v1/suppliers/{id}/performance` — record/list performance entries.
- `GET /api/v1/suppliers/{id}/ncr-history` — aggregated read of supplier NCRs from
  the [NCR](NCR.md) module (read-only join, not duplicated data).

## Workflow

A supplier is created against a `companies` record from [People](People.md) →
certifications are recorded with expiry dates and reminders → performance is recorded
over time → an approval status and risk rating are maintained (risk rating shares its
configurable-scoring design question with NCR and Risk Assessments — see
[TODO.md](../TODO.md) Research Required) → the [NCR](NCR.md) module references this
supplier for supplier NCRs, and that history is surfaced back here without
duplication.

## Relationships to other modules

Per [ProductSpecification.md](../ProductSpecification.md#module-relationships):

- **Suppliers link to NCR**; **people link to suppliers.** Supplier contacts are
  [People](People.md) rows with `company_id` set to this supplier's `companies` row.
- [Products](Products.md) link to Suppliers via `product_supplier_links`.
- Certificates are [Document Management](DocumentManagement.md) records.

## Future improvements

- Automated expiry email reminders.
- Supplier scorecards/dashboards.
- Self-service supplier portal for certificate submission.

## Known issues / status

Backend schema, migration, and API are implemented and tested (unit + real-PostgreSQL
integration); the frontend (`SuppliersPage` search/filter/create, `SupplierDetailPage`
metadata edit + certifications + performance records) is implemented and tested
(Vitest + React Testing Library) — see the
[Milestone 3 plan](../../.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md).
`GET /api/v1/suppliers/{id}/ncr-history` is deferred to Milestone 4, when the NCR
module's `ncr_records.supplier_id` actually exists (plan design decision 6). The exact
risk-scoring formula remains an open research question shared with
[NCR](NCR.md) and [Health and Safety: Risk Assessments](HealthAndSafetyRiskAssessments.md)
— see [TODO.md](../TODO.md#research-required); `risk_rating`/performance `score` are
plain operator-entered fields for now.

## Related documents

- [Roadmap.md](../Roadmap.md#m3-products-and-suppliers)
- [People.md](People.md)
- [NCR.md](NCR.md)

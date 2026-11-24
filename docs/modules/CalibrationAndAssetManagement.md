# Calibration and Asset Management

**Status: Backend implemented (asset CRUD, calibration schedules/events, maintenance schedules and due list).** [Milestone 5](../Roadmap.md#m5-calibration-and-asset-management)
is in progress — full scope, schema, API, and design decisions in the
[Milestone 5 plan](../../.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md).
Asset CRUD and calibration schedules/events are implemented and tested against
disposable PostgreSQL; see [docs/CurrentStatus.md](../CurrentStatus.md)
for exact scope. The frontend asset register/create and metadata detail/edit/
soft-delete, calibration schedule and separate asset maintenance schedule
management and the combined due-list page are implemented; event UI and
full-stack acceptance remain pending.

## Purpose

Inspection equipment, measuring equipment and company assets: calibration schedules,
appropriate asset maintenance schedules, certificate storage, reminders, status and
complete equipment history. Examples include micrometers, calipers, CMMs, height
gauges, surface testers and torque equipment. **Production machinery belongs in
[Maintenance](Maintenance.md), not this module** — this is the explicit boundary
drawn in [ProductSpecification.md](../ProductSpecification.md#calibration-and-asset-management).

## Database tables

`assets` carries `organisation_id`; schedule/event tenant scope is inherited
through mandatory `asset_id` and checked via the parent asset service, as with
Document Management's child tables (see [Database.md](../Database.md#multi-tenancy-baseline)).

- **`assets`** — `id`, `organisation_id`, `asset_tag`, `name`, `asset_type`
  (`measuring_equipment` / `inspection_equipment` / `company_asset`),
  `serial_number`, `location`, `owner_id` → [People](People.md), `status`
  (`in_service` / `out_of_service` / `retired`), `purchase_date`, `created_at`,
  `updated_at`.
- **`calibration_schedules`** — implemented. `id`, `asset_id`, `interval_value`, `interval_unit`
  (`days` / `months` / `years`), `next_due_date`.
- **`calibration_events`** — implemented. `id`, `asset_id`, `performed_at`, `performed_by_id`
  (nullable → `people`) or `performed_by_supplier_id` (nullable →
  [Suppliers](Suppliers.md), for external calibration houses), `certificate_document_id`
  → [Document Management](DocumentManagement.md), `result` (`pass` / `fail` /
  `limited`), `next_due_date`, optional `notes`, creator and timestamp. Full immutable event history is the "complete equipment history"
  required by the spec.
- **`asset_maintenance_schedules`** — `id`, `asset_id`, `interval_value`,
  `interval_unit`, `next_due_date` — scheduled maintenance *for tracked
  equipment/assets specifically* (e.g. a CMM's annual service), distinct from the
  ad hoc, request-driven workflow in [Maintenance](Maintenance.md).

## APIs

Under `/api/v1/calibration`:

- `GET/POST /api/v1/calibration/assets`, `GET/PATCH/DELETE /api/v1/calibration/assets/{id}`
  — CRUD, filterable by type, status, location.
- `GET/POST/PATCH /api/v1/calibration/assets/{id}/schedule` — implemented calibration schedule; one per asset, positive interval, due date updated on an event or set manually.
- `GET/POST /api/v1/calibration/assets/{id}/events` — implemented immutable record/paginated list. An existing certificate document is linked after upload through Document Management, not uploaded through this endpoint. A recorded event computes its due-date snapshot using the schedule interval; only a current/newer calibration updates the schedule, so backfilled history cannot regress its due date.
- `GET/POST/PATCH /api/v1/calibration/assets/{id}/maintenance-schedule` — equipment
  maintenance schedule.
- `GET /api/v1/calibration/due` — implemented backend list of both calibration
  and maintenance due/overdue entries, filtered by the configured reminder
  window or a bounded explicit override, feeding future frontend reminders.

## Workflow

Register an asset → set a calibration schedule (and, separately, an equipment
maintenance schedule if applicable) → reminders surface as the due date approaches →
a calibration event is performed and recorded (in-house or via an external
calibration house) → a certificate is attached → the asset's status and next due date
update → full history is retained indefinitely.

## Relationships to other modules

Per [ProductSpecification.md](../ProductSpecification.md#module-relationships),
**"Assets link to calibration and maintenance"**:

- Certificates are [Document Management](DocumentManagement.md) records.
- Calibration performers and asset owners are [People](People.md); external
  calibration houses are [Suppliers](Suppliers.md).
- [Maintenance](Maintenance.md) requests may reference an `asset_id` here when the
  request concerns tracked equipment, while remaining a distinct workflow for
  ad hoc/production-machinery work.

## Future improvements

- Automated reminder emails as due dates approach.
- Barcode/QR asset tagging and mobile scanning for lookup.
- Configurable calibration interval defaults by asset type.

## Known issues / status

`assets` (creation, editing, listing filterable by type/status/location/search,
and soft deletion, all scoped to the caller's organisation, any active user —
design decision 1) are implemented and tested against real PostgreSQL.
`asset_tag` uniqueness per organisation is enforced with a check-then-insert
plus an `IntegrityError` fallback, matching `products.part_number`'s
precedent. `update_asset`/`delete_asset` use the same per-asset row-locking
pattern as `documents`/`ncrs`, applied proactively from this slice's first
commit (an independent security review confirmed the guard is genuine, not a
gap) rather than found reactively as happened three times during Milestone 4.
Calibration schedules/events are now backend-implemented, with row locks for
concurrent updates and a read-after-lock guard against a soft-deleted asset.
The real-PostgreSQL integration suite and migration downgrade/upgrade were
exercised against a disposable database. Asset maintenance schedules are
backend-implemented; sequential API lifecycle, tenant and deleted-asset
rejections were tested against disposable PostgreSQL, plus unit coverage for
the positive-interval constraint, named unique-error classification and partial
PATCH. The asset row lock serializes writes with soft deletion by design, but
a concurrent PostgreSQL schedule-write/delete test has not yet been run. The
migration passed a fresh-database upgrade/downgrade/upgrade cycle. The `due`
list backend is implemented and tested on disposable PostgreSQL for combined
schedule types, overdue, windows, pagination, tenant isolation and soft deletion.
The asset-list, metadata-detail and calibration-schedule UI are implemented;
the detail indicator uses the UTC calendar date and cannot clear a previously
set due date (calibration PATCH treats null as no change). The asset maintenance
panel supports explicit due-date clearing through its distinct partial PATCH.
The due-list UI shows both obligations, the backend-configured window (or a
bounded override), asset links and pagination; it does not send notifications.
Event UI and end-to-end Compose acceptance are pending. The boundary with
[Maintenance](Maintenance.md) (this module owns *scheduled* calibration/maintenance
of tracked equipment; Maintenance owns *ad hoc requests*, especially for production
machinery) is documented here and in [Maintenance.md](Maintenance.md) to prevent
duplication during implementation.

## Related documents

- [Roadmap.md](../Roadmap.md#m5-calibration-and-asset-management)
- [Milestone 5 plan](../../.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md)
  — full schema, API, and design decisions for this implementation.
- [Maintenance.md](Maintenance.md)
- [Suppliers.md](Suppliers.md)

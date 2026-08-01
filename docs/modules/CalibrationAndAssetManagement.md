# Calibration and Asset Management

**Status: Planned, implementation starting.** Targeted for
[Milestone 5](../Roadmap.md#m5-calibration-and-asset-management); full scope,
schema, API, and design decisions in the
[Milestone 5 plan](../../.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md).
No code exists for this module yet; see [docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

Inspection equipment, measuring equipment and company assets: calibration schedules,
appropriate asset maintenance schedules, certificate storage, reminders, status and
complete equipment history. Examples include micrometers, calipers, CMMs, height
gauges, surface testers and torque equipment. **Production machinery belongs in
[Maintenance](Maintenance.md), not this module** — this is the explicit boundary
drawn in [ProductSpecification.md](../ProductSpecification.md#calibration-and-asset-management).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`assets`** — `id`, `organisation_id`, `asset_tag`, `name`, `asset_type`
  (`measuring_equipment` / `inspection_equipment` / `company_asset`),
  `serial_number`, `location`, `owner_id` → [People](People.md), `status`
  (`in_service` / `out_of_service` / `retired`), `purchase_date`, `created_at`,
  `updated_at`.
- **`calibration_schedules`** — `id`, `asset_id`, `interval_value`, `interval_unit`
  (`days` / `months` / `years`), `next_due_date`.
- **`calibration_events`** — `id`, `asset_id`, `performed_at`, `performed_by_id`
  (nullable → `people`) or `performed_by_supplier_id` (nullable →
  [Suppliers](Suppliers.md), for external calibration houses), `certificate_document_id`
  → [Document Management](DocumentManagement.md), `result` (`pass` / `fail` /
  `limited`), `next_due_date`. Full event history is the "complete equipment history"
  required by the spec.
- **`asset_maintenance_schedules`** — `id`, `asset_id`, `interval_value`,
  `interval_unit`, `next_due_date` — scheduled maintenance *for tracked
  equipment/assets specifically* (e.g. a CMM's annual service), distinct from the
  ad hoc, request-driven workflow in [Maintenance](Maintenance.md).

## Planned APIs

Under `/api/v1/calibration`:

- `GET/POST /api/v1/calibration/assets`, `GET/PATCH/DELETE /api/v1/calibration/assets/{id}`
  — CRUD, filterable by type, status, location.
- `GET/POST /api/v1/calibration/assets/{id}/schedule` — calibration schedule.
- `GET/POST /api/v1/calibration/assets/{id}/events` — record/list calibration
  events (with certificate upload).
- `GET/POST /api/v1/calibration/assets/{id}/maintenance-schedule` — equipment
  maintenance schedule.
- `GET /api/v1/calibration/due` — assets due or overdue for calibration/maintenance,
  feeding reminders and dashboards.

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

Planned only; no schema, API, or UI exists yet. The boundary with
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

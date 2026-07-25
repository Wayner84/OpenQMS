# Maintenance

**Status: Planned.** Not yet implemented — targeted for
[Milestone 6](../Roadmap.md#m6-maintenance). No code exists for this module yet;
see [docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

Separate from calibration: manage maintenance requests through raise, prioritise,
assign owner, attach photos, due date, completion and history. Support urgent work
such as fire doors or machine breakdowns and non-urgent repairs. Dashboards must make
priorities obvious, per
[ProductSpecification.md](../ProductSpecification.md#maintenance).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`maintenance_requests`** — `id`, `organisation_id`, `title`, `description`,
  `asset_id` (nullable → [Calibration and Asset Management](CalibrationAndAssetManagement.md)
  `assets.id`, when the request concerns a tracked asset) or free-text
  `location`/`equipment_description` for untracked production machinery/facilities,
  `priority` (data-driven scale, defaulting to `urgent` / `non_urgent` per the spec's
  examples, via the `configuration` table pattern), `status` (`raised` / `assigned` /
  `in_progress` / `complete`), `raised_by_id` → [People](People.md),
  `assigned_to_id` → `people`, `due_date`, `completed_at`, `created_at`,
  `updated_at`.
- **`maintenance_request_photos`** — `id`, `maintenance_request_id`,
  `document_id` → [Document Management](DocumentManagement.md).
- **`maintenance_history`** — `id`, `maintenance_request_id`, `event_type`
  (`raised` / `assigned` / `status_changed` / `completed`), `note`,
  `changed_by_id` → `people`, `changed_at` — full history required by the spec.

## Planned APIs

Under `/api/v1/maintenance`:

- `GET/POST /api/v1/maintenance/requests`,
  `GET/PATCH/DELETE /api/v1/maintenance/requests/{id}` — CRUD, filterable by
  priority, status, assignee.
- `POST /api/v1/maintenance/requests/{id}/photos` — attach photos.
- `GET /api/v1/maintenance/requests/{id}/history` — full history.
- `GET /api/v1/maintenance/dashboard` — priority-grouped, overdue-highlighted view
  satisfying the spec's "dashboards must make priorities obvious" requirement.

## Workflow

Raise a request → prioritise (urgent vs. non-urgent, or a finer configurable scale) →
assign an owner → track through to completion against a due date → every state
change is recorded in `maintenance_history`. Urgent items (e.g. fire doors, machine
breakdowns) are visually distinguished from non-urgent repairs on the dashboard.

## Relationships to other modules

- May reference an `asset_id` in
  [Calibration and Asset Management](CalibrationAndAssetManagement.md) when the
  request concerns tracked equipment — per the spec, **"Assets link to calibration
  and maintenance."** Requests concerning untracked production machinery/facilities
  use free-text fields instead of forcing an asset record to exist.
  **Production machinery itself is explicitly this module's concern, not
  Calibration's** (see [CalibrationAndAssetManagement.md](CalibrationAndAssetManagement.md)
  for the exact boundary).
- Raisers/assignees are [People](People.md) — **"People link to maintenance and
  actions."**
- Photos are [Document Management](DocumentManagement.md) records.

## Future improvements

- Preventive maintenance scheduling for production machinery (distinct from
  Calibration's scheduled equipment maintenance).
- SLA/overdue alerting (email or in-app).
- Spare parts tracking.

## Known issues / status

Planned only; no schema, API, or UI exists yet. The boundary with
[Calibration and Asset Management](CalibrationAndAssetManagement.md) (that module
owns scheduled calibration/maintenance of tracked measuring/inspection equipment;
this module owns ad hoc requests, especially for production machinery) is documented
in both module files to prevent duplication during implementation.

## Related documents

- [Roadmap.md](../Roadmap.md#m6-maintenance)
- [CalibrationAndAssetManagement.md](CalibrationAndAssetManagement.md)
- [People.md](People.md)

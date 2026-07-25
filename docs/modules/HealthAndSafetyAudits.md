# Health and Safety: Audits

**Status: Planned.** Not yet implemented — targeted for
[Milestone 9](../Roadmap.md#m9-health-and-safety-suite). No code exists for this
module yet; see [docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

Configurable templates for factory, office, fire and environmental audits; findings,
actions, photographs, scheduling and recurring audits, per
[ProductSpecification.md](../ProductSpecification.md#health-and-safety-audits).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`audit_templates`** — `id`, `organisation_id`, `name`, `category` (`factory` /
  `office` / `fire` / `environmental` / `custom`), `questions` (JSONB — a
  configurable checklist structure, satisfying the spec's "configurable templates"
  requirement without a fixed schema per audit type).
- **`audits`** — `id`, `organisation_id`, `template_id`, `scheduled_for`,
  `performed_by_id` → [People](People.md), `status` (`scheduled` / `in_progress` /
  `complete`), `performed_at`, `recurrence_rule` (nullable — e.g. an RRULE-style
  string for recurring audits).
- **`audit_findings`** — `id`, `audit_id`, `question_ref`, `finding_text`,
  `severity`, `photo_document_id` → [Document Management](DocumentManagement.md).
- **`audit_actions`** — `id`, `audit_id` (nullable), `finding_id` (nullable),
  `description`, `owner_id` → `people`, `due_date`, `status` — the same
  action-tracking shape used by [NCR](NCR.md) and
  [Maintenance](Maintenance.md).

## Planned APIs

Under `/api/v1/hse/audits`:

- `GET/POST /api/v1/hse/audits/templates`,
  `GET/PATCH/DELETE /api/v1/hse/audits/templates/{id}` — template CRUD.
- `GET/POST /api/v1/hse/audits`, `GET/PATCH/DELETE /api/v1/hse/audits/{id}` — audit
  CRUD, including scheduling and recurrence.
- `GET/POST /api/v1/hse/audits/{id}/findings` — record findings during/after an
  audit.
- `GET/POST /api/v1/hse/audits/{id}/actions` — raise actions from findings.

## Workflow

Define a configurable template for an audit category → schedule an audit (one-off or
recurring) → perform the audit, recording findings and photographs against the
template's questions → raise actions from findings → track actions to completion,
independent of the parent audit's own completion.

## Relationships to other modules

- Performers and action owners are [People](People.md).
- Photographs are [Document Management](DocumentManagement.md) records.
- Shares its finding/action/scheduling shape conceptually with
  [Health and Safety: Incident Reporting](HealthAndSafetyIncidentReporting.md) and
  [Maintenance](Maintenance.md), though each module owns its own tables (no shared
  cross-module "actions" table — see [Architecture.md](../Architecture.md#module-boundary-pattern)
  on modules not reaching into each other's tables).

## Future improvements

- Mobile-optimised audit capture (offline-friendly field entry).
- Trend dashboards across recurring audits (e.g. recurring finding categories).

## Known issues / status

Planned only; no schema, API, or UI exists yet. Depends on
[People](People.md) and [Document Management](DocumentManagement.md) existing first.

## Related documents

- [Roadmap.md](../Roadmap.md#m9-health-and-safety-suite)
- [HealthAndSafetyIncidentReporting.md](HealthAndSafetyIncidentReporting.md)
- [Maintenance.md](Maintenance.md)

# Health and Safety: Incident Reporting

**Status: Planned.** Not yet implemented — targeted for
[Milestone 9](../Roadmap.md#m9-health-and-safety-suite). No code exists for this
module yet; see [docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

Near misses, incidents and accidents with investigation, root cause, actions,
assigned owners, email notifications and attachments, per
[ProductSpecification.md](../ProductSpecification.md#health-and-safety-incident-reporting).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`incidents`** — `id`, `organisation_id`, `type` (`near_miss` / `incident` /
  `accident`), `reported_by_id` → [People](People.md), `occurred_at`, `location`,
  `description`, `status` (`reported` / `investigating` / `closed`), `severity`,
  `created_at`, `updated_at`.
- **`incident_investigations`** — `id`, `incident_id`, `root_cause_summary`,
  `investigated_by_id` → `people`, `investigated_at`.
- **`incident_actions`** — `id`, `incident_id`, `description`, `owner_id` →
  `people`, `due_date`, `status` — the same action-tracking shape used by
  [NCR](NCR.md) and [Health and Safety: Audits](HealthAndSafetyAudits.md).
- **`incident_attachments`** — `id`, `incident_id`, `document_id` →
  [Document Management](DocumentManagement.md).

## Planned APIs

Under `/api/v1/hse/incidents`:

- `GET/POST /api/v1/hse/incidents`,
  `GET/PATCH/DELETE /api/v1/hse/incidents/{id}` — CRUD, filterable by type, status,
  severity.
- `GET/POST /api/v1/hse/incidents/{id}/investigation` — record investigation and
  root cause.
- `GET/POST /api/v1/hse/incidents/{id}/actions` — manage actions.
- `GET/POST /api/v1/hse/incidents/{id}/attachments` — manage attachments.
- Creation and status changes trigger an email notification to relevant people
  (exact recipient rules configurable — ties into the `configuration` table pattern
  in [Database.md](../Database.md#configuration-table) for email templates).

## Workflow

Report a near miss, incident or accident → investigate and record a root cause →
raise actions with owners and due dates → notify relevant people by email → track to
closure. Severity informs prioritisation but does not gate the workflow.

## Relationships to other modules

- Reporters, investigators and action owners are [People](People.md).
- Attachments are [Document Management](DocumentManagement.md) records.
- Shares its finding/action shape conceptually with
  [Health and Safety: Audits](HealthAndSafetyAudits.md), though each module owns its
  own tables.

## Future improvements

- Configurable notification/escalation rules by severity.
- Regulatory export formats (e.g. RIDDOR-style reporting for relevant jurisdictions).

## Known issues / status

Planned only; no schema, API, or UI exists yet. Depends on
[People](People.md) existing first; email notification delivery depends on a
transactional email mechanism being established (not yet designed — track in
[TODO.md](../TODO.md) when this milestone is scheduled for implementation).

## Related documents

- [Roadmap.md](../Roadmap.md#m9-health-and-safety-suite)
- [HealthAndSafetyAudits.md](HealthAndSafetyAudits.md)
- [Database.md](../Database.md#configuration-table)

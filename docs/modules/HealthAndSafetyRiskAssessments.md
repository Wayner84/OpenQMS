# Health and Safety: Risk Assessments

**Status: Planned.** Not yet implemented — targeted for
[Milestone 9](../Roadmap.md#m9-health-and-safety-suite). No code exists for this
module yet; see [docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

Configurable likelihood/severity scoring and risk matrices, control measures, review
dates and printable reports for both general walkthroughs and specific processes, per
[ProductSpecification.md](../ProductSpecification.md#health-and-safety-risk-assessments).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`risk_matrices`** — `id`, `organisation_id`, `name`, `likelihood_levels`
  (JSONB), `severity_levels` (JSONB), `scoring_formula` (JSONB/text describing how a
  score is derived from likelihood × severity) — fully data-driven per the spec's
  cross-cutting configuration requirement, not a hard-coded matrix.
- **`risk_assessments`** — `id`, `organisation_id`, `title`, `scope`
  (`general_walkthrough` / `specific_process`), `matrix_id` → `risk_matrices`,
  `assessed_by_id` → [People](People.md), `review_date`, `status`, `created_at`,
  `updated_at`.
- **`risk_assessment_hazards`** — `id`, `risk_assessment_id`, `hazard_description`,
  `likelihood`, `severity`, `computed_risk_score` (derived from the assessment's
  `matrix_id` at save time), `control_measures_text`.

## Planned APIs

Under `/api/v1/hse/risk-assessments`:

- `GET/POST /api/v1/hse/risk-matrices`,
  `GET/PATCH/DELETE /api/v1/hse/risk-matrices/{id}` — matrix CRUD.
- `GET/POST /api/v1/hse/risk-assessments`,
  `GET/PATCH/DELETE /api/v1/hse/risk-assessments/{id}` — assessment CRUD,
  filterable by scope, status, review date.
- `GET/POST /api/v1/hse/risk-assessments/{id}/hazards` — manage hazards and control
  measures.
- `GET /api/v1/hse/risk-assessments/{id}/export` — printable report.

## Workflow

Define or select a risk matrix (likelihood/severity levels and scoring formula) →
create an assessment for a general walkthrough or a specific process → record hazards
with likelihood/severity, letting the system compute a risk score from the selected
matrix → record control measures → set a review date → export a printable report.

## Relationships to other modules

- Assessors are [People](People.md).
- Shares its configurable-scoring design question with [NCR](NCR.md) (risk
  implicit in severity/priority) and [Suppliers](Suppliers.md) (`risk_rating`) — see
  [TODO.md](../TODO.md#research-required): whether one shared scoring engine can
  serve all three or whether they need independent models.
- Future linking of hazards to incidents/NCRs that later realised them (not built
  now — see [FutureIdeas.md](../FutureIdeas.md)).

## Future improvements

- Automatic review-date reminders.
- Linking hazards to [Health and Safety: Incident Reporting](HealthAndSafetyIncidentReporting.md)
  records that realised them.

## Known issues / status

Planned only; no schema, API, or UI exists yet. The shared risk-scoring research
question (see [TODO.md](../TODO.md#research-required)) should ideally conclude before
this module, [NCR](NCR.md), and [Suppliers](Suppliers.md) each independently lock in
incompatible scoring schemas.

## Related documents

- [Roadmap.md](../Roadmap.md#m9-health-and-safety-suite)
- [NCR.md](NCR.md)
- [Suppliers.md](Suppliers.md)

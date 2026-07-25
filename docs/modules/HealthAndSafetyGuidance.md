# Health and Safety: Government Guidance

**Status: Planned.** Not yet implemented — targeted for
[Milestone 9](../Roadmap.md#m9-health-and-safety-suite). No code exists for this
module yet; see [docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

Browse HSE guidance. Opening an item downloads the current source so obsolete local
copies are not presented as current, per
[ProductSpecification.md](../ProductSpecification.md#health-and-safety-government-guidance).

## Planned database tables

- **`hse_guidance_items`** — `id`, `title`, `source_url`, `category`,
  `last_synced_at`. **Deliberately not `organisation_id`-scoped** — this is a shared
  catalogue of publicly-published government guidance, identical across every
  self-hosted instance, and is the one documented exception to the "every
  tenant-scoped table carries `organisation_id`" rule in
  [Architecture.md](../Architecture.md#multi-tenancy-strategy) (there is nothing
  tenant-specific about HSE guidance metadata itself).
- **`hse_guidance_bookmarks`** — `id`, `organisation_id`, `person_id` →
  [People](People.md), `guidance_item_id` → `hse_guidance_items.id` — an
  organisation's/person's saved shortcuts, which *are* tenant-scoped.

## Planned APIs

Under `/api/v1/hse/guidance`:

- `GET /api/v1/hse/guidance` — browse/search the catalogue, filterable by category.
- `GET /api/v1/hse/guidance/{id}/open` — resolves to the item's current live source
  (redirect or live fetch-through) rather than ever serving a cached copy, per the
  spec's explicit "not obsolete" requirement.
- `GET/POST/DELETE /api/v1/hse/guidance/bookmarks` — manage the current
  organisation's bookmarks.

## Workflow

A catalogue of guidance items is maintained (seeded and periodically refreshed —
exact maintenance mechanism, manual curation vs. scheduled source checks, is an open
design question, see "Known issues" below) → users browse/search the catalogue →
opening an item always resolves to the live source at open-time, never a stored copy,
so the system can never present something obsolete as current.

## Relationships to other modules

- Bookmarks reference [People](People.md).
- May be referenced as background material from
  [Health and Safety: Risk Assessments](HealthAndSafetyRiskAssessments.md) in the
  future (not built now).

## Future improvements

- Full-text indexing of guidance titles/categories for better search.
- Scheduled staleness checks that flag `source_url`s that no longer resolve.

## Known issues / status

Planned only; no schema, API, or UI exists yet. Open design question flagged for
resolution before implementation: how the guidance catalogue itself is populated and
kept current (manual curation, scheduled scraping/sync, or a static bundled list with
manual updates) — not yet decided, and not scheduled as a
[TODO.md](../TODO.md#research-required) item until this milestone approaches, since
it has no dependency on earlier milestones' outcomes.

## Related documents

- [Roadmap.md](../Roadmap.md#m9-health-and-safety-suite)
- [People.md](People.md)

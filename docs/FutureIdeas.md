# Future Ideas

Concepts that are intentionally **out of scope** for the current roadmap
([Roadmap.md](Roadmap.md)) but worth recording so they are not lost, and so no
milestone accidentally builds toward them prematurely. Nothing here is scheduled;
items move from here into [TODO.md](TODO.md)/[Roadmap.md](Roadmap.md) only when a
deliberate decision is made to schedule them (recorded in
[DecisionLog.md](DecisionLog.md) if architecturally significant).

## Product features named as "future" in the specification

- **Electronic signatures** for Document Management approvals — needs real legal/
  compliance research first (see [TODO.md](TODO.md) Research Required: electronic
  signature legal/compliance requirements).
- **ISO compliance assistance** within Document Management — guided help aligning
  document control with ISO 9001-style requirements.
- **Automatic CMM data imports** for SPC — direct import from coordinate measuring
  machines rather than CSV upload; needs a format survey first (see [TODO.md](TODO.md)
  Research Required: automatic CMM import formats).

## Hosted / SaaS

- **Hosted offering**: one Docker instance per organisation, provisioned and managed
  by an operator-side layer, per
  [Deployment.md](Deployment.md#future-hostedsaas-shape-not-implemented). The
  application schema is already designed to permit this
  ([DecisionLog.md](DecisionLog.md#2026-07-25-multi-tenancy-and-future-saas-shape)),
  but the provisioning/billing/subdomain-routing system itself does not exist and is
  not scheduled.
- **Multi-organisation login** for a single user account (e.g. a consultant working
  across several client instances) — only relevant if/when a shared-instance hosted
  mode is ever chosen over the preferred instance-per-organisation shape.
- **UUID v7 primary keys** — revisit if index locality on very large tables becomes a
  measured problem (see [DecisionLog.md](DecisionLog.md#2026-07-25-primary-key-strategy)).

## Platform capabilities

- **Configurable dashboards and saved filters** across modules (spec-mentioned UX
  goal, tracked as a Future item in [TODO.md](TODO.md) once ≥2 modules exist to
  dashboard over).
- **Application-wide search** across all modules.
- **Cursor-based pagination** if/when offset/limit stops scaling for a given list
  endpoint (see [API.md](API.md#pagination)).
- **Row-level security enforcement** in PostgreSQL for tenant isolation, as a
  defence-in-depth layer beyond application-level `organisation_id` filtering.
- **Soft delete and a formal audit trail** (`deleted_at`, append-only `audit_log`
  table) — planned approach recorded in
  [Database.md](Database.md#soft-delete-and-audit-trail), deferred until Document
  Management (Milestone 2) actually needs it.
- **CI pipeline** (e.g. GitHub Actions running lint/type/test on every change) — not
  requested by Milestone 0; worth adding once there is a remote to run it against and
  a decision to authorise pushing.

## Not in the current specification at all

These are genuinely speculative — recorded only so a future planning pass can
consciously accept or reject them, not because they're expected:

- **Mobile-friendly or native mobile access** beyond responsive web.
- **Internationalisation (i18n)** / multi-language UI.
- **AI-assisted root cause suggestions** for NCR investigations, drawing on historical
  NCR data.
- **Plugin/integration marketplace** for third-party extensions.
- **Direct ERP integrations**, beyond the "integrate with future ERP in mind" data
  modelling already noted for the Products module.
- **Offline mode** for field use (e.g. H&S audits/incident reporting on a factory
  floor with poor connectivity).

## Related documents

- [Roadmap.md](Roadmap.md) — what's actually scheduled and why.
- [TODO.md](TODO.md) — the "Future" and "Research Required" sections track items once
  they're closer to being scheduled.
- [DecisionLog.md](DecisionLog.md) — records the reasoning that keeps these
  deliberately deferred.

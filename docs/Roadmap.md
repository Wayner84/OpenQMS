# Roadmap

openQMS is delivered as a documented, tested platform foundation followed by vertical
module slices, in priority order — not all modules at once (per the product spec's
scope discipline). This roadmap records that order and the reasoning behind it. See
[CurrentStatus.md](CurrentStatus.md) for exactly where the project currently stands
and [TODO.md](TODO.md) for granular tracked tasks within the current milestone.

Milestones are numbered M0, M1, M2, ... Each milestone is expected to be implemented,
tested, and documented before the next begins, per [Contributing.md](Contributing.md).
Scope inside a milestone may be split across multiple commits/batches; a milestone is
"done" when its own acceptance criteria (recorded in its
[.hermes/plans/](../.hermes/plans/) plan document) are met and
[CurrentStatus.md](CurrentStatus.md) reflects it.

## Ordering rationale

Module order is driven by dependency direction from the spec's own module
relationships (Products link to NCR/FAIR/SPC/documents; Suppliers link to NCR; People
link to Suppliers, Maintenance and actions; Assets link to Calibration and
Maintenance; Documents link to all appropriate domain records) — modules that many
others reference are built before the modules that reference them, so later modules
never need to be reworked to add a link that should have existed from the start.

## M0 — Platform foundation (documentation: this batch; implementation: next batch)

No product module. Establishes the backend/frontend skeleton, health/readiness
endpoints, database and organisation/configuration baseline, Docker Compose, and
lint/type/test tooling every later milestone depends on. Full detail:
[.hermes/plans/2026-07-25-milestone-0-foundation.md](../.hermes/plans/2026-07-25-milestone-0-foundation.md).

## M1 — Authentication, Organisations, People

Real user accounts, login, JWT-based auth (see [API.md](API.md#authentication)), and
the People module (shared employees/customers/suppliers/contacts database). Chosen
second because almost every other module needs "who is doing this" (owners, assignees,
approvers) and People is explicitly meant to be reused throughout the system per the
spec. Authentication is scoped to a single organisation per user for now — multi-
organisation login is future SaaS work (see [FutureIdeas.md](FutureIdeas.md)), not
built here.

## M2 — Document Management

Core QMS document control: SOPs, work instructions, forms, policies, revision
history, approval workflow, permissions, electronic acknowledgement, search,
categories/tags, PDF preview, version comparison, configurable numbering. Chosen
third because the spec states documents link to all appropriate domain records —
every later module benefits from documents already existing to link to, rather than
Document Management being retrofitted with links after the fact.

## M3 — Products and Suppliers

Product/component records and approved supplier records. Chosen fourth because NCR,
FAIR and SPC (the next, larger modules) all reference products, and NCR references
suppliers; building these foundational reference-data modules first avoids NCR/FAIR/
SPC needing placeholder or retrofitted product/supplier relationships.

## M4 — NCR

The first major workflow module: internal and supplier NCRs, configurable prefixes,
the Open → Investigate → Containment → Corrective Action → Verification → Close
workflow, 5 Why/Fishbone/8D/10D tools, attachments, actions, owners, due dates, and
PDF export. Chosen fifth (right after its dependencies — People, Products, Suppliers,
Documents — exist) because it is explicitly called out as a major module and a strong
proof point for the platform's workflow, configuration, and reporting capabilities.

## M5 — Calibration and Asset Management

Inspection/measuring equipment and company assets, calibration schedules, certificate
storage, reminders, and equipment history. Chosen sixth: a well-scoped, high-value
module that depends on People (owners) and Documents (certificates) already existing.

## Testing-readiness gates after M5

Before attempting a pilot of controlled CMM programs, add two bounded vertical
slices: **granular role/permission management** first, then the optional
[Program Control](modules/ProgramControl.md) module. This is a deliberate
priority insertion ahead of M6–M10, not a claim that either feature exists yet.
Preserve the completed bootstrap-admin and admin/member baseline, migrate existing
users without widening or silently removing their privileges, enforce every
permission on the backend, and hide unavailable modules/actions in the UI. The
program pilot must use isolated storage and a designated CMM/share, not an
untested production master. Detailed policy design is in
[Permissions.md](Permissions.md). See the testing-readiness decision in
[DecisionLog.md](DecisionLog.md#2026-11-23-testing-readiness-permissions-and-optional-cmm-program-control).

## M6 — Maintenance

Maintenance requests separate from calibration: raise, prioritise, assign, attach
photos, due date, completion, history, urgent-vs-non-urgent dashboards. Chosen
seventh: depends on People and Assets (assets link to both Calibration and
Maintenance per the spec) already existing.

## M7 — FAIR

AS9102 First Article Inspection Reports: PDF/image drawing import, grid/ballooning,
characteristic capture, AS9102 form generation. Chosen eighth: a substantial,
somewhat R&D-heavy module (dimension recognition) that benefits from Products and
Documents already existing; its harder open questions are tracked in
[TODO.md](TODO.md) under Research Required.

## M8 — SPC

CSV measurement import, Cp/Cpk/Pp/Ppk/sigma calculation, histograms, Xbar-R,
Individuals/Moving Range charts, control charts, trend and report export. Chosen
ninth: another major, self-contained module; benefits from Products existing for
measurement-to-part linkage. Automatic CMM import is explicitly future scope (see
[FutureIdeas.md](FutureIdeas.md)), not part of this milestone.

## M9 — Health and Safety suite

Government Guidance browsing (with live re-download so obsolete local copies are
never presented as current), Audits (configurable templates, findings, actions,
photos, scheduling), Incident Reporting (near misses/incidents/accidents,
investigation, root cause, actions, notifications), and Risk Assessments
(configurable likelihood/severity scoring, control measures, review dates, printable
reports). Grouped as one milestone since these four sub-modules share a lot of
structural shape (findings/actions/scheduling) and are lower urgency than the
manufacturing-quality core (NCR, Calibration, FAIR, SPC) for the product's initial
audience.

## M10 — Cross-cutting platform hardening

Configurable dashboards, saved filters, application-wide search, light/dark theming
polish, and the first real steps toward the hosted/SaaS shape described in
[Deployment.md](Deployment.md#future-hostedsaas-shape-not-implemented) if by this
point there is demand for it. Electronic signatures and ISO compliance assistance
(explicitly noted as "future" in the Document Management module description) are
candidates for this milestone or later, re-evaluated against real usage at the time.

## Explicitly out of scope until its milestone

Building ahead of this order (e.g. starting NCR before Document Management, or any
SaaS/multi-organisation UI before M10) is a deviation from this roadmap and should not
happen without a new [DecisionLog.md](DecisionLog.md) entry explaining why the order
changed.

## Related documents

- [CurrentStatus.md](CurrentStatus.md) — current milestone and real progress.
- [TODO.md](TODO.md) — granular tasks within the current milestone.
- [DecisionLog.md](DecisionLog.md) — the Milestone 0 scope boundary decision.
- [docs/modules/](modules/) — full detail per module, all currently status: Planned.

# TODO

Tracked tasks for openQMS, organised High / Medium / Low / Future / Research
Required, per [ProductSpecification.md](ProductSpecification.md). Every item records
a description, its dependencies, an estimated complexity (S/M/L/XL), and a status.
Kept current in the same commit as affected work, per
[Contributing.md](Contributing.md). See [Roadmap.md](Roadmap.md) for the milestone
narrative this list implements and [CurrentStatus.md](CurrentStatus.md) for the
current milestone.

Status values: `Not Started`, `In Progress`, `Done`.

## High Priority — Milestone 0 (Platform Foundation)

Full scope and acceptance criteria:
[.hermes/plans/2026-07-25-milestone-0-foundation.md](../.hermes/plans/2026-07-25-milestone-0-foundation.md).

1. **Backend project skeleton** — FastAPI app factory, `core/config.py` (typed
   `Settings`), `core/db.py` (async engine/session), `core/logging.py` (structured
   JSON logging), directory layout per [Architecture.md](Architecture.md).
   Dependencies: none. Complexity: **M**. Status: Done.
2. **Health and readiness endpoints** — `GET /api/v1/health`,
   `GET /api/v1/health/ready` per [API.md](API.md). Dependencies: Task 1.
   Complexity: **S**. Status: Done.
3. **Alembic setup + organisations/configuration baseline** — initialise Alembic,
   write the migration creating `organisations` and `configuration` tables plus a
   data migration seeding one organisation row, per [Database.md](Database.md).
   Dependencies: Task 1. Complexity: **M**. Status: Done.
4. **Backend tooling and tests** — ruff, mypy, pytest configuration; unit tests for
   config/health logic, integration test for `/health/ready` against real
   PostgreSQL, written test-first. Dependencies: Tasks 1–3. Complexity: **M**.
   Status: Done.
5. **Frontend project skeleton** — Vite + React + TypeScript scaffold, layout shell,
   theme provider (light/dark), per [Architecture.md](Architecture.md). Dependencies:
   none. Complexity: **M**. Status: Done.
6. **Frontend API health display** — typed `shared/api/client.ts` wrapper, one
   screen that calls `/api/v1/health` (and `/health/ready`) and displays live status.
   Dependencies: Tasks 2, 5. Complexity: **S**. Status: Done.
7. **Frontend tooling and tests** — ESLint, Prettier, Vitest + React Testing Library;
   at least one component test for the health display, written test-first.
   Dependencies: Tasks 5–6. Complexity: **S**. Status: Done.
8. **Docker Compose stack** — `backend/Dockerfile`, `frontend/Dockerfile`,
   `docker-compose.yml`, `.env.example`, named volumes, health checks, per
   [Docker.md](Docker.md). Dependencies: Tasks 1–7. Complexity: **M**.
   Status: Done.
9. **Docker smoke test** — verify the full smoke test sequence in
   [Docker.md](Docker.md#smoke-test-definition), including volume persistence across
   `down`/`up`. Dependencies: Task 8. Complexity: **S**. Status: Done.
10. **Close out Milestone 0 documentation** — update
    [CurrentStatus.md](CurrentStatus.md), this file, and check off acceptance
    criteria in the Milestone 0 plan once verified. Dependencies: Tasks 1–9.
    Complexity: **S**. Status: Done.

## Medium Priority — Milestone 1 (Auth, Organisations, People) — COMPLETE

Full scope and acceptance criteria (all checked off):
[.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md](../.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md).

11. **Authentication (JWT)** — user model, password hashing (Argon2id), login
    endpoint, `Depends()`-based current-user resolution, scoped to one organisation
    per user. Dependencies: Milestone 0 complete. Complexity: **L**. Status: Done
    (backend and frontend both implemented and tested).
12. **User management** — create/list/deactivate users within the seeded
    organisation; roles/permissions model (at least a basic admin/member
    distinction). Dependencies: Task 11. Complexity: **M**. Status: Done
    (backend and frontend both implemented and tested).
13. **People module** — shared employees/customers/suppliers/contacts records per
    [docs/modules/People.md](modules/People.md); multiple contacts per
    customer/supplier. Dependencies: Task 11 (owner/creator attribution),
    Milestone 0's `organisation_id` pattern. Complexity: **L**. Status: Done
    (backend and frontend both implemented and tested).

Milestone 1 closeout (final validation batch, 2026-07-26): full gate re-run, a real
upgrade/downgrade/upgrade migration cycle, dependency audits, an independent
security/tenant-isolation review, and a real browser-driven Docker Compose smoke
test — all passed, with two defects found and fixed test-first along the way (a
login timing side-channel and a React StrictMode `mountedRef` bug affecting all three
Milestone 1 data-table pages). See [CurrentStatus.md](CurrentStatus.md) and
[DecisionLog.md](DecisionLog.md#2026-07-26-milestone-1-closeout-login-timing-side-channel-and-a-react-strictmode-mountedref-bug)
for full detail. Next: Milestone 2 (Document Management) — see below.

## Medium Priority — Milestone 2 (Document Management) — COMPLETE

Full scope and acceptance criteria (all checked off):
[.hermes/plans/2026-07-26-milestone-2-document-management.md](../.hermes/plans/2026-07-26-milestone-2-document-management.md).

14. **Document Management module** — see
    [docs/modules/DocumentManagement.md](modules/DocumentManagement.md). Categories,
    tags, documents, immutable versions, configurable numbering, approval/rejection
    workflow, acknowledgements, search/filtering, permissions, secure upload/download/
    preview, version comparison; backend and frontend. Dependencies: Milestone 1.
    Complexity: **XL**. Status: Done (backend and frontend both implemented and
    tested; closed out 2026-07-28 with a full gate re-run, the real-PostgreSQL
    integration suite, a migration upgrade/downgrade/upgrade cycle, dependency
    audits, and a browser-driven Docker Compose smoke test with a persistence-restart
    check — see [CurrentStatus.md](CurrentStatus.md)).

Milestone 2 closeout (2026-07-28): full gate re-run (backend and frontend), the
64-test real-PostgreSQL integration suite (a disposable PostgreSQL 16 container, not
the shared dev database), a real upgrade → downgrade → upgrade cycle for the complete
six-revision migration chain, re-verified dependency audits (no new findings), and a
real headless-Chromium browser walkthrough of the full Document Management workflow
through `docker compose up --build`, surviving a `down`/`up` restart with the
uploaded file's own bytes intact. No new defects found. See
[CurrentStatus.md](CurrentStatus.md) for full detail. Next: Milestone 3 (Products and
Suppliers) — see below.

## Medium Priority — Milestone 3 (Products and Suppliers) — COMPLETE

Full scope and acceptance criteria (all checked off):
[.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md](../.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md).

15. **Products module** — see [docs/modules/Products.md](modules/Products.md).
    Dependencies: Milestone 1, Task 14 (document links), Task 16 (supplier links).
    Complexity: **L**. Status: Done (backend and frontend both implemented and tested).
16. **Suppliers module** — see [docs/modules/Suppliers.md](modules/Suppliers.md).
    Dependencies: Milestone 1, Task 13 (people/contacts). Complexity: **M**.
    Status: Done (backend and frontend both implemented and tested).

Milestone 3 closeout (2026-07-29): full gate re-run (backend and frontend), the
274-test real-PostgreSQL integration suite, a real upgrade → downgrade → upgrade
cycle for the complete eight-revision migration chain, re-verified dependency
audits (no new findings), an independent security/tenant-isolation review that
found and fixed test-first a TOCTOU race in three Products check-then-insert paths,
and a real headless-Chromium browser walkthrough of the full Suppliers/Products
workflow through `docker compose up --build`, surviving a `down`/`up` restart. See
[CurrentStatus.md](CurrentStatus.md) and
[DecisionLog.md](DecisionLog.md#2026-07-29-milestone-3-closeout-products-check-then-insert-races-mapped-to-clean-conflicts)
for full detail. Next: Milestone 4 (NCR) — see below.

Milestone 4 closeout (2026-07-30): full gate re-run (backend and frontend), the
123-test real-PostgreSQL integration suite (245 unit + 123 integration backend;
278 frontend), a real upgrade → downgrade → upgrade cycle for the complete
12-revision migration chain, re-verified dependency audits (no new findings), a
final holistic independent security/tenant-isolation review that found and
fixed test-first a missing frozen-once-closed guard on `update_ncr` (a closed
NCR's own metadata could be silently rewritten after closure), and a real
headless-Chromium browser walkthrough of the full NCR workflow (internal +
supplier NCR, action, investigation tool, attachment, full transition to
Closed blocked-then-unblocked by an open action, PDF export, Suppliers
NCR-history) through `docker compose up --build`, surviving a `down`/`up`
restart. See [CurrentStatus.md](CurrentStatus.md) and
[DecisionLog.md](DecisionLog.md#2026-07-30-milestone-4-closeout-update_ncr-had-no-frozen-once-closed-guard)
for full detail. Next: Milestone 5 (Calibration and Asset Management) — see
below.

## Medium Priority — Milestone 4 (NCR) — COMPLETE

Full scope and acceptance criteria (all checked off):
[.hermes/plans/2026-07-29-milestone-4-ncr.md](../.hermes/plans/2026-07-29-milestone-4-ncr.md).

17. **NCR module** — see [docs/modules/NCR.md](modules/NCR.md). Dependencies:
    Tasks 13, 14, 15, 16 (all complete). Complexity: **XL**. Status: Done
    (backend and frontend both implemented and tested; Milestone 4 closeout
    verification complete).

## Medium Priority — Milestone 5 (Calibration and Asset Management) — IN PROGRESS

Full scope and acceptance criteria:
[.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md](../.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md).

18. **Calibration and Asset Management module** — see
    [docs/modules/CalibrationAndAssetManagement.md](modules/CalibrationAndAssetManagement.md).
    Dependencies: Tasks 13, 14 (both complete). Complexity: **L**. Status: In
    Progress (`assets` CRUD and calibration schedules/events implemented and
    tested in the backend; asset maintenance schedules and the `due` endpoint
    backend implemented; asset-list/create, metadata-detail and calibration-
    schedule, asset-maintenance, due-list and event frontend implemented;
    full-stack acceptance pending).

## High Priority — Testing readiness after Milestone 5 (planned)

TR1. **Granular user permissions and role templates** — retain the bootstrap admin
    and last-admin guard; add organisation-scoped, admin-managed permission grants
    for module visibility and resource actions (e.g. `documents.read` without
    `documents.revise`), a server-side policy dependency on every affected route,
    and a capabilities-driven frontend that hides unavailable navigation and
    controls. Migrate existing accounts without breaking their current access;
    test direct-API bypass, cross-organisation isolation, self-escalation and
    revocation. Dependencies: M1 and existing module endpoints; complete M5 first
    unless a separate documented priority change is made. Complexity: **XL**.
    Status: Not Started.
TR2. **Optional CMM Program Control** — organisation-level Settings toggle;
    immutable binary revisions with SHA-256, selected approver, audited decision,
    approved-only atomic publication to a configured CMM-accessible root, separate
    read-only master and writable run-data path, integrity/recovery and backup
    checks. Pilot on an isolated target before production share use. See
    [modules/ProgramControl.md](modules/ProgramControl.md). Dependencies: TR1,
    Document Management storage conventions, PostgreSQL and a confirmed CMM/share
    topology. Complexity: **XL**. Status: Not Started.

## Low Priority — Later modules (Milestones 6–9)
19. **Maintenance module** — see [docs/modules/Maintenance.md](modules/Maintenance.md).
    Dependencies: Tasks 13, 18 (assets). Complexity: **M**. Status: Not Started.
20. **FAIR module** — see [docs/modules/FAIR.md](modules/FAIR.md). Dependencies:
    Tasks 14, 15; see also Research Required below. Complexity: **XL**.
    Status: Not Started.
21. **SPC module** — see [docs/modules/SPC.md](modules/SPC.md). Dependencies:
    Task 15. Complexity: **XL**. Status: Not Started.
22. **Health and Safety: Government Guidance** — see
    [docs/modules/HealthAndSafetyGuidance.md](modules/HealthAndSafetyGuidance.md).
    Dependencies: Milestone 1. Complexity: **S**. Status: Not Started.
23. **Health and Safety: Audits** — see
    [docs/modules/HealthAndSafetyAudits.md](modules/HealthAndSafetyAudits.md).
    Dependencies: Tasks 13, 14. Complexity: **L**. Status: Not Started.
24. **Health and Safety: Incident Reporting** — see
    [docs/modules/HealthAndSafetyIncidentReporting.md](modules/HealthAndSafetyIncidentReporting.md).
    Dependencies: Task 13. Complexity: **M**. Status: Not Started.
25. **Health and Safety: Risk Assessments** — see
    [docs/modules/HealthAndSafetyRiskAssessments.md](modules/HealthAndSafetyRiskAssessments.md).
    Dependencies: Task 13. Complexity: **M**. Status: Not Started.

## Future

26. **Configurable dashboards and saved filters** — cross-cutting UX capability
    described in the spec's user experience section. Dependencies: at least two
    modules implemented (to have real data to filter/dashboard). Complexity: **L**.
    Status: Not Started.
27. **Application-wide search** — cross-module search. Dependencies: several modules
    implemented. Complexity: **L**. Status: Not Started.
28. **Electronic signatures** — noted as future in Document Management module
    description. Dependencies: Document Management (Task 14). Complexity: **L**.
    Status: Not Started.
29. **ISO compliance assistance** — noted as future in Document Management module
    description. Dependencies: Document Management (Task 14). Complexity: **L**.
    Status: Not Started.
30. **Automatic CMM data import for SPC** — noted as future in the SPC module
    description. Dependencies: SPC module (Task 21). Complexity: **L**.
    Status: Not Started.
31. **Hosted/SaaS provisioning layer** — the operator-side system that would run one
    Docker instance per hosted organisation, per
    [Deployment.md](Deployment.md#future-hostedsaas-shape-not-implemented).
    Dependencies: sustained self-hosted usage validating the product first.
    Complexity: **XL**. Status: Not Started.
32. **Mobile-friendly / native mobile access** — not in the current spec; candidate
    future idea. Dependencies: core modules stable. Complexity: **XL**.
    Status: Not Started.
33. **Internationalisation (i18n)** — not in the current spec; candidate future idea.
    Dependencies: none technical, but touches every module's UI. Complexity: **L**.
    Status: Not Started.

## Research Required

34. **FAIR dimension recognition from imported PDFs/images** — how to reliably grid,
    recognise, and auto-number dimensions/balloons on imported drawings; likely
    needs OCR/CV research and a fallback manual-ballooning UX. Dependencies: none
    yet (research can start independently). Complexity: **L** (research spike).
    Status: Not Started.
35. **Automatic CMM import formats** — survey common CMM export formats (e.g. DMIS,
    vendor-specific CSV/XML) to design a durable import abstraction before building
    Task 30. Dependencies: none yet. Complexity: **M** (research spike).
    Status: Not Started.
36. **Electronic signature legal/compliance requirements** — research what
    21 CFR Part 11 / eIDAS-style compliance would actually require before building
    Task 28, so the feature is designed correctly the first time. Dependencies:
    none yet. Complexity: **M** (research spike). Status: Not Started.
37. **Configurable risk scoring model design** — the spec requires risk scoring to be
    data-driven (NCR risk, supplier risk, H&S risk assessments all need scoring);
    research whether one shared configurable scoring engine can serve all three or
    whether they need independent models, before Tasks 17/23/25/16 lock in a schema.
    Dependencies: none yet, but should conclude before Task 17. Complexity: **M**
    (research spike). Status: Not Started.
38. **Cursor-based pagination need assessment** — revisit whether offset/limit
    pagination (current default, see [API.md](API.md#pagination)) remains adequate
    once real data volumes exist, particularly for NCR/SPC/Document lists.
    Dependencies: at least one module with real usage data. Complexity: **S**
    (research spike). Status: Not Started.

## Related documents

- [Roadmap.md](Roadmap.md) — milestone narrative these tasks implement.
- [CurrentStatus.md](CurrentStatus.md) — current milestone and truthful progress.
- [DecisionLog.md](DecisionLog.md) — architectural decisions already made.

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
   Dependencies: none. Complexity: **M**. Status: Not Started.
2. **Health and readiness endpoints** — `GET /api/v1/health`,
   `GET /api/v1/health/ready` per [API.md](API.md). Dependencies: Task 1.
   Complexity: **S**. Status: Not Started.
3. **Alembic setup + organisations/configuration baseline** — initialise Alembic,
   write the migration creating `organisations` and `configuration` tables plus a
   data migration seeding one organisation row, per [Database.md](Database.md).
   Dependencies: Task 1. Complexity: **M**. Status: Not Started.
4. **Backend tooling and tests** — ruff, mypy, pytest configuration; unit tests for
   config/health logic, integration test for `/health/ready` against real
   PostgreSQL, written test-first. Dependencies: Tasks 1–3. Complexity: **M**.
   Status: Not Started.
5. **Frontend project skeleton** — Vite + React + TypeScript scaffold, routing/layout
   shell, theme provider (light/dark), per [Architecture.md](Architecture.md).
   Dependencies: none. Complexity: **M**. Status: Not Started.
6. **Frontend API health display** — typed `shared/api/client.ts` wrapper, one
   screen that calls `/api/v1/health` (and `/health/ready`) and displays live status.
   Dependencies: Tasks 2, 5. Complexity: **S**. Status: Not Started.
7. **Frontend tooling and tests** — ESLint, Prettier, Vitest + React Testing Library;
   at least one component test for the health display, written test-first.
   Dependencies: Tasks 5–6. Complexity: **S**. Status: Not Started.
8. **Docker Compose stack** — `backend/Dockerfile`, `frontend/Dockerfile`,
   `docker-compose.yml`, `.env.example`, named volumes, health checks, per
   [Docker.md](Docker.md). Dependencies: Tasks 1–7. Complexity: **M**.
   Status: Not Started.
9. **Docker smoke test** — verify the full smoke test sequence in
   [Docker.md](Docker.md#smoke-test-definition), including volume persistence across
   `down`/`up`. Dependencies: Task 8. Complexity: **S**. Status: Not Started.
10. **Close out Milestone 0 documentation** — update
    [CurrentStatus.md](CurrentStatus.md), this file, and check off acceptance
    criteria in the Milestone 0 plan once verified. Dependencies: Tasks 1–9.
    Complexity: **S**. Status: Not Started.

## Medium Priority — Milestone 1 (Auth, Organisations, People)

11. **Authentication (JWT)** — user model, password hashing (Argon2id), login
    endpoint, `Depends()`-based current-user resolution, scoped to one organisation
    per user. Dependencies: Milestone 0 complete. Complexity: **L**.
    Status: Not Started.
12. **User management** — create/list/deactivate users within the seeded
    organisation; roles/permissions model (at least a basic admin/member
    distinction). Dependencies: Task 11. Complexity: **M**. Status: Not Started.
13. **People module** — shared employees/customers/suppliers/contacts records per
    [docs/modules/People.md](modules/People.md); multiple contacts per
    customer/supplier. Dependencies: Task 11 (owner/creator attribution),
    Milestone 0's `organisation_id` pattern. Complexity: **L**. Status: Not Started.

## Low Priority — Later modules (Milestones 2–9)

14. **Document Management module** — see
    [docs/modules/DocumentManagement.md](modules/DocumentManagement.md).
    Dependencies: Milestone 1. Complexity: **XL**. Status: Not Started.
15. **Products module** — see [docs/modules/Products.md](modules/Products.md).
    Dependencies: Milestone 1, Task 14 (document links). Complexity: **L**.
    Status: Not Started.
16. **Suppliers module** — see [docs/modules/Suppliers.md](modules/Suppliers.md).
    Dependencies: Milestone 1, Task 13 (people/contacts). Complexity: **M**.
    Status: Not Started.
17. **NCR module** — see [docs/modules/NCR.md](modules/NCR.md). Dependencies:
    Tasks 13, 14, 15, 16. Complexity: **XL**. Status: Not Started.
18. **Calibration and Asset Management module** — see
    [docs/modules/CalibrationAndAssetManagement.md](modules/CalibrationAndAssetManagement.md).
    Dependencies: Tasks 13, 14. Complexity: **L**. Status: Not Started.
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

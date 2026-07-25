# openQMS

openQMS is an open-source, Docker-first quality management system for organisations
ranging from one person to hundreds of users — a clean, modern, fast, intuitive and
highly configurable alternative to expensive systems such as Q-Pulse, ETQ,
MasterControl, QT9, Minitab (for routine SPC), and commercial FAIR tools.

It deliberately avoids becoming an overcomplicated ERP: simple workflows, modularity,
minimal clicks, and integration between modules instead of duplicated data.

Full product vision: [docs/ProductSpecification.md](docs/ProductSpecification.md).

## Project status

**Planning complete for Milestone 0; no application code has been written yet.** This
repository currently contains the documentation-first architecture and implementation
plan for the platform foundation. See [docs/CurrentStatus.md](docs/CurrentStatus.md)
for the truthful, up-to-date state and
[.hermes/plans/2026-07-25-milestone-0-foundation.md](.hermes/plans/2026-07-25-milestone-0-foundation.md)
for exactly what the next batch of work will implement.

## Stack

- **Backend:** Python (FastAPI), SQLAlchemy 2.0 (async) + Alembic, PostgreSQL.
- **Frontend:** React + TypeScript, built with Vite.
- **Orchestration:** Docker Compose, one command to start the full stack.

Reasoning for these choices: [docs/DecisionLog.md](docs/DecisionLog.md). Full system
design: [docs/Architecture.md](docs/Architecture.md).

## Getting started

Once Milestone 0 is implemented (see status above), the full stack will start with:

```
cp .env.example .env
docker compose up --build
```

Backend at `http://localhost:8000` (interactive API docs at `/docs`), frontend at
`http://localhost:5173`. Full detail: [docs/Docker.md](docs/Docker.md).

## Modules

openQMS is delivered as a documented, tested platform foundation followed by vertical
module slices, in roadmap order — not all at once. See [docs/Roadmap.md](docs/Roadmap.md)
for delivery order and reasoning. Every module has a planning document under
[docs/modules/](docs/modules/), each currently labelled `Status: Planned` since no
module has been implemented yet:

- [Document Management](docs/modules/DocumentManagement.md)
- [Calibration and Asset Management](docs/modules/CalibrationAndAssetManagement.md)
- [People](docs/modules/People.md)
- [Products](docs/modules/Products.md)
- [Suppliers](docs/modules/Suppliers.md)
- [NCR](docs/modules/NCR.md)
- [FAIR](docs/modules/FAIR.md)
- [SPC](docs/modules/SPC.md)
- [Health and Safety: Government Guidance](docs/modules/HealthAndSafetyGuidance.md)
- [Health and Safety: Audits](docs/modules/HealthAndSafetyAudits.md)
- [Health and Safety: Incident Reporting](docs/modules/HealthAndSafetyIncidentReporting.md)
- [Health and Safety: Risk Assessments](docs/modules/HealthAndSafetyRiskAssessments.md)
- [Maintenance](docs/modules/Maintenance.md)

## Documentation

| Document | Purpose |
|---|---|
| [docs/Architecture.md](docs/Architecture.md) | System design, layering, module boundaries, multi-tenancy |
| [docs/Roadmap.md](docs/Roadmap.md) | Milestone and module delivery order |
| [docs/CurrentStatus.md](docs/CurrentStatus.md) | Truthful current state, in-progress work, blockers |
| [docs/FutureIdeas.md](docs/FutureIdeas.md) | Deliberately deferred ideas |
| [docs/CodingStandards.md](docs/CodingStandards.md) | Code conventions, testing, tooling commands |
| [docs/Database.md](docs/Database.md) | Schema conventions, migrations, multi-tenancy baseline |
| [docs/API.md](docs/API.md) | REST conventions, versioning, endpoint contracts |
| [docs/Docker.md](docs/Docker.md) | Compose services, volumes, smoke test |
| [docs/Deployment.md](docs/Deployment.md) | Self-hosting and future hosted deployment |
| [docs/Contributing.md](docs/Contributing.md) | Workflow: test-first, commits, session continuity |
| [docs/TODO.md](docs/TODO.md) | Tracked tasks by priority, with dependencies and complexity |
| [docs/DecisionLog.md](docs/DecisionLog.md) | Architectural decisions: problem, options, choice, trade-offs |
| [docs/modules/](docs/modules/) | One document per product module |

## Autonomous development

This repository is developed over a long period by autonomous coding agents. See
[CLAUDE.md](CLAUDE.md) for the operating contract, and
[docs/ProductSpecification.md](docs/ProductSpecification.md#autonomous-development-contract)
for the source requirement. In short: every commit explains its reason, every feature
is documented alongside the code that implements it, and
[docs/CurrentStatus.md](docs/CurrentStatus.md)/[docs/TODO.md](docs/TODO.md)/
[docs/DecisionLog.md](docs/DecisionLog.md) stay current so any session — human or
agent — can pick the project back up cold.

## License

Not yet chosen. Recording this here so it is visibly open rather than silently
assumed; a license decision is expected before or alongside the first public release
and will be recorded in [docs/DecisionLog.md](docs/DecisionLog.md) when made.

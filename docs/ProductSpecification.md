# openQMS Product Specification

## Vision

openQMS is an open-source, Docker-first quality management system for organisations ranging from one person to hundreds of users. It should be a clean, modern, fast, intuitive and highly configurable alternative to expensive systems such as Q-Pulse, ETQ, MasterControl, QT9, Minitab for routine SPC, and commercial FAIR tools.

The product must avoid becoming an overcomplicated ERP. Prefer simple workflows, modularity, minimal clicks and integrations between modules instead of duplicated data.

## Autonomous development contract

This repository is expected to be developed over a long period by autonomous coding agents. Maintainability, documentation and recoverability are as important as code.

- Save progress continuously in sensible Git commits after every completed feature or milestone.
- Commit messages must explain the reason for a change.
- Every meaningful feature must document what was built, why, how it works, and what remains.
- No feature may exist without documentation.
- Keep `docs/CurrentStatus.md`, `docs/TODO.md` and `docs/DecisionLog.md` current in the same commit as affected work.
- Keep the repository continuable after session endings, crashes, interrupted conversations, model changes and fresh clones.
- Do not push or rewrite history unless explicitly authorised.

## Required documentation

Maintain at least:

- `README.md`
- `docs/Architecture.md`
- `docs/Roadmap.md`
- `docs/CurrentStatus.md`
- `docs/FutureIdeas.md`
- `docs/CodingStandards.md`
- `docs/Database.md`
- `docs/API.md`
- `docs/Docker.md`
- `docs/Deployment.md`
- `docs/Contributing.md`
- `docs/TODO.md`
- `docs/DecisionLog.md`
- one document per product module under `docs/modules/`

Each module document must cover purpose, database tables, APIs, workflow, relationships, future improvements and known issues.

`CurrentStatus.md` must always cover the current milestone, completed work, work in progress, known bugs, next recommended tasks, future ideas and blockers.

`TODO.md` must be organised into High Priority, Medium Priority, Low Priority, Future and Research Required. Every task records description, dependencies, estimated complexity and completion status.

Every major architectural entry in `DecisionLog.md` records the problem, options considered, chosen option and reason, pros and cons.

## Technology and deployment constraints

- Backend: Python with clear type hints, modular architecture and dependency injection where sensible.
- Frontend: a modern maintainable framework (React or Vue are acceptable); record the decision.
- Database: PostgreSQL in Docker; SQLite may be supported for local development if it does not compromise correctness.
- ORM and schema migrations are required.
- Tests: unit tests and appropriate integration tests. New behaviour follows test-first RED-GREEN-REFACTOR.
- Public functions require meaningful documentation. Avoid giant files and hard-coded business rules.
- The complete stack must start with one Docker Compose command and use persistent volumes.
- Self-hosting is free, simple and fully supported.
- The design must permit future hosted/SaaS deployment without implementing SaaS features now: organisation/tenant separation must be possible, authentication must later support multiple organisations, and configuration must be database driven. A likely future hosted shape is multiple Docker instances managed on a server.

## Cross-cutting configuration

Business behaviour should be data-driven wherever practical, including NCR and document prefixes, issue numbering, document numbering, risk scoring, supplier requirements, email templates, storage locations, folder structures, approval workflows, audit frequencies and calibration intervals.

## Modules

### Document Management

Core QMS document control: SOPs, work instructions, forms, policies, controlled documents, revision history, approval workflow, change history, permissions, electronic acknowledgement, search, categories, tags, PDF preview, version comparison and configurable numbering. Future: electronic signatures and ISO compliance assistance.

### Calibration and Asset Management

Inspection equipment, measuring equipment and company assets; calibration schedules, appropriate asset maintenance schedules, certificate storage, reminders, status and complete equipment history. Examples include micrometers, calipers, CMMs, height gauges, surface testers and torque equipment. Production machinery belongs in Maintenance, not this module.

### People

A shared database of employees, customers, suppliers and contacts with phone, email, role, department, notes and relationships. Support multiple contacts per customer and supplier. Reuse people throughout the system.

### Products

Central records for internal products, purchased products, assemblies and components. Store part number, description, revision, images, CAD/drawing/specification links, categories, manufacturing notes and supplier relationships. Integrate products with NCR, FAIR, SPC, documents and suppliers, with future ERP integrations in mind.

### Suppliers

Approved supplier records, certificates, addresses, contacts, performance, NCR history, approval status, expiry reminders, ISO and other accreditation, risk rating and preferred supplier status.

### NCR

A major module supporting internal and supplier NCRs with configurable prefixes (defaults `NCR` and `SNCR`). Workflow: Open, Investigate, Containment, Corrective Action, Verification, Close. Include 5 Why, Fishbone/Ishikawa, 8D and 10D tools, attachments, actions, owners, due dates and completion tracking. An NCR cannot close while actions are open. Export incomplete NCRs with blank printable sections and completed NCRs as polished PDF reports.

### FAIR

AS9102 First Article Inspection Reports. Import PDF/image drawings, apply a grid, recognise dimensions, automatically number balloons, store characteristics (nominal, tolerance, measured value, result), and generate AS9102 forms. Aim for useful commercial-tool capability with a clean UI.

### SPC

A major module that imports CSV measurements and calculates Cp, Cpk, Pp, Ppk and sigma. Provide histograms, Xbar-R, Individuals/Moving Range charts, control charts, trends and report export. Keep it simple for daily use but powerful enough to replace Minitab for routine SPC. Document future automatic CMM imports.

### Health and Safety: Government Guidance

Browse HSE guidance. Opening an item downloads the current source so obsolete local copies are not presented as current.

### Health and Safety: Audits

Configurable templates for factory, office, fire and environmental audits; findings, actions, photographs, scheduling and recurring audits.

### Health and Safety: Incident Reporting

Near misses, incidents and accidents with investigation, root cause, actions, assigned owners, email notifications and attachments.

### Health and Safety: Risk Assessments

Configurable likelihood/severity scoring and risk matrices, control measures, review dates and printable reports for both general walkthroughs and specific processes.

### Maintenance

Separate from calibration. Manage maintenance requests through raise, prioritise, assign owner, attach photos, due date, completion and history. Support urgent work such as fire doors or machine breakdowns and non-urgent repairs. Dashboards must make priorities obvious.

## Module relationships

Prefer references to canonical records instead of duplication:

- Products link to NCR, FAIR, SPC and documents.
- Suppliers link to NCR; people link to suppliers.
- People link to maintenance and actions.
- Assets link to calibration and maintenance.
- Documents link to all appropriate domain records.

## User experience

- Modern, clean, fast and responsive.
- Consistent navigation and minimal clicks.
- Light and dark modes.
- Powerful filtering and saved filters.
- Configurable dashboards.
- Search throughout the application.

## Scope discipline

Do not build every module at once. Establish a documented, tested platform foundation and deliver vertical slices in roadmap order. Every design decision should favour extensibility, maintainability, simple operation and excellent handoff documentation.
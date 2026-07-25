# People

**Status: Implemented** (Milestone 1). See
[.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md](../../.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#3-people-module)
for the implementation plan and [docs/CurrentStatus.md](../CurrentStatus.md) for
current verification status.

## Purpose

A shared database of employees, customers, suppliers and contacts, reused throughout
the system instead of each module keeping its own contact records. Stores phone,
email, role, department and notes, and supports multiple contacts per customer and
supplier per [ProductSpecification.md](../ProductSpecification.md#people).

## Database tables

Implemented by
`backend/alembic/versions/f151a2c68c12_add_companies_and_people_tables.py`. Both
tables carry `organisation_id` per
[Database.md](../Database.md#multi-tenancy-baseline).

- **`companies`** (`backend/app/modules/people/models.py`) — `id`, `organisation_id`,
  `name`, `type` (native PostgreSQL ENUM `customer` / `supplier` / `other`),
  `address`, `phone`, `general_email`, `notes`, `created_by_id`/`updated_by_id` (FK →
  `users.id`, nullable), `created_at`, `updated_at`. A lightweight
  external-organisation record; the [Suppliers](Suppliers.md) module (not yet built)
  is expected to attach supplier-specific fields to a `companies` row rather than
  duplicating name/address/contact data.
- **`people`** — `id`, `organisation_id`, `company_id` (nullable FK →
  `companies.id`), `first_name`, `last_name`, `email` (nullable), `phone`, `role`,
  `department`, `notes`, `is_employee` (bool), `created_by_id`/`updated_by_id`,
  `created_at`, `updated_at`. A null `company_id` represents an internal employee; a
  populated one represents a contact at a customer or supplier company — this is how
  "multiple contacts per customer and supplier" is satisfied (many `people` rows
  referencing one `companies` row). **Invariant**: `is_employee` is `true` if and
  only if `company_id` is `null` — enforced by a Pydantic validator
  (`backend/app/modules/people/schemas.py`) that rejects a contradictory combination
  with `422`, before it reaches the service layer.

No soft delete: per
[Database.md](../Database.md#soft-delete-and-audit-trail)'s "purely operational/
lookup tables may hard-delete" carve-out, `DELETE` removes the row. A `companies`
row cannot be deleted while any `people` row still references it (`409`) — an
operator must reassign or delete those contacts first.

## APIs

Implemented under `/api/v1/people` and `/api/v1/companies`
(`backend/app/modules/people/router.py`), per [API.md](../API.md). Every endpoint
requires authentication (any active user in the organisation — People is a shared
directory, not an admin-only function) and is scoped to the caller's own
organisation; a cross-organisation id returns `404`, never revealing whether it
exists elsewhere.

- `GET/POST /api/v1/people`, `GET/PATCH/DELETE /api/v1/people/{id}` — standard CRUD,
  paginated (`?limit=&offset=`) and filterable by `company_id`, `is_employee`,
  `department`.
- `GET/POST /api/v1/companies`, `GET/PATCH/DELETE /api/v1/companies/{id}` — CRUD for
  the company directory.
- `GET /api/v1/companies/{id}/people` — paginated list of contacts for one company.
- `GET /api/v1/people?search=` — case-insensitive substring search across
  `first_name`/`last_name`/`email`/`role`, feeding the app-wide search goal in
  [Architecture.md](../Architecture.md).

Creator/updater attribution: `created_by_id` is set from the authenticated caller on
create; `updated_by_id` is set on every update.

## Workflow

People is a directory module, not a workflow module: records are created and
maintained directly, then **referenced** (never duplicated) by owner/assignee/
approver/contact fields across every other module — e.g. an NCR's `raised_by_id`, a
Maintenance request's `assigned_to_id`, a Supplier's linked `company_id`.

## Relationships to other modules

- [Suppliers](Suppliers.md) (not yet built) — a `suppliers` row will link to a
  `companies` row for identity/contact data; supplier contacts are `people` rows
  with that `company_id`.
- Every future module with an owner, assignee, approver, or reporter field (NCR,
  Maintenance, Calibration, the Health and Safety modules) is expected to reference
  `people.id` rather than storing name/contact details inline.
- [Document Management](DocumentManagement.md) (not yet built) — approvers and
  acknowledging staff are expected to be `people`.

## Future improvements

- Basic org-chart / reporting-line modelling.
- Contact import (CSV/vCard).
- Richer customer relationship fields if a dedicated CRM-style need emerges (kept out
  of scope for now — see [FutureIdeas.md](../FutureIdeas.md)).

## Known issues / status

Backend (schema, migration, service layer, API) is implemented and tested — unit
tests for models/schemas/service (`backend/tests/unit/test_people_*.py`) and
integration tests against real PostgreSQL covering organisation isolation, the
`is_employee`/`company_id` invariant, and the companies-with-contacts delete guard
(`backend/tests/integration/test_people.py`). Frontend screens are tracked
separately in [docs/CurrentStatus.md](../CurrentStatus.md) — see that document for
exactly what is and isn't done as of the current session.

## Related documents

- [Roadmap.md](../Roadmap.md#m1-authentication-organisations-people)
- [Database.md](../Database.md)
- [API.md](../API.md)
- [Suppliers.md](Suppliers.md)

# People

**Status: Planned.** Not yet implemented — targeted for
[Milestone 1](../Roadmap.md#m1-authentication-organisations-people). No code exists
for this module yet; see [docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

A shared database of employees, customers, suppliers and contacts, reused throughout
the system instead of each module keeping its own contact records. Stores phone,
email, role, department and notes, and supports multiple contacts per customer and
supplier per [ProductSpecification.md](../ProductSpecification.md#people).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`companies`** — `id`, `organisation_id`, `name`, `type` (`customer` / `supplier` /
  `other`), `address`, `phone`, `general_email`, `notes`, `created_at`, `updated_at`.
  A lightweight external-organisation record; the [Suppliers](Suppliers.md) module
  attaches supplier-specific fields to a `companies` row rather than duplicating
  name/address/contact data.
- **`people`** — `id`, `organisation_id`, `company_id` (nullable FK →
  `companies.id`), `first_name`, `last_name`, `email`, `phone`, `role`, `department`,
  `notes`, `is_employee` (bool), `created_at`, `updated_at`. A null `company_id`
  represents an internal employee; a populated one represents a contact at a customer
  or supplier company — this is how "multiple contacts per customer and supplier" is
  satisfied (many `people` rows referencing one `companies` row).

## Planned APIs

Under `/api/v1/people` per [API.md](../API.md#module-endpoint-prefixes-reserved-not-yet-implemented):

- `GET/POST /api/v1/people`, `GET/PATCH/DELETE /api/v1/people/{id}` — standard CRUD,
  paginated and filterable by `company_id`, `is_employee`, `department`.
- `GET/POST /api/v1/companies`, `GET/PATCH/DELETE /api/v1/companies/{id}` — CRUD for
  the company directory.
- `GET /api/v1/companies/{id}/people` — list contacts for one company.
- `GET /api/v1/people?search=` — name/email/role search, feeding the app-wide search
  goal in [Architecture.md](../Architecture.md).

## Workflow

People is a directory module, not a workflow module: records are created and
maintained directly, then **referenced** (never duplicated) by owner/assignee/
approver/contact fields across every other module — e.g. an NCR's `raised_by_id`, a
Maintenance request's `assigned_to_id`, a Supplier's linked `company_id`.

## Relationships to other modules

- [Suppliers](Suppliers.md) — a `suppliers` row links to a `companies` row for
  identity/contact data; supplier contacts are `people` rows with that `company_id`.
- Every module with an owner, assignee, approver, or reporter field (NCR, Maintenance,
  Calibration, the Health and Safety modules) references `people.id` rather than
  storing name/contact details inline.
- [Document Management](DocumentManagement.md) — approvers and acknowledging staff
  are `people`.

## Future improvements

- Basic org-chart / reporting-line modelling.
- Contact import (CSV/vCard).
- Richer customer relationship fields if a dedicated CRM-style need emerges (kept out
  of scope for now — see [FutureIdeas.md](../FutureIdeas.md)).

## Known issues / status

Planned only; no schema, API, or UI exists yet. Depends on
[authentication](../Roadmap.md#m1-authentication-organisations-people) landing in
the same milestone, since `people` rows are expected to be attributable to acting
users once auth exists.

## Related documents

- [Roadmap.md](../Roadmap.md#m1-authentication-organisations-people)
- [Database.md](../Database.md)
- [Suppliers.md](Suppliers.md)

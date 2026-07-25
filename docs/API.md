# API

REST conventions for the openQMS backend. Milestone 0 implements the health and
readiness endpoints; this is the contract every later module must follow. See
[Architecture.md](Architecture.md) for how the API fits the layered backend and
[DecisionLog.md](DecisionLog.md) for why URL path versioning was chosen.

## Versioning

All endpoints are mounted under `/api/v1/`. Each module owns one `APIRouter` with its
own prefix, aggregated into the versioned router in `backend/app/api/v1/router.py`,
e.g. `/api/v1/documents`, `/api/v1/ncr`. A future breaking change would be introduced
as `/api/v2/...` alongside the still-running `v1`, not as an in-place break.

## Interactive documentation

FastAPI's automatic OpenAPI schema is exposed at `/api/v1/openapi.json`, with
interactive docs at `/docs` (Swagger UI) and `/redoc` (ReDoc) in non-production
environments. This is the authoritative, always-current contract; this document
describes conventions the schema itself does not capture (error shape, pagination,
auth headers).

## Request/response conventions

- All request and response bodies are JSON (`application/json`).
- Every request body and response body is defined by an explicit Pydantic schema in
  the owning module's `schemas.py` — no ad hoc dict responses.
- Field names are `snake_case`, matching the database columns they represent, to keep
  the mapping between API, schema, and schema-generated TypeScript types obvious.
- Timestamps are ISO 8601 with timezone (`2026-07-25T12:00:00Z`).
- UUIDs are serialised as their canonical hyphenated string form.

## Error format

Errors use a consistent JSON body regardless of status code:

```json
{
  "detail": "Human-readable summary of what went wrong.",
  "errors": [
    { "field": "email", "message": "value is not a valid email address" }
  ]
}
```

`errors` is present for `422` validation failures (FastAPI/Pydantic's default
validation error shape is normalised into this format via a shared exception handler
in `backend/app/core/errors.py`) and omitted otherwise. Standard HTTP status codes are
used throughout: `400` bad request, `401` unauthenticated, `403` forbidden, `404` not
found, `409` conflict, `422` validation error, `500` unhandled server error. Backend
code never leaks stack traces or internal exception text to the client in `500`
responses; those are logged server-side only.

## Pagination

List endpoints use offset/limit query parameters with a consistent envelope:

```
GET /api/v1/<resource>?limit=50&offset=0
```

```json
{
  "items": [ /* ... */ ],
  "total": 137,
  "limit": 50,
  "offset": 0
}
```

`limit` defaults to 50 and is capped (server-enforced maximum, e.g. 200) to prevent
accidentally unbounded queries. Cursor-based pagination is deferred until a table's
scale actually needs it (tracked in [FutureIdeas.md](FutureIdeas.md)); offset/limit is
sufficient for Milestone 0 and the first modules.

## Filtering and search

Deferred beyond Milestone 0. When modules add filtering (the spec requires "powerful
filtering and saved filters" across the product), the convention will be query
parameters matching field names for exact filters (e.g. `?status=open`) with a
documented, per-endpoint list of filterable fields in that module's docs
(`docs/modules/<Module>.md`) — not a generic/opaque query language, to keep endpoints
simple and typed.

## Authentication

Implemented in Milestone 1: JWT bearer tokens (`Authorization: Bearer <token>`)
issued on login, validated per-request via the `get_current_user` FastAPI dependency
(`backend/app/core/deps.py`), which resolves the current user and their organisation
from the token — never from client-supplied input. A user belongs to exactly one
organisation per token (see the multi-tenancy decision in
[DecisionLog.md](DecisionLog.md)); multi-organisation login is future SaaS work (see
[FutureIdeas.md](FutureIdeas.md)).

Full design reasoning (password hashing, token claims, the logout/revocation
strategy, the bootstrap admin mechanism) is recorded in
[DecisionLog.md](DecisionLog.md#2026-07-25-authentication-password-hashing-and-token-revocation-strategy)
and the
[Milestone 1 plan](../.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#1-authentication).

### `POST /api/v1/auth/login`

Request:
```json
{ "email": "user@example.com", "password": "..." }
```

Response `200`:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": "...", "organisation_id": "...", "email": "...",
    "full_name": "...", "role": "admin", "is_active": true
  }
}
```

Response `401` for wrong password, unknown email, or an inactive user — always the
same body (`{"detail": "Incorrect email or password"}`), so the response never
reveals which of the three occurred.

### `POST /api/v1/auth/logout`

Requires `Authorization: Bearer <token>`. Increments the calling user's
`token_version`, immediately invalidating every access token issued to that user so
far (all sessions, not just the current one — see the DecisionLog entry for the
trade-off). Response `204`.

### `GET /api/v1/auth/me`

Requires `Authorization: Bearer <token>`. Returns the authenticated user's own
profile (same shape as the `user` object in the login response). `401` if the token
is missing, invalid, expired, revoked, or the user is inactive.

## Health and readiness endpoints (Milestone 0)

These are the only endpoints Milestone 0 implements:

### `GET /api/v1/health`

Liveness probe. Does not touch the database. Always returns quickly.

Response `200`:
```json
{ "status": "ok" }
```

### `GET /api/v1/health/ready`

Readiness probe. Executes a trivial query (`SELECT 1`) against the database to
confirm connectivity.

Response `200` (ready):
```json
{ "status": "ready", "database": "ok" }
```

Response `503` (database unreachable):
```json
{ "status": "not_ready", "database": "error" }
```

## Module endpoint prefixes

`/api/v1/auth` is implemented (see "Authentication" above). The rest are reserved
prefixes for future modules, so routing collisions are avoided as modules land per
the [Roadmap](Roadmap.md). Each will get full documentation in its
`docs/modules/<Module>.md` "Planned APIs" section as it is implemented:

| Prefix | Module |
|---|---|
| `/api/v1/auth` | Authentication (Milestone 1) — implemented |
| `/api/v1/people` | People |
| `/api/v1/documents` | Document Management |
| `/api/v1/products` | Products |
| `/api/v1/suppliers` | Suppliers |
| `/api/v1/ncr` | NCR |
| `/api/v1/calibration` | Calibration and Asset Management |
| `/api/v1/maintenance` | Maintenance |
| `/api/v1/fair` | FAIR |
| `/api/v1/spc` | SPC |
| `/api/v1/hse/guidance` | Health and Safety: Government Guidance |
| `/api/v1/hse/audits` | Health and Safety: Audits |
| `/api/v1/hse/incidents` | Health and Safety: Incident Reporting |
| `/api/v1/hse/risk-assessments` | Health and Safety: Risk Assessments |

## Related documents

- [Architecture.md](Architecture.md) — layered backend and module boundaries.
- [Database.md](Database.md) — how these endpoints read/write data.
- [docs/modules/](modules/) — per-module planned API details.

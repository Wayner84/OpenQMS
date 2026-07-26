# Docker

openQMS is Docker-first: the entire stack must start with one Compose command and
persist data in named volumes. This document describes the target Compose layout for
Milestone 0. See [Deployment.md](Deployment.md) for how this is operated in
production and [Database.md](Database.md) for schema/migration details.

## One-command startup

```
docker compose up --build
```

This must, from a clean clone with only Docker installed:

1. Build the `backend` and `frontend` images.
2. Start PostgreSQL with a persistent named volume.
3. Run Alembic migrations against PostgreSQL automatically before the backend starts
   serving traffic.
4. Serve the backend at `http://localhost:8000` and the frontend at
   `http://localhost:5173` (dev) with the frontend able to reach the backend's
   `/api/v1/health` endpoint.

No manual steps (creating databases, running migrations by hand, installing
dependencies on the host) should be required beyond having Docker and Docker Compose
installed and copying `.env.example` to `.env`.

## Services

| Service | Image | Purpose | Port |
|---|---|---|---|
| `db` | `postgres:16` (pinned minor version) | Primary datastore | `5432` (host-mapped for local psql access) |
| `backend` | built from `backend/Dockerfile` | FastAPI app via Uvicorn | `8000` |
| `frontend` | built from `frontend/Dockerfile` | Vite dev server (dev) / static build behind a lightweight server (prod-style build) | `5173` |

`docker-compose.yml` defines these three services for Milestone 0. No reverse proxy,
cache, or message broker service is introduced until a module actually needs one —
avoiding speculative infrastructure per the spec's scope discipline.

## Volumes

| Volume | Mounted at | Purpose |
|---|---|---|
| `openqms_postgres_data` | `/var/lib/postgresql/data` in `db` | Persistent database storage across container restarts/rebuilds |
| `openqms_uploads` | `/app/uploads` in `backend` | Reserved for future file storage (documents, certificates, photos) — created in Milestone 0, unused until a module needs it |

Both are named Docker volumes (not bind mounts) so data survives `docker compose
down` (but not `docker compose down -v`, which is the explicit, intentional way to
reset local state).

## Environment configuration

`.env.example` at the repository root documents every variable Compose and the
backend need, with safe placeholder values — never real secrets. Contributors copy it
to `.env` (git-ignored) before running Compose. Planned variables for Milestone 0:

```
# Database
POSTGRES_USER=openqms
POSTGRES_PASSWORD=changeme
POSTGRES_DB=openqms
DATABASE_URL=postgresql+asyncpg://openqms:changeme@db:5432/openqms

# Backend
BACKEND_CORS_ORIGINS=http://localhost:5173
ENVIRONMENT=development
LOG_LEVEL=INFO

# Authentication (Milestone 1) - see docs/DecisionLog.md. JWT_SECRET_KEY has no safe
# default; the backend refuses to start without one.
JWT_SECRET_KEY=changeme-generate-a-long-random-secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Bootstrap admin (Milestone 1) - creates the first admin user on first startup only.
# Leave BOOTSTRAP_ADMIN_PASSWORD empty to have a random password generated and logged
# once (see `docker compose logs backend`).
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

## Health checks

`docker-compose.yml` defines a Compose `healthcheck` for `db` (using `pg_isready`),
for `backend` (using the `/api/v1/health/ready` endpoint from [API.md](API.md), via
`python -c` since the runtime image has no `curl`), and for `frontend` (a `node -e`
one-liner requesting the Vite dev server root, since `node:20-slim` also has no
`curl`), so `docker compose ps` accurately reflects whether the stack is actually
usable, not just running, for all three services.

## Dockerfiles

- `backend/Dockerfile` — multi-stage build: a `builder` stage installs dependencies
  with `uv` into a virtual environment, a slim runtime stage copies only the venv and
  application code, runs as a non-root user, and runs Alembic migrations then starts
  Uvicorn via an entrypoint script.
- `frontend/Dockerfile` — a dev-oriented stage (`npm install` + `npm run dev -- --host`)
  used by `docker-compose.yml`, and a separate production-oriented multi-stage build
  (`npm run build` → static files served by a minimal web server) documented here for
  later use in [Deployment.md](Deployment.md); Milestone 0 only needs the dev stage
  working end-to-end.

Both images pin their base image tags (e.g. `python:3.12-slim`, `node:20-slim`)
rather than floating `latest`, so builds are reproducible.

## Smoke test definition

The concrete, minimal smoke test for "does Milestone 0 work in Docker" (used to
verify the next implementation batch, not run in this documentation batch):

1. `docker compose up --build -d`
2. `docker compose ps` shows all services healthy.
3. `curl http://localhost:8000/api/v1/health` returns `{"status": "ok"}`.
4. `curl http://localhost:8000/api/v1/health/ready` returns `{"status": "ready", "database": "ok"}`.
5. Loading `http://localhost:5173` in a browser shows the frontend shell reporting the
   API as healthy (see [the Milestone 0 plan](../.hermes/plans/2026-07-25-milestone-0-foundation.md)
   for the exact UI acceptance criterion).
6. `docker compose down` stops cleanly; `docker compose up` again (without `--build`,
   without `-v`) brings the stack back up with the same seeded `organisations` row
   still present, proving volume persistence.

**Milestone 1 extension, verified:** with `JWT_SECRET_KEY` and `BOOTSTRAP_ADMIN_EMAIL`/
`BOOTSTRAP_ADMIN_PASSWORD` set in `.env`, the same sequence additionally verified,
through a real headless-browser walkthrough of `http://localhost:5173` (not just
`curl`): the bootstrap admin can log in, create and deactivate/reactivate a user, is
blocked from deactivating themselves (`409` shown inline), a member cannot see or use
`/users` (client-side hidden and server-side `403` on direct API call), and a member
can create a company, a company contact, and an employee under People — all of it
still present after a `docker compose down` / `up` restart (no `-v`). Verified with
the backend host port temporarily remapped to `18000` in a local, uncommitted test
only, for the same reason recorded in the Milestone 0 smoke test note above; the
committed `docker-compose.yml` is unaffected.

## Related documents

- [Deployment.md](Deployment.md) — production operation, backups, future hosted mode.
- [Database.md](Database.md) — migration workflow that runs at container startup.
- [Architecture.md](Architecture.md) — overall system shape.

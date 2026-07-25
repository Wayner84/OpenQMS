# Deployment

openQMS is self-hosted first: free, simple, and fully supported without any hosted
service. This document describes the self-hosting deployment model and the future
hosted/SaaS shape the architecture is designed to permit, without implementing SaaS
features now. See [Docker.md](Docker.md) for the Compose layout this deploys and
[Architecture.md](Architecture.md#multi-tenancy-strategy) for the multi-tenancy
reasoning.

## Self-hosting (primary, supported today)

**Target:** a single server (VM, on-prem machine, small cloud instance) running
Docker and Docker Compose.

1. Clone the repository.
2. Copy `.env.example` to `.env` and set real values (database password, CORS
   origins, etc. — see [Docker.md](Docker.md#environment-configuration)).
3. `docker compose up --build -d`.
4. Put a reverse proxy in front of the stack for TLS termination and a stable
   hostname. openQMS does not prescribe one — Caddy, Traefik, and Nginx all work; a
   minimal example reverse-proxy config is planned documentation for when the first
   production-style deployment actually happens (tracked in [TODO.md](TODO.md)), not
   invented speculatively now.
5. Back up the `openqms_postgres_data` and `openqms_uploads` named volumes on a
   schedule appropriate to the operator (see Backups below).

No account, license key, telemetry, or external service call is required to run
openQMS self-hosted. This must remain true for the life of the project per the
product vision.

## Backups

- **Database:** `pg_dump` against the running `db` service (or a scheduled `docker
  compose exec db pg_dump ...` cron job) is the primary, human-operable backup path.
  Volume-level snapshots (if the host platform supports them) are a secondary option.
- **Uploads:** the `openqms_uploads` volume should be backed up alongside the
  database, since document/certificate/photo records reference files stored there.
- Restoring is: stop the stack, restore the volume(s) or `pg_restore` the dump,
  restart the stack. This procedure will be expanded with exact commands once file
  storage is implemented (Milestone 2 onward) — documented here as it becomes real
  rather than speculatively now.

## Environments

Two environments are recognised via the `ENVIRONMENT` variable
(`development` / `production`):

- **development** — verbose logging, permissive CORS to `localhost`, Vite dev server
  with hot module reload, auto-reload on the backend (Uvicorn `--reload`).
- **production** — structured JSON logging at `INFO`, CORS restricted to the
  operator's configured origins only, frontend served as a static build, backend run
  without `--reload` and with multiple Uvicorn workers.

No "staging" environment is prescribed; self-hosted operators may run a second,
independent Compose stack with its own `.env` if they want one.

## Future hosted/SaaS shape (not implemented)

The product must permit a future hosted offering without building SaaS features now
(per the product spec). The architecture decision
([DecisionLog.md](DecisionLog.md#2026-07-25-multi-tenancy-and-future-saas-shape))
records the preferred future shape: **one Docker Compose stack per hosted
organisation**, managed on a server (or fleet of servers) by an operator-side
provisioning layer that does not exist yet and is explicitly out of scope for the
foreseeable roadmap (see [Roadmap.md](Roadmap.md) and
[FutureIdeas.md](FutureIdeas.md)). This is preferred over multiplexing many
organisations inside one running instance because:

- it reuses the exact same self-hosted image and Compose file with no "hosted mode"
  code branch to maintain,
- it gives each hosted customer the same data isolation guarantees as a self-hosted
  operator gets by construction (a separate database, not a shared one filtered by
  row),
- it matches what the product spec itself suggests as the likely future hosted shape.

Nothing in Milestone 0 builds toward the *provisioning* side of that (billing,
instance orchestration, subdomain routing) — only the schema-level readiness
(`organisation_id` on every tenant-scoped table) that either hosting shape would need.

## Related documents

- [Docker.md](Docker.md) — Compose services, volumes, smoke test.
- [Database.md](Database.md) — migration workflow applied on deploy.
- [Architecture.md](Architecture.md) — security baseline applied in production.
- [DecisionLog.md](DecisionLog.md) — multi-tenancy reasoning.

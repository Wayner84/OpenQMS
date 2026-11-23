# CMM Program Control

**Status: Planned — not implemented.** Optional module proposed for the testing-readiness phase after Milestone 5; see [Roadmap.md](../Roadmap.md#testing-readiness-gates-after-m5). This is not a substitute for Document Management's SOP/drawing records or a machine-side validation of the controlled program.

## Purpose

Control encrypted/binary CMM programs by exact bytes, approvals and publication rather than attempting a source-code diff. Operators upload candidate revisions, select an eligible approver, and can only load the approved master from a configured CMM-accessible location. Retain historical masters and the decision trail. A SHA-256 match establishes byte identity, **not** correctness or a semantic comparison.

## Database tables (planned)

- `programs`: `id`, `organisation_id`, machine/site association and stable program identity, display name, current approved revision pointer, timestamps; unique identity within the organisation's chosen naming scope.
- `program_revisions`: immutable `id`, program ID, revision label/sequence, server-generated private storage key, original filename (display only), size, server-computed SHA-256, change note, uploader ID/time, selected approver ID, status (`draft`, `in_review`, `approved`, `rejected`, `superseded`, `withdrawn`), timestamps. New bytes always create a new revision, never replace an old file.
- `program_decisions`: append-only decision ID, revision ID, acting user ID, outcome, timestamp, comments. No silent approver reassignment or admin override.
- `program_publications`: revision ID, export-root identifier, published relative name, verified SHA-256, publication state and timestamps; reconcile after crash. Store no arbitrary client-supplied filesystem path.
- Organisation-scoped configuration: module-enabled flag (off by default on existing installations), approved file extensions/max size, protected upload/archive root, export root mapping, run-data root (writable separately) and any approval/retention policy. Environment/container mounts and secret credentials remain deployment configuration; never put passwords into these rows.

The existing PostgreSQL + SQLAlchemy/Alembic stack remains the source of record. The files themselves require separately backed-up storage; a DB backup alone cannot restore them.

## APIs (planned, all server-authorised)

- Admin Settings: read/update enable toggle, upload policy and logical storage-root configuration; validate path reachability, root separation and permissions before enabling publication. Do not expose server secrets or permit an arbitrary request path.
- `GET/POST /api/v1/programs`: list/create program identities; `GET /api/v1/programs/{id}` for controlled metadata and revision history.
- `POST /api/v1/programs/{id}/revisions`: bounded binary upload to private storage with checksum; `POST .../submit`: nominate an active same-organisation approver with `programs.approve` capability; `POST .../approve` or `.../reject`: selected approver only (explicitly auditable override, if later approved as a policy), with a required reason on rejection.
- `GET .../revisions/{revision_id}/download` and `GET .../verify`: authorised download and server-side checksum verification; `GET .../publication`: publication status/integrity. Admin-only withdrawal and reconciliation interfaces, with audit entries.
- Disabled module returns denial server-side even if a client calls an endpoint directly; the frontend hides its navigation and controls for users lacking `programs.view`, and offers the enable toggle in Settings only to authorised administrators.

Exact URL/schema contract to be settled in a bounded implementation plan before code. The initial path configuration must be checked against Docker host/container mounts and UNC/network-share behaviour on the target deployment.

## Workflow and invariants

1. Create program identity; upload candidate bytes into non-public, server-named storage. Validate size/type and calculate SHA-256 while streaming. Do not trust supplied hash, filename or MIME as authority.
2. Uploader selects an eligible approver and submits. Reject self-approval by default. The named approver approves or rejects; record who/when/comments immutably. Only approval can trigger publication.
3. Publish the exact approved bytes by staged write, checksum validation and atomic rename **where the filesystem supports it**, then mark publication current. Never expose a draft/rejected file on the CMM path. Lock per program/revision and make retries idempotent; reconcile database/filesystem state after interruption before treating it as published.
4. Keep all former approved bytes in the protected archive; a newer approval supersedes the previous published version without deleting its history. Explicit withdrawal removes current availability without erasing audit evidence. Periodic checksum verification reports changes or missing files; don't silently repair a tampered share without an auditable recovery action.
5. Make the published master read-only as an additional guardrail. The CMM account must lack master-write permission at the share/ACL level, while run data has a separate writable destination. Read-only metadata alone does **not** guarantee a CMM's Save As behaviour and a SHA-256 digest cannot prevent modification. Verify the actual target software and filesystem permissions during a one-machine pilot.

## Relationships

Program identity may reference an [Asset](CalibrationAndAssetManagement.md) for the CMM and [Product](Products.md) for the measured part when useful. Link an accompanying approved instruction/drawing to [Document Management](DocumentManagement.md) rather than copying it into the binary master. Decisions refer to authenticated `users`, not `people`. Permissions are shared with [role/permission management](../Roadmap.md#testing-readiness-gates-after-m5).

## Test and deployment acceptance (not yet met)

- Single-admin bootstrap remains usable; toggle off means no program route/action can publish. Separate `view`, `upload`, `submit`, `approve`, `publish/configure`, `verify`, and `withdraw` permissions enforced at the API boundary.
- Wrong-tenant IDs return 404 without leaking existence; inactive/non-approver/self-approver attempts cannot approve. Concurrent revisions/approvals have deterministic conflicts.
- Upload, approve, reject, supersede, restart/reconcile, missing-file and tamper cases covered against disposable PostgreSQL + isolated filesystem roots; no real CMM share is written in tests.
- Pilot with a specific CMM application and read-only service account verifies approved bytes, actual Save/Save As and run-data destinations, backup/restore and rollback. No blanket claim that filesystem read-only forces Save As across CMM vendors.

## Future improvements / open decisions

Confirm target CMM products, machine/site naming scope, companion-file handling, approver reassignment/override, emergency withdrawal, retention policy, UNC versus local mount topology, and physical permission model before production deployment. Multi-approver or e-signature workflows are separate future policy decisions, not assumed by this first version.

## Known issues / status

Entire module is planned. Existing Document Management already stores SHA-256 for its versions and has an admin-only approval workflow, but it does not implement named approver selection, a CMM export share, binary master immutability guarantees or this module's permission model. No production-readiness claim is warranted yet.

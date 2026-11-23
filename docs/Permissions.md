# Granular access control (planned)

**Status:** Not implemented. The existing baseline has one bootstrap admin, admin/member roles and admin-only user CRUD. Do not describe this page as the current runtime policy.

## Goal

A single-admin installation remains the default. An admin can create users, assign organisation-scoped roles and grant/deny granular capabilities. A user with `documents.read` but not `documents.revise` may list and download documents but cannot upload a new version via the UI **or a direct HTTP call**. A user lacking a module's `.view` capability cannot see or access that module. The optional Program Control module also requires its organisation toggle to be enabled.

## Proposed schema and policy

- A fixed, versioned permission catalogue in code (stable keys), backed by organisation-scoped `roles`, `role_permissions`, `user_roles` and optional `user_permission_overrides` in PostgreSQL. Avoid arbitrary free-text permission names. The initial admin/member roles migrate to equivalent grants so existing users are not silently locked out or escalated.
- Set module visibility (`documents.view`, `programs.view`, etc.) distinctly from object actions (`documents.read`, `documents.create`, `documents.update`, `documents.revise`, `documents.approve`, `documents.delete`, `programs.upload`, `programs.approve`, `programs.withdraw`, `settings.configure`). Inventory every existing endpoint and assign exactly one or more requirements; don't leave a mutation reachable through an unprotected alternate route.
- Administrator cannot self-escalate through ordinary user endpoints and cannot disable/demote the last active administrator. Grant and role-management routes require dedicated server-side permission; organisation IDs always derive from the authenticated actor. Restrict role assignment and approver eligibility to the same organisation.
- Resolve effective permissions on each request from the database or a safely invalidated cache; do not embed durable grants in the JWT. Deny should override grants, pending an explicit implementation decision. All auth failures remain distinct from cross-tenant lookup behaviour: 401 for no valid session, 403 for authenticated-but-unauthorised, 404 for a foreign resource whose existence must not be revealed.
- `GET /api/v1/auth/me` or a capabilities endpoint returns the caller's effective permission keys and the module-enabled flags needed by the frontend. Frontend uses them for navigation, route guards and action controls; the backend remains authoritative. Changing permissions should affect the next request and refresh the session capabilities.

## Bounded build/checkpoints

1. Inventory current API routes and legacy admin/member matrix; write migration/compatibility tests first. Decide role/override precedence and preserve last-admin invariants.
2. Implement SQL models, migration, policy evaluator and authenticated capabilities response. Verify with disposable PostgreSQL, including migration/downgrade and legacy accounts.
3. Enforce document-action permissions server-side, with a read-but-not-revise integration test; extend endpoint by endpoint using the inventory rather than silently flipping all current member actions at once.
4. Build Settings/user-role administration and capabilities-driven frontend navigation/action hiding; test direct-route and direct-API bypass. Then extend enforcement to every existing module and publish a final permission matrix.
5. Only then implement optional [Program Control](modules/ProgramControl.md), including its module toggle and named-approver eligibility.

## Acceptance blockers

No claim of test readiness until a current-member compatibility matrix, direct-API denial tests, cross-organisation scoping, last-admin guard, permission-revocation behaviour, and the backend/frontend end-to-end flow pass. UI hiding alone is not security. The role policy must also remain usable in the default single-admin setup.

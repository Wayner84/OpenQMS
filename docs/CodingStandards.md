# Coding Standards

Code-level conventions for openQMS, backend and frontend. Written before any
application code exists; applies from the first commit of Milestone 0 onward. See
[Architecture.md](Architecture.md) for the layered structure these standards operate
within and [Contributing.md](Contributing.md) for the workflow (branching, commits,
test-first) around writing code.

## Cross-cutting principles

- **No feature without documentation.** Per the project's autonomy contract in
  [ProductSpecification.md](ProductSpecification.md), no meaningful feature merges
  without an accompanying update to the relevant docs
  (`docs/modules/<Module>.md`, [CurrentStatus.md](CurrentStatus.md),
  [TODO.md](TODO.md), [DecisionLog.md](DecisionLog.md) as applicable) in the same
  commit.
- **Test-first (RED-GREEN-REFACTOR).** New behaviour starts with a failing test, the
  minimum code to pass it, then refactoring with the test green throughout. See
  [Contributing.md](Contributing.md#test-first-workflow-red-green-refactor) for the concrete workflow.
- **No hard-coded business rules.** Numbering schemes, prefixes, risk scoring,
  approval workflows, intervals — anything the spec calls out as configurable — is
  read from the database `configuration` pattern (see
  [Database.md](Database.md#configuration-table)), never a literal in code.
- **No giant files.** If a router, service, or component file is doing clearly
  separable things, split it. As a guideline (not a hard limit enforced by tooling):
  if a file exceeds roughly 300–400 lines, look for a natural seam before adding more.
- **Public functions are documented.** Every public function/method (not prefixed
  `_`) has a docstring (Python) or TSDoc comment (TypeScript) explaining what it does
  and why, when the name and types alone don't make it obvious. Trivial getters/
  passthroughs don't need one.
- **Comments explain why, not what.** Default to no comments; add one only for a
  non-obvious constraint, invariant, or workaround. Well-named code explains what it
  does.

## Backend (Python)

- **Python 3.12+, full type hints everywhere.** No untyped `def` in application code;
  `mypy` runs in strict-ish mode (see below) and must pass.
- **Formatting and linting: ruff.** `ruff format` for formatting, `ruff check` for
  linting (imports, unused code, common bug patterns). No separate Black/isort/flake8
  config — ruff replaces all three.
- **Type checking: mypy**, configured in `backend/pyproject.toml`. Third-party
  libraries without stubs are handled with targeted `ignore_missing_imports`
  overrides, not a blanket project-wide relaxation.
- **Dependency injection via FastAPI `Depends()`** for database sessions, current
  user/organisation (once auth exists), and shared config — never a global mutable
  singleton reached into from inside a function body.
- **SQLAlchemy 2.0 declarative style** (`Mapped[]`, `mapped_column()`); no legacy
  `Column()` declarations in new models.
- **Layering is one-directional**: routers → services → models. A router never
  queries the database directly; a model never calls a service. See
  [Architecture.md](Architecture.md#layered-backend-architecture).
- **Pydantic schemas are the API contract**, kept separate from ORM models
  (`schemas/` vs `models/`) so storage details don't leak into the wire format.
- **Module isolation**: a module (`backend/app/modules/<name>/`) may call another
  module's public `service.py` functions; it must not import another module's
  `models.py` directly or query its tables. Cross-module data access goes through the
  owning module's service layer.
- **Structured logging** via the standard `logging` module with a JSON formatter
  (configured once in `core/logging.py`); modules call `logging.getLogger(__name__)`,
  never `print()`.

## Frontend (React + TypeScript)

- **TypeScript strict mode** (`"strict": true` in `tsconfig.json`); no `any` in new
  code — use `unknown` plus narrowing, or a proper generated/declared type.
- **Functional components with hooks only.** No class components.
- **Feature-folder structure**: `frontend/src/modules/<module_name>/` mirrors the
  backend module boundary — components, hooks, and API-client functions for a module
  live together, not scattered by technical type (no global `components/`,
  `hooks/` dumping grounds for module-specific code; `shared/` is reserved for things
  genuinely used across multiple modules).
- **API access is centralised**: each module's API calls go through a small typed
  client function set (`modules/<name>/api.ts`) built on one shared `fetch` wrapper in
  `shared/api/client.ts` that attaches the base URL, JSON headers, and (once auth
  exists) the bearer token. Components never call `fetch` directly.
- **Styling**: plain CSS with custom properties (CSS variables), no component library
  or CSS-in-JS — chosen in Milestone 0 for a dependency-light, framework-agnostic
  baseline (see [DecisionLog.md](DecisionLog.md#2026-07-25-frontend-styling-approach)).
  Theme colours are defined once as CSS custom properties on `:root` and overridden
  under `[data-theme='dark']`; components style against the variables, never
  hard-coded colours. Light/dark mode is applied via a `data-theme` attribute on
  `<html>`, driven by `shared/theme/ThemeProvider.tsx`, which resolves the OS
  `prefers-color-scheme` by default and persists an explicit user toggle
  (`shared/theme/ThemeToggle.tsx`) to `localStorage`. This keeps theming centralised
  and not a per-component concern.
- **Linting/formatting: ESLint** (TypeScript + React + accessibility plugins) and
  **Prettier**, run via `npm run lint`.
- **Type checking**: `tsc --noEmit` via `npm run typecheck`, must pass with zero
  errors before merge.
- **The unmount-safety `mountedRef` pattern must reset on every (re-)mount, not just
  clear on unmount.** A component with an async effect/handler that guards
  `setState` calls with `if (mountedRef.current)` needs:
  ```tsx
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  ```
  not just the cleanup half. React 18 `<StrictMode>` (used in `main.tsx`)
  double-invokes every effect once in development (mount → cleanup → mount again) to
  surface missing-cleanup bugs; a ref that is only ever set `false` and never back to
  `true` gets stuck `false` after that simulated first mount, silently dropping every
  later `setState` — including the one that turns off the initial loading state. This
  shipped undetected in `UsersPage`/`CompaniesPage`/`PeoplePage` because plain RTL
  `render()` doesn't exercise `<StrictMode>`; see
  [DecisionLog.md](DecisionLog.md#2026-07-26-milestone-1-closeout-login-timing-side-channel-and-a-react-strictmode-mountedref-bug).
  A test that wraps `render()` in `<StrictMode>` and asserts the initial data still
  loads is required for any new component using this pattern.

## Testing

- **Backend**: pytest. Unit tests (`backend/tests/unit/`) target services and pure
  logic with SQLite where possible; integration tests
  (`backend/tests/integration/`) exercise routers end-to-end via httpx's
  `AsyncClient` against a real PostgreSQL instance and any PostgreSQL-only behaviour.
  Coverage is measured (`pytest-cov`) and tracked over time, not gated at an arbitrary
  threshold while the codebase is this young.
- **Frontend**: Vitest + React Testing Library for component/unit tests. End-to-end
  browser testing (e.g. Playwright) is deferred until there is a real user workflow
  worth testing end-to-end (tracked in [FutureIdeas.md](FutureIdeas.md)), not built
  speculatively for a health-check page.
- **Test-first is the default workflow** for new behaviour; it is not retroactively
  required for exploratory spikes, but a spike does not merge to `main` until it has
  tests. See [Contributing.md](Contributing.md#test-first-workflow-red-green-refactor).

## Commands (established in Milestone 0, referenced by every later batch)

| Command | Purpose |
|---|---|
| `cd backend && uv run ruff check .` | Lint backend |
| `cd backend && uv run ruff format .` | Format backend |
| `cd backend && uv run mypy .` | Type-check backend |
| `cd backend && uv run pytest` | Run backend tests |
| `cd backend && uv run alembic upgrade head` | Apply migrations |
| `cd frontend && npm run lint` | Lint frontend |
| `cd frontend && npm run typecheck` | Type-check frontend |
| `cd frontend && npm run test` | Run frontend tests |
| `cd frontend && npm run build` | Production build |

These exact commands must exist and pass (or be justifiably empty, e.g. "no tests
yet" only ever true before Milestone 0's own tests are written) once Milestone 0 is
implemented; see the
[Milestone 0 plan](../.hermes/plans/2026-07-25-milestone-0-foundation.md) for
acceptance criteria.

## Related documents

- [Architecture.md](Architecture.md) — the structure these standards apply within.
- [Contributing.md](Contributing.md) — workflow: branching, commits, PR expectations.
- [Database.md](Database.md) — schema/migration conventions.
- [API.md](API.md) — API contract conventions.

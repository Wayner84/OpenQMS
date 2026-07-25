# Contributing

openQMS is built by a long series of autonomous coding agent sessions, potentially
interleaved with human contributors. This document is the workflow contract that
keeps the project continuable across session endings, crashes, interrupted
conversations, model changes and fresh clones — the "autonomous development contract"
from [ProductSpecification.md](ProductSpecification.md) made concrete.

## Guiding rule

**If you changed behaviour, you update its documentation in the same commit.** No
feature exists without documentation. Specifically, keep these current in the same
commit as the work they describe:

- [CurrentStatus.md](CurrentStatus.md)
- [TODO.md](TODO.md)
- [DecisionLog.md](DecisionLog.md) (for architectural decisions)
- the relevant `docs/modules/<Module>.md` (for module work)

## Test-first workflow (RED-GREEN-REFACTOR)

For new behaviour:

1. **RED** — write a failing test that expresses the desired behaviour, at the
   appropriate layer (a service unit test for business logic, a router integration
   test for an endpoint contract). Run it and confirm it fails for the expected
   reason.
2. **GREEN** — write the minimum code to make the test pass. Resist adding anything
   the test doesn't require yet.
3. **REFACTOR** — clean up implementation and test code with the test suite green
   throughout, checking after each change.

Bug fixes follow the same shape: reproduce the bug as a failing test first, then fix
it.

Exploratory spikes (figuring out an approach) don't need to start with a test, but a
spike does not merge to `main` without tests covering the behaviour it introduces.

## Local development commands

See [CodingStandards.md](CodingStandards.md#commands-established-in-milestone-0-referenced-by-every-later-batch)
for the exact lint/typecheck/test/build commands once Milestone 0 is implemented.
Before that point, `docs/CurrentStatus.md` states plainly that these commands do not
exist yet.

## Branching and commits

- Work happens on `main` directly for this project's current single-agent-at-a-time
  cadence, unless a task explicitly calls for a branch (e.g. a large, risky, or
  parallel-with-other-work change) — match branch usage to what the task actually
  needs, don't create branches by default.
- **Commit messages explain the reason for a change**, not just what changed — per
  the product spec's autonomy contract. Prefer:
  `docs: record stack decisions before Milestone 0 implementation`
  over `docs: update files`.
- Commit at the boundary of a completed, coherent unit of work (a finished feature, a
  finished milestone slice, a finished documentation pass) — not mid-edit, and not so
  large that the commit bundles unrelated concerns. See each milestone plan under
  [.hermes/plans/](../.hermes/plans/) for the specific commit boundaries expected of
  that batch of work.
- Never rewrite history (`rebase -i`, `commit --amend` on already-recorded work,
  `push --force`) and never push unless a task explicitly authorises it. Sessions
  operate against the local repository; pushing to a remote is a separate, explicitly
  authorised action.

## Session continuity

Every session should leave the repository in a state a **fresh** session (no memory
of this conversation) can pick up correctly by reading, in order:

1. [README.md](../README.md) — orientation.
2. [docs/CurrentStatus.md](CurrentStatus.md) — what's actually done vs. in progress.
3. [docs/TODO.md](TODO.md) — what's next, with complexity/dependencies noted.
4. The relevant plan under [.hermes/plans/](../.hermes/plans/) — the exact next batch
   of work and its acceptance criteria.
5. [docs/DecisionLog.md](DecisionLog.md) — why the codebase looks the way it does, so
   past decisions aren't silently re-litigated or contradicted.

If a session cannot finish a unit of work, it must leave `CurrentStatus.md` and
`TODO.md` truthful about exactly what is and isn't done — never optimistic. A
half-finished feature is documented as half-finished, with concrete next steps, not
described as complete.

## Definition of done for a unit of work

- Tests pass (`pytest`, `npm run test`) for anything touched.
- Lint and type-check pass (`ruff check`, `mypy`, ESLint, `tsc --noEmit`) for anything
  touched.
- Relevant documentation (see "Guiding rule" above) is updated in the same commit.
- `docs/CurrentStatus.md` reflects the new state truthfully.
- The change is committed with a reason-focused message.

## Related documents

- [CodingStandards.md](CodingStandards.md) — code-level conventions and exact
  commands.
- [DecisionLog.md](DecisionLog.md) — how to record a new architectural decision.
- [Roadmap.md](Roadmap.md) — milestone order this workflow delivers against.

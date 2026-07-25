# CLAUDE.md

Operating contract for autonomous coding agents (Claude or otherwise) working in this
repository. Read this file, then [docs/CurrentStatus.md](docs/CurrentStatus.md) and
[docs/TODO.md](docs/TODO.md), before starting any work.

## What this project is

openQMS: an open-source, Docker-first quality management system. Full vision:
[docs/ProductSpecification.md](docs/ProductSpecification.md). Do not re-derive the
product vision from guesswork — it is fully specified there, including the
autonomous development contract this file operationalises.

## Read this before doing anything

1. [docs/CurrentStatus.md](docs/CurrentStatus.md) — what is actually done vs.
   planned. Trust this over assumptions from file presence alone.
2. [docs/TODO.md](docs/TODO.md) — next tasks, with dependencies and complexity.
3. The current milestone's plan under [.hermes/plans/](.hermes/plans/) — exact scope
   and acceptance criteria for the batch of work in front of you.
4. [docs/DecisionLog.md](docs/DecisionLog.md) — why the codebase looks the way it
   does. Do not silently contradict a recorded decision; if one needs to change, add
   a new dated entry explaining why.
5. [docs/Architecture.md](docs/Architecture.md), [docs/CodingStandards.md](docs/CodingStandards.md),
   [docs/Contributing.md](docs/Contributing.md) — the structure and conventions to
   follow.

## Non-negotiable rules

- **No feature without documentation.** Every meaningful change updates the relevant
  `docs/modules/<Module>.md`, [docs/CurrentStatus.md](docs/CurrentStatus.md),
  [docs/TODO.md](docs/TODO.md), and [docs/DecisionLog.md](docs/DecisionLog.md) (for
  architectural decisions) in the **same commit**.
- **Test-first (RED-GREEN-REFACTOR)** for new behaviour. See
  [docs/Contributing.md](docs/Contributing.md#test-first-workflow-red-green-refactor).
- **Commit messages explain the reason** for a change, not just what changed.
- **Never push, force-push, rewrite history, or amend already-recorded commits**
  unless a task explicitly authorises it.
- **Never build ahead of the roadmap order** ([docs/Roadmap.md](docs/Roadmap.md))
  without a new [docs/DecisionLog.md](docs/DecisionLog.md) entry explaining the
  deviation.
- **Keep `docs/CurrentStatus.md` truthful.** Never describe planned or in-progress
  work as complete. If a session cannot finish a unit of work, leave the status
  documentation reflecting exactly what is and isn't done.
- **No SaaS features yet.** The schema is designed to permit a future hosted mode
  (`organisation_id` on tenant-scoped tables), but multi-organisation switching,
  billing, and provisioning are explicitly out of scope until scheduled — see
  [docs/FutureIdeas.md](docs/FutureIdeas.md).
- **No hard-coded business rules.** Numbering schemes, prefixes, risk scoring,
  approval workflows, intervals — read from the database `configuration` pattern
  (see [docs/Database.md](docs/Database.md#configuration-table)), never a literal.
- **Stay in scope discipline.** Build the current milestone's vertical slice; do not
  start unrelated modules or speculative infrastructure "while you're in there."

## Stack (see docs/DecisionLog.md for reasoning)

Backend: Python, FastAPI, SQLAlchemy 2.0 (async) + Alembic, PostgreSQL (SQLite
permitted for fast unit tests only). Frontend: React + TypeScript + Vite. Everything
runs via one `docker compose up --build`.

## Commands

See [docs/CodingStandards.md](docs/CodingStandards.md#commands-established-in-milestone-0-referenced-by-every-later-batch)
for the exact lint/typecheck/test/build commands once they exist. Do not invent
commands that aren't documented there — add them to that table in the same commit
that introduces them.

## Session handoff

Before ending a session, ensure a fresh session with no memory of this conversation
could resume correctly by reading the files listed under "Read this before doing
anything" above. That is the definition of done for repository state, independent of
whether the assigned task itself is fully complete.

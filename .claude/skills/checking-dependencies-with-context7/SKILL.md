---
name: checking-dependencies-with-context7
description: Use before writing any code that introduces a new dependency, upgrades a dependency's version, or calls an API on an existing dependency (fastapi, sqlalchemy, pydantic, alembic, python-jose, passlib/bcrypt, or any future package) whose exact current shape isn't already confirmed in this session.
---

# Checking Dependencies with context7

## Overview

Training data goes stale; package APIs change across versions (this
project pins `fastapi>=0.115.0`, `sqlalchemy>=2.0.0`, `pydantic>=2.0.0`,
`alembic>=1.13.0`, `python-jose[cryptography]>=3.3.0`,
`passlib[bcrypt]>=1.7.4` in `pyproject.toml`). Before writing code against
a dependency's API, confirm the current shape via the `context7` MCP
tools instead of assuming from memory — this matters especially for
SQLAlchemy 1.x-vs-2.x style and Pydantic v1-vs-v2 style, where both major
versions are common in training data and the wrong one won't always fail
loudly.

## When to Use

- Adding a new dependency to `pyproject.toml`.
- Bumping an existing dependency's version.
- Writing code that calls a dependency API not already verified earlier in
  the same session (a new SQLAlchemy 2.0-style query construct, a Pydantic
  v2 validator/`ConfigDict` pattern, a `python-jose` claim-handling detail,
  etc.).

**Skip it for:** pure standard-library code, and calls into this
project's own modules (`database.py`, `models.py`, `schemas.py`,
`auth.py`, `analytics.py`) — context7 is for external dependency docs,
not this codebase's own source, which should be read directly instead.

## Workflow

1. `resolve-library-id` — resolve the package name (e.g. `sqlalchemy`) to
   its context7 library ID.
2. `query-docs` — fetch current documentation for that library ID, scoped
   to the specific API surface you're about to use (a query construct, a
   validator signature, a config option), not the whole library.
3. Write code against what the docs actually show — don't fall back to a
   remembered API shape if it conflicts with what context7 returns.

## Common Mistakes

- Guessing a method name/signature from training data when the package
  has had breaking changes since (SQLAlchemy 1.x → 2.0 and Pydantic v1 →
  v2 are the two most likely traps here) — check first, don't patch after
  a `pytest` run fails.
- Running this for internal project modules — there's nothing external to
  look up; just read the source.
- Skipping this on a "small" API call — a one-line call to the wrong
  overload is exactly the kind of thing this catches cheaply.

Referenced from `CLAUDE.md`'s dependency-check rule; not tied to a
specific subagent — applies to whoever is about to write the code (main
thread or `requirement-specialist`'s green-adjacent context).

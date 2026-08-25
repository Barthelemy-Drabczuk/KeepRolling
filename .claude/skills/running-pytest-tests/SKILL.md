---
name: running-pytest-tests
description: Use when running or writing pytest commands for this project — the red step (new failing test) and the full-suite verify step — and when telling a valid red/failing state apart from a broken one.
---

# Running pytest Tests

## Overview

Correct `pytest` invocations for this project, and how to tell a valid
red state (test fails because the behavior isn't implemented yet) from a
broken one (test fails or errors for an unrelated reason: bad import,
typo, fixture problem).

## The cwd requirement

Every module under `backend/app/` uses bare imports —
`from database import get_db`, `from models import UserModel`, not
`from backend.app.database import ...`. These only resolve when
`backend/app/` itself is on `sys.path`. Always run pytest **from
`backend/app/`**, not the repo root:

```bash
cd backend/app
pytest
```

Running `pytest` from the repo root will fail to collect any test that
imports application modules, with `ModuleNotFoundError`, not a clean
"no tests found" — don't mistake that for a real red state.

## Common Invocations

| Command (run from `backend/app/`) | Purpose |
|---|---|
| `pytest` | Full suite |
| `pytest tests/test_auth.py` | One test file |
| `pytest tests/test_auth.py::test_hash_password_roundtrips` | One test |
| `pytest -k "mood and not entry"` | Keyword-filtered subset |
| `pytest -x` | Stop at first failure — useful while confirming red |
| `pytest --collect-only` | Confirm a new test is discovered before checking it's red, without running it |

There is no `tests/` directory yet in this project — the first test
written should create `backend/app/tests/` and (if pytest doesn't
auto-discover it) a `backend/app/tests/__init__.py` or a `conftest.py`
alongside it.

## Telling Red From Broken

A valid red state: the test runs, reaches the assertion or the call into
missing behavior, and fails there (`AssertionError`, or the specific
exception the requirement implies).

Not a valid red state — fix these before treating the test as "red":
- **Collection errors** (`ERROR` instead of `FAILED` in pytest's output) —
  usually an import typo or a missing fixture, not the intended failure.
- **`ModuleNotFoundError` for a project module** — almost always means
  pytest was run from the wrong directory (see cwd requirement above).
- **Fixture setup failing** (e.g., a `TestClient`/DB-session fixture
  raising before the test body runs) — the test never actually exercised
  the requirement.

## Common Mistakes

- Running `pytest` from the repo root and reading the resulting
  `ModuleNotFoundError` as "no implementation yet" — it isn't; fix the cwd
  first.
- Treating a collection error as red just because the exit code is
  nonzero — check the output actually shows `FAILED` on the test you
  wrote, for the reason you expect.
- Using `TestClient` against the real `DATABASE_URL` from `backend/app/.env`
  — prefer overriding the `get_db` dependency with a test database/session
  so tests don't mutate real data.

Used by `requirement-specialist` (red step) and `qc-specialist` (verify
step) — see root `SKILLS.md`.

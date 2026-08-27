# Python / FastAPI profile

**Location & naming:** tests live under `backend/app/tests/`, one
`test_<module>.py` per module under test. Use FastAPI's
`TestClient`/`httpx` for endpoint behavior, plain function tests for
`analytics.py`/`auth.py` logic.

**Red confirmation:** run `pytest` from `backend/app/` — imports in
this codebase are bare (`from database import get_db`, not
`from backend.app.database import ...`) and only resolve with
`backend/app/` as cwd. A new test must fail because implementation is
missing, not because of a typo or a collection error — a collection
error is not a valid red state.

**Verify commands, in order:**
1. `ruff format --check .` — from the repo root.
2. `ruff check .` — from the repo root; `[tool.ruff]` lives in the root
   `pyproject.toml` and covers `backend/db.py` and `backend/alembic/`
   too, not just `backend/app/`.
3. `pytest` — from `backend/app/`, full suite, not just the module that
   changed.

**Cautions:** none beyond the cwd requirement above — a Python test
suite is cheap and safe to run repeatedly and in full.

# python-pytest

Applies to everything under `backend/app/` (see `STACK.md`). Managed
with pixi (`pyproject.toml`'s `[tool.pixi.tasks]`); `ruff` lives in the
`dev` feature/environment, `pytest` in the `test` feature — neither is
in the default environment, so every command below names its `-e`
explicitly.

## Red-confirmation

From `backend/app/`:

```
pixi run -e test pytest -q <path/to/new_test.py>::<test_name>
```

(or the whole new file, or `-k <expression>` for several new tests at
once). A valid red state fails with an `AssertionError` (or another
exception the test is specifically checking for) on the behavior under
test. It is **not** a valid red state if the failure is a
`SyntaxError`, `ImportError`/`ModuleNotFoundError` from a typo, or a
pytest collection error — fix the typo and re-run rather than reporting
red.

## Verify

Three commands, two different working directories:

```
# from the repo root
pixi run -e dev format-check     # ruff format --check .
pixi run -e dev lint             # ruff check .

# from backend/app/
pixi run -e test pytest -q
```

`ruff`'s config (`[tool.ruff]`) lives in the repo-root `pyproject.toml`,
which is why the first two run from there; `pytest.ini`'s
`pythonpath = .` is what lets `pytest`, run from `backend/app/`, import
the application modules the same way `uvicorn` does — see `CLAUDE.md`'s
"Commands" section for why `backend/app/` has to be the process's
working directory for this stack in general (bare imports, a
relative `StaticFiles` mount path).

The existing codebase is not fully `ruff`-clean (`CLAUDE.md`'s "Coding
style" section: ~320 pre-existing issues, mostly in `backend/db.py` and
files `ruff` hasn't touched yet). Don't take that baseline as a target
to fix incidentally — a "verify" pass only needs to confirm no *new*
issues were introduced in the files the current diff touches, not a
repo-wide clean bill.

## Green

The red-confirmation command from above now passes, and the full
`pixi run -e test pytest -q` suite (all tests, not just the new ones)
is still green — a change that fixes its own target test while breaking
another one is not green.

## Infra-vs-code split signal

This stack has no infrastructure half of its own (no Terraform/IaC in
this repo) — a requirement targeting `python-pytest` is always the code
half of a split, never the infrastructure half. If a future requirement
needs a real external resource (a queue, a second database, a scheduled
job) that doesn't exist as code, that resource's own stack (once
defined in `STACK.md`) is the infrastructure half that has to land
first.

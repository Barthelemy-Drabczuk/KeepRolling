"""Tests for REQ-SEC-1 and REQ-SEC-2 (see BUSINESS.md).

Both requirements are about *import-time* behavior: ``auth.py`` reads
``SECRET_KEY`` and ``app.py`` reads ``NICEGUI_STORAGE_SECRET`` while the
module executes, the same way ``database.py`` reads ``DATABASE_URL``.

Two things make that awkward to test in-process, hence the subprocess
helper below:

* ``conftest.py`` already imported both modules at collection time, so
  the only way to re-run their module bodies here would be
  ``importlib.reload`` — and a module whose reload raises part-way
  through leaves a half-updated namespace in ``sys.modules`` for every
  later test in the session to trip over.
* ``auth.py`` calls ``load_dotenv()`` at import, and a developer's local
  ``src/backend/app/.env`` (gitignored, absent in CI) defines
  ``SECRET_KEY``. The child process therefore neutralises
  ``dotenv.load_dotenv`` before importing anything from the app, so
  "the variable is not set" means the same thing on every machine.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent

# The configuration the modules under test need in order to get *past*
# their other import-time checks, so that the only thing missing in any
# given case is the one variable that case is about.
BASELINE_ENV = {
    "DATABASE_URL": "postgresql://unused:unused@localhost/unused",
    "SECRET_KEY": "subprocess-secret-key",
    "NICEGUI_STORAGE_SECRET": "subprocess-storage-secret",
}

_CHILD_SCRIPT = """
import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False

import {module}
"""

_UNSET = object()


def import_in_fresh_interpreter(module, variable=None, value=_UNSET):
    """Import ``module`` in a new interpreter and return the CompletedProcess.

    ``variable`` names one entry of ``BASELINE_ENV`` to override: removed
    from the child's environment when ``value`` is left at ``_UNSET``,
    otherwise set to ``value``.
    """
    env = dict(os.environ)
    env.update(BASELINE_ENV)
    if variable is not None:
        if value is _UNSET:
            del env[variable]
        else:
            env[variable] = value
    return subprocess.run(
        [sys.executable, "-c", _CHILD_SCRIPT.format(module=module)],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def assert_refused_startup(result, variable):
    """Assert the child exited non-zero on a ValueError naming ``variable``."""
    assert result.returncode != 0, (
        f"importing the module with {variable} absent succeeded "
        f"(exit 0); it must refuse to start.\nstdout: {result.stdout}"
    )
    assert "ValueError" in result.stderr, (
        f"expected a ValueError for the missing {variable}, got:\n{result.stderr}"
    )
    assert variable in result.stderr, (
        f"the error does not name {variable}, so it does not tell the "
        f"operator which variable to set:\n{result.stderr}"
    )


# ==================== REQ-SEC-1 ====================


@pytest.mark.parametrize("value", [_UNSET, ""], ids=["unset", "empty"])
def test_importing_auth_without_secret_key_refuses_startup(value):
    """REQ-SEC-1: no usable SECRET_KEY means auth.py raises, not a default key."""
    result = import_in_fresh_interpreter("auth", "SECRET_KEY", value)

    assert_refused_startup(result, "SECRET_KEY")


def test_importing_auth_with_secret_key_set_succeeds():
    """REQ-SEC-1: a configured SECRET_KEY still imports cleanly (guard)."""
    result = import_in_fresh_interpreter("auth")

    assert result.returncode == 0, result.stderr


# ==================== REQ-SEC-2 ====================


@pytest.mark.parametrize("value", [_UNSET, ""], ids=["unset", "empty"])
def test_importing_app_without_storage_secret_refuses_startup(value):
    """REQ-SEC-2: no usable NICEGUI_STORAGE_SECRET means app.py raises."""
    result = import_in_fresh_interpreter("app", "NICEGUI_STORAGE_SECRET", value)

    assert_refused_startup(result, "NICEGUI_STORAGE_SECRET")


def test_importing_app_with_storage_secret_set_succeeds():
    """REQ-SEC-2: a configured NICEGUI_STORAGE_SECRET still imports cleanly (guard)."""
    result = import_in_fresh_interpreter("app")

    assert result.returncode == 0, result.stderr

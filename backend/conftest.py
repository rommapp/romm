import hashlib
import os
import re
from pathlib import Path


def worktree_tag(start: Path) -> str:
    """Tag the linked git worktree (whose `.git` is a file) holding `start`, or ""."""
    for folder in (start, *start.parents):
        dot_git = folder / ".git"
        if dot_git.is_file():
            # Folder names that sanitize or truncate alike still get separate databases.
            digest = hashlib.sha256(str(folder).encode()).hexdigest()[:8]
            return f"{folder.name[:31]}_{digest}"
        if dot_git.exists():
            return ""
    return ""


# Tests must never inherit DB_NAME from the ambient environment (e.g. a
# sourced .env pointing at a real dev/prod database) -- the autouse
# `clear_database` fixture in tests/conftest.py deletes every row in that
# database on every test. Always pin to a dedicated test database, made
# unique per pytest-xdist worker so parallel workers can't wipe rows another
# worker is mid-test with. This must run before any application module
# (config / database handlers) is imported, so the engine built at import
# time binds to the test name. As the rootdir conftest, this file is
# imported before `tests/conftest.py` (which imports those modules).
#
# The Redis cache needs no equivalent handling: under pytest it is an in-process
# FakeRedis, so each worker process is already isolated.
#
# ROMM_TEST_DB_TAG runs use temporary databases that tests/conftest.py drops at
# session end; the `tmp_` prefix keeps them apart from the untagged worker names.
# A linked worktree gets one by default, since another checkout's migrations on
# the shared romm_test would break its runs.
if not os.environ.get("ROMM_TEST_DB_TAG") and (
    _worktree := worktree_tag(Path(__file__).resolve().parent)
):
    os.environ["ROMM_TEST_DB_TAG"] = _worktree

_tag = re.sub(r"[^A-Za-z0-9_]", "_", os.environ.get("ROMM_TEST_DB_TAG", ""))
_base = f"romm_test_tmp_{_tag}" if _tag else "romm_test"
_xdist_worker = os.environ.get("PYTEST_XDIST_WORKER")
os.environ["DB_NAME"] = f"{_base}_{_xdist_worker}" if _xdist_worker else _base

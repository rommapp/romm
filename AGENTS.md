# Repository Instructions

Read and follow [CLAUDE.md](CLAUDE.md) for all repository instructions.

## Never run the full backend test suite locally

A bare `uv run pytest` (or `pytest -vv`) over `backend/` takes 20+ minutes and burns a
huge number of tokens on output. Don't do it, even to "double check" at the end.

Instead, select the tests affected by the change and run only those:

```bash
cd backend
uv run pytest tests/path/to/test_file.py                # one file
uv run pytest tests/path/to/test_file.py::test_name     # one test
uv run pytest tests/handler/ tests/endpoints/           # affected areas
uv run pytest -k "scan or queue"                        # by name pattern
```

Pick the targets from the diff: the test file mirroring each changed module
(`backend/<area>/x.py` → `backend/tests/<area>/test_x.py`), plus the tests of the
callers of anything whose signature or behavior you changed (`grep` for the symbol).

CI runs the whole suite on the PR (`pytest.yml`, MariaDB + PostgreSQL). That is the
place for full-suite coverage; local runs stay scoped.

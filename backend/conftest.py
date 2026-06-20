import os

# When running under pytest-xdist, give each worker its own database so the
# autouse `clear_database` fixture in one worker can't wipe rows another worker
# is mid-test with. This must run before any application module (config /
# database handlers) is imported, so the engine built at import time binds to
# the per-worker name. As the rootdir conftest, this file is imported before
# `tests/conftest.py` (which imports those modules).
#
# The Redis cache needs no equivalent handling: under pytest it is an in-process
# FakeRedis, so each worker process is already isolated.
_xdist_worker = os.environ.get("PYTEST_XDIST_WORKER")
if _xdist_worker:
    _base_db_name = os.environ.get("DB_NAME", "romm_test")
    os.environ["DB_NAME"] = f"{_base_db_name}_{_xdist_worker}"

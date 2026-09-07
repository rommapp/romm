import os

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
_xdist_worker = os.environ.get("PYTEST_XDIST_WORKER")
os.environ["DB_NAME"] = f"romm_test_{_xdist_worker}" if _xdist_worker else "romm_test"

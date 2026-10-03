import os
import re

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
_tag = re.sub(r"[^A-Za-z0-9_]", "_", os.environ.get("ROMM_TEST_DB_TAG", ""))
_base = f"romm_test_tmp_{_tag}" if _tag else "romm_test"
_xdist_worker = os.environ.get("PYTEST_XDIST_WORKER")
os.environ["DB_NAME"] = f"{_base}_{_xdist_worker}" if _xdist_worker else _base

"""The API imports without opening a database connection or starting a thread, so gunicorn can preload it."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# Run in a fresh interpreter, the way the gunicorn master imports the app.
REPORT = """
import threading
import main
from handler.database.base_handler import sync_engine
others = [t.name for t in threading.enumerate() if t is not threading.main_thread()]
print("THREADS=" + ",".join(others))
print("DB=" + str(sync_engine.pool.checkedin() + sync_engine.pool.checkedout()))
"""


def test_importing_the_api_opens_no_connection_and_starts_no_thread() -> None:
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND),
        # Nothing listens on port 1, so a query made during import fails it.
        # Valkey is left out: redis-py starts a fresh pool when it sees a fork.
        "DB_PORT": "1",
        "OTEL_SDK_DISABLED": "true",
    }
    # Import the app as it starts in production, not in its pytest mode.
    for name in ("PYTEST_VERSION", "PYTEST_CURRENT_TEST", "SENTRY_DSN"):
        env.pop(name, None)

    result = subprocess.run(
        [sys.executable, "-c", REPORT],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        "importing main failed; it may have queried the database:\n"
        + result.stderr[-2000:]
    )
    report = dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )
    assert report["THREADS"] == "", f"threads started at import: {report['THREADS']}"
    assert report["DB"] == "0", "a database connection was opened at import"

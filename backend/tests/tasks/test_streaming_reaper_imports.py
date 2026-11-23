import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

# What the reaper's parent would load if its imports reached the database or the API.
HEAVY = ("handler.database", "handler.scan", "handler.metadata", "fastapi", "endpoints")


def test_the_streaming_worker_preloads_the_reaper_without_the_database_or_the_api(
    tmp_path: Path,
) -> None:
    """The parent keeps what it preloads; a work horse loads the rest if it reaps."""
    # A fresh interpreter, since this one has long since loaded all of them.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, handler.rq_worker;"
            "import tasks.scheduled.reap_streaming_sessions;"
            f"print([m for m in {HEAVY!r} if m in sys.modules])",
        ],
        cwd=BACKEND,
        # The default state; a developer's .env could otherwise turn telemetry on.
        env={
            **os.environ,
            "OTEL_SDK_DISABLED": "true",
            "ROMM_BASE_PATH": str(tmp_path),
        },
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "[]"

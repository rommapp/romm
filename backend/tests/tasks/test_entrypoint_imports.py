import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("entrypoint", ["tasks.cron_config", "handler.rq_worker"])
def test_rq_processes_start_without_loading_sqlalchemy(entrypoint: str) -> None:
    """Neither queries the database itself; their jobs load SQLAlchemy in their own process."""
    # A fresh interpreter, since this one has long since loaded SQLAlchemy.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys, {entrypoint}; print('sqlalchemy' in sys.modules)",
        ],
        cwd=BACKEND,
        # The default state; a developer's .env could otherwise turn telemetry on.
        env={**os.environ, "OTEL_SDK_DISABLED": "true"},
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "False"

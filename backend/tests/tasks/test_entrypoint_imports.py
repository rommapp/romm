import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("entrypoint", ["tasks.cron_config", "handler.rq_worker"])
@pytest.mark.parametrize("platform_formats", [False, True])
def test_rq_processes_start_without_loading_sqlalchemy(
    entrypoint: str, platform_formats: bool, tmp_path: Path
) -> None:
    """Neither queries the database itself; their jobs load SQLAlchemy in their own process."""
    # Setting converto.platform_formats makes the config validate it on load.
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yml").write_text(
        "converto:\n  platform_formats:\n    psx: chd\n" if platform_formats else ""
    )
    # A fresh interpreter, since this one has long since loaded SQLAlchemy.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys, {entrypoint}; print('sqlalchemy' in sys.modules)",
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

    assert result.stdout.strip().splitlines()[-1] == "False"

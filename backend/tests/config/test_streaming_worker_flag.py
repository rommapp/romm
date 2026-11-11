import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]


def _flag_seen_by_config(value: str | None) -> str:
    # Arrange
    env = {k: v for k, v in os.environ.items() if k != "ENABLE_STREAMING_WORKER"}
    if value is not None:
        env["ENABLE_STREAMING_WORKER"] = value

    # Act
    result = subprocess.run(
        [sys.executable, "-c", "import config; print(config.ENABLE_STREAMING_WORKER)"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    # Assert
    return result.stdout.strip()


@pytest.mark.parametrize(
    "value,expected",
    [(None, "True"), ("true", "True"), ("false", "False"), ("0", "False")],
)
def test_streaming_worker_is_on_unless_turned_off(value, expected):
    assert _flag_seen_by_config(value) == expected

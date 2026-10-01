import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from utils import get_version
from utils.sentry import init_sentry


def test_init_sentry_skips_the_sdk_without_a_dsn():
    with (
        patch("utils.sentry.SENTRY_DSN", None),
        patch("sentry_sdk.init") as mock_init,
    ):
        init_sentry()

    mock_init.assert_not_called()


def test_init_sentry_starts_the_sdk_with_a_dsn():
    dsn = "https://key@sentry.example.com/1"
    with (
        patch("utils.sentry.SENTRY_DSN", dsn),
        patch("sentry_sdk.init") as mock_init,
    ):
        init_sentry()

    mock_init.assert_called_once_with(dsn=dsn, release=f"romm@{get_version()}")


def test_init_sentry_never_loads_the_sdk_without_a_dsn():
    backend_root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(backend_root)}
    env.pop("SENTRY_DSN", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "from utils.sentry import init_sentry\n"
            "init_sentry()\n"
            "print('LOADED:' + str('sentry_sdk' in sys.modules))\n",
        ],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.rpartition("LOADED:")[2].strip() == "False"

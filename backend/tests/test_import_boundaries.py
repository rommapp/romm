"""Modules every RomM process imports must not pull in the web or database stack."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# The RQ workers, cron and the gunicorn master must not load these before they fork.
HEAVY = (
    "sqlalchemy",
    "fastapi",
    "starlette",
    "pydantic",
    "socketio",
    "endpoints",
    "tasks",
    "handler.database",
    "models.rom",
)


def _loaded_by(module: str, tmp_path: Path) -> set[str]:
    # Run in a fresh interpreter, since this one has long since loaded everything.
    (tmp_path / "config").mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib, sys\n"
            "before = set(sys.modules)\n"
            "importlib.import_module(sys.argv[1])\n"
            "print('LOADED:' + ' '.join(set(sys.modules) - before))\n",
            module,
        ],
        cwd=BACKEND_ROOT,
        env={
            "ROMM_AUTH_SECRET_KEY": "test",
            **os.environ,
            "PYTHONPATH": str(BACKEND_ROOT),
            "ROMM_BASE_PATH": str(tmp_path),
            "OTEL_SDK_DISABLED": "true",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    return set(result.stdout.rpartition("LOADED:")[2].split())


def test_config_manager_stays_clear_of_the_web_and_database_stack(
    tmp_path: Path,
) -> None:
    loaded = _loaded_by("config.config_manager", tmp_path)

    banned = sorted(
        name
        for name in loaded
        if any(name == heavy or name.startswith(f"{heavy}.") for heavy in HEAVY)
    )
    assert banned == []


def test_limits_import_nothing_but_the_models_package(tmp_path: Path) -> None:
    loaded = _loaded_by("models.limits", tmp_path)

    assert {
        name for name in loaded if name.split(".")[0] not in sys.stdlib_module_names
    } == {"models", "models.limits"}

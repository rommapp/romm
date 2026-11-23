"""Modules every RomM process imports must not pull in the web or database stack."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

# Imported by the RQ workers, cron and the gunicorn master before it forks.
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

REPORT = """
import sys
before = set(sys.modules)
import {module}
print("\\n".join(sorted(set(sys.modules) - before)))
"""


def _loaded_by(module: str, tmp_path: Path) -> set[str]:
    # A fresh interpreter, since this one has long since loaded everything.
    (tmp_path / "config").mkdir(exist_ok=True)
    env = {
        "ROMM_AUTH_SECRET_KEY": "test",
        **os.environ,
        "OTEL_SDK_DISABLED": "true",
        "ROMM_BASE_PATH": str(tmp_path),
    }
    result = subprocess.run(
        [sys.executable, "-c", REPORT.format(module=module)],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.split())


def _banned(loaded: set[str]) -> list[str]:
    return sorted(
        name
        for name in loaded
        if any(name == heavy or name.startswith(f"{heavy}.") for heavy in HEAVY)
    )


@pytest.mark.parametrize("module", ["config.config_manager", "models.limits"])
def test_module_stays_clear_of_the_web_and_database_stack(
    module: str, tmp_path: Path
) -> None:
    assert _banned(_loaded_by(module, tmp_path)) == []


def test_limits_import_nothing_but_the_models_package(tmp_path: Path) -> None:
    loaded = _loaded_by("models.limits", tmp_path)

    assert {name for name in loaded if name.split(".")[0] == "models"} == {
        "models",
        "models.limits",
    }
    assert not {name for name in loaded if name.split(".")[0] == "config"}

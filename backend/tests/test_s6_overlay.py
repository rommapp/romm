"""Guards the shape of the s6-overlay service tree in docker/s6-overlay."""

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
S6_ROOT = REPO_ROOT / "docker" / "s6-overlay"
SERVICES_DIR = S6_ROOT / "s6-rc.d"
SCRIPTS_DIR = S6_ROOT / "scripts"
USER_BUNDLE = S6_ROOT / "user-bundles.d" / "user" / "contents.d"
DEV_ENTRYPOINT = REPO_ROOT / "entrypoint.sh"

# Services s6-overlay ships, which ours may depend on.
S6_BUILTIN_SERVICES = {"base"}

# Where the image copies docker/s6-overlay, so `up` files name these paths.
S6_INSTALL_ROOT = "/etc/s6-overlay/"


def _services() -> dict[str, str]:
    return {
        path.name: (path / "type").read_text().strip()
        for path in sorted(SERVICES_DIR.iterdir())
        if path.is_dir()
    }


def _longruns() -> list[str]:
    return [name for name, kind in _services().items() if kind == "longrun"]


def _oneshots() -> list[str]:
    return [name for name, kind in _services().items() if kind == "oneshot"]


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


@pytest.mark.parametrize("name", list(_services()))
def test_service_type_is_known(name: str) -> None:
    assert _services()[name] in {"oneshot", "longrun"}


def test_every_service_is_in_the_user_bundle() -> None:
    """s6-rc never starts a service no bundle names."""
    bundled = {path.name for path in USER_BUNDLE.iterdir()}
    assert bundled == set(_services())


@pytest.mark.parametrize("name", list(_services()))
def test_dependencies_name_existing_services(name: str) -> None:
    deps_dir = SERVICES_DIR / name / "dependencies.d"
    deps = {path.name for path in deps_dir.iterdir()} if deps_dir.is_dir() else set()
    assert deps, f"{name} has no dependencies, so it can start before romm-init"
    assert deps <= set(_services()) | S6_BUILTIN_SERVICES


@pytest.mark.parametrize("name", _longruns())
def test_longrun_is_bounded_and_swept(name: str) -> None:
    """Without these a dead service can strand PID 1 or keep its port bound."""
    service = SERVICES_DIR / name
    assert _is_executable(service / "run")
    assert _is_executable(service / "finish")
    assert "sweep-process-group" in (service / "finish").read_text()
    assert (service / "flag-timeout-killpg").is_file()
    assert int((service / "timeout-kill").read_text()) > 0
    assert "record_process_group" in (service / "run").read_text()


@pytest.mark.parametrize("name", _oneshots())
def test_oneshot_runs_an_executable_script(name: str) -> None:
    command = (SERVICES_DIR / name / "up").read_text().strip()
    assert command.startswith(S6_INSTALL_ROOT)
    assert _is_executable(S6_ROOT / command.removeprefix(S6_INSTALL_ROOT))


@pytest.mark.parametrize("script", sorted(SCRIPTS_DIR.iterdir()), ids=lambda p: p.name)
def test_scripts_are_executable_unless_sourced(script: Path) -> None:
    assert _is_executable(script) == (script.suffix != ".sh")


def _s6_rq_workers() -> set[tuple[str, ...]]:
    return {
        tuple(match.split())
        for path in SERVICES_DIR.glob("*/run")
        for match in re.findall(r"^exec_rq_worker (.+)$", path.read_text(), re.M)
    }


def _dev_rq_workers() -> set[tuple[str, ...]]:
    return {
        tuple(match.split()[1:])
        for match in re.findall(
            r"^\s*start_rq_worker (.+)$", DEV_ENTRYPOINT.read_text(), re.M
        )
    }


def test_dev_entrypoint_runs_the_same_rq_workers() -> None:
    """The dev image keeps its own launcher, so its queues must not drift."""
    assert _s6_rq_workers()
    assert _dev_rq_workers() == _s6_rq_workers()


def test_dev_entrypoint_runs_the_rq_cron_scheduler() -> None:
    assert "rq cron" in DEV_ENTRYPOINT.read_text()
    assert "tasks.cron_config" in (SERVICES_DIR / "romm-rq-cron" / "run").read_text()


def _rq_options(script: str, command: str) -> dict[str, str | None]:
    """Each --flag of the first `rq <command>` call, mapped to its value."""
    match = re.search(rf"\brq {command} \\\n((?:.*\\\n)*.*)", script)
    assert match, f"no `rq {command}` call found"
    return {
        flag: value
        for flag, value in re.findall(
            r"^\s*(--[\w-]+)(?: (.+?))?\s*\\?$", match.group(1), re.M
        )
    }


# The dev image writes PID files for its own tooling; s6 supervises without them.
DEV_ONLY_RQ_FLAGS = {"--pid"}

# The dev image runs from /app, and has no lib.sh to default LOGLEVEL to INFO.
DEV_RQ_VALUES = {
    "--path": ("/app/backend", "/backend"),
    "--logging_level": ('"${LOGLEVEL:-INFO}"', '"${LOGLEVEL}"'),
    "--logging-level": ('"${LOGLEVEL:-INFO}"', '"${LOGLEVEL}"'),
}


@pytest.mark.parametrize(
    ("command", "s6_script"),
    [
        ("worker", SCRIPTS_DIR / "lib.sh"),
        ("cron", SERVICES_DIR / "romm-rq-cron" / "run"),
    ],
)
def test_dev_entrypoint_passes_the_same_rq_options(
    command: str, s6_script: Path
) -> None:
    dev = _rq_options(DEV_ENTRYPOINT.read_text(), command)
    s6 = _rq_options(s6_script.read_text(), command)
    for flag in DEV_ONLY_RQ_FLAGS:
        dev.pop(flag, None)
    for flag, (dev_value, s6_value) in DEV_RQ_VALUES.items():
        if flag in dev and dev[flag] == dev_value:
            dev[flag] = s6_value
    assert dev == s6

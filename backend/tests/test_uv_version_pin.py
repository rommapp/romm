"""Assert both images pin the exact uv version ``pyproject.toml`` requires."""

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Each image pins uv its own way: the release build through a build arg, the
# devcontainer through the tag it copies the binary from.
IMAGE_PINS = {
    "docker/Dockerfile": r"^ARG UV_VERSION=(\S+)",
    "Dockerfile": r"^COPY --from=ghcr\.io/astral-sh/uv:(\S+?)\s",
}


def _required_version() -> str:
    config = tomllib.loads(PYPROJECT.read_text())
    required = config["tool"]["uv"].get("required-version", "")
    assert required, "pyproject.toml [tool.uv] is missing required-version"
    return str(required)


def test_required_version_is_an_exact_pin() -> None:
    # A range would let setup-uv resolve a newer uv than the images run.
    required = _required_version()
    assert re.fullmatch(
        r"==\S+", required
    ), f"required-version must be an exact '==' pin, got {required!r}"


@pytest.mark.parametrize(("dockerfile", "pattern"), IMAGE_PINS.items())
def test_image_uv_pin_matches_required_version(dockerfile: str, pattern: str) -> None:
    match = re.search(pattern, (REPO_ROOT / dockerfile).read_text(), re.M)
    assert match, f"{dockerfile} is missing a uv pin matching {pattern!r}"
    required = _required_version().removeprefix("==")
    assert match.group(1) == required, (
        f"{dockerfile} pins uv {match.group(1)}, not the required {required}; "
        f"its build would fail"
    )

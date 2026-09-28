"""Assert both images pin the same uv version, inside ``pyproject.toml``'s range."""

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

# Lower bound admits Dependabot's bundled uv; upper bound caps the minor so a
# lockfile format change can't slip in.
RANGE_PATTERN = r">=(\d+(?:\.\d+)*),<(\d+(?:\.\d+)*)"


def _version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def _required_range() -> tuple[tuple[int, ...], tuple[int, ...]]:
    config = tomllib.loads(PYPROJECT.read_text())
    required = str(config["tool"]["uv"].get("required-version", ""))
    match = re.fullmatch(RANGE_PATTERN, required)
    assert match, f"required-version must look like '>=X.Y.Z,<X.Y', got {required!r}"
    return _version(match.group(1)), _version(match.group(2))


def _image_pin(dockerfile: str, pattern: str) -> str:
    match = re.search(pattern, (REPO_ROOT / dockerfile).read_text(), re.M)
    assert match, f"{dockerfile} is missing a uv pin matching {pattern!r}"
    return match.group(1)


def test_required_version_caps_at_the_next_minor() -> None:
    lower, upper = _required_range()
    next_minor = (lower[0], lower[1] + 1)
    assert (
        upper == next_minor
    ), f"required-version upper bound must be {'.'.join(map(str, next_minor))}"


@pytest.mark.parametrize(("dockerfile", "pattern"), IMAGE_PINS.items())
def test_image_uv_pin_satisfies_required_version(dockerfile: str, pattern: str) -> None:
    pin = _image_pin(dockerfile, pattern)
    lower, upper = _required_range()
    assert lower <= _version(pin) < upper, (
        f"{dockerfile} pins uv {pin}, outside pyproject's required-version; "
        f"its build would fail"
    )


def test_images_pin_the_same_uv() -> None:
    pins = {name: _image_pin(name, pattern) for name, pattern in IMAGE_PINS.items()}
    assert len(set(pins.values())) == 1, f"images pin different uv versions: {pins}"

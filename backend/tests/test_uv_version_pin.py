"""Guards the uv version pin against drift between the images and CI.

``required-version`` in ``pyproject.toml`` is the single source of truth: CI's
``setup-uv`` resolves its uv from it, and both images copy ``pyproject.toml``
in and run ``uv sync``, which refuses to run on a mismatched version. Those
build-time checks only fire on a real image build, which is label-gated rather
than part of every CI run, so assert the pins agree here as well.
"""

import re
import tomllib
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Each image pins uv its own way: the release build through a build arg, the
# devcontainer through the tag it copies the binary from.
IMAGE_PINS = {
    "docker/Dockerfile": r"^ARG UV_VERSION=(\S+)",
    "Dockerfile": r"^COPY --from=ghcr\.io/astral-sh/uv:(\S+?)\s",
}


def _required_version() -> SpecifierSet:
    config = tomllib.loads(PYPROJECT.read_text())
    required = config["tool"]["uv"].get("required-version")
    assert required, "pyproject.toml [tool.uv] is missing required-version"
    return SpecifierSet(required)


@pytest.mark.parametrize(("dockerfile", "pattern"), IMAGE_PINS.items())
def test_image_uv_pin_satisfies_required_version(dockerfile: str, pattern: str) -> None:
    match = re.search(pattern, (REPO_ROOT / dockerfile).read_text(), re.M)
    assert match, f"{dockerfile} is missing a uv pin matching {pattern!r}"
    version = Version(match.group(1))
    required = _required_version()
    assert version in required, (
        f"{dockerfile} pins uv {version}, which does not satisfy "
        f"required-version {required}; its build would fail"
    )


def test_required_version_is_an_exact_pin() -> None:
    # A floor would let setup-uv resolve a newer uv than the images run, so a
    # lock written by it could pass CI and then fail the image build.
    specifiers = list(_required_version())
    assert (
        len(specifiers) == 1 and specifiers[0].operator == "=="
    ), f"required-version must pin one exact version, got {_required_version()}"

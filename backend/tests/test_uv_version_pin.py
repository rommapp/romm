"""Guards the uv version pin against drift between the image and CI.

``required-version`` in ``pyproject.toml`` is the single source of truth: CI's
``setup-uv`` resolves its uv from it, and the image build's ``uv sync`` refuses
to run when the pinned ``UV_VERSION`` falls outside it. That build-time check
only fires on a real image build, which is label-gated rather than part of
every CI run, so assert the two agree here as well.
"""

import re
import tomllib
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _dockerfile_uv_version() -> Version:
    match = re.search(r"^ARG UV_VERSION=(\S+)", DOCKERFILE.read_text(), re.M)
    assert match, "docker/Dockerfile is missing an ARG UV_VERSION pin"
    return Version(match.group(1))


def _required_version() -> SpecifierSet:
    config = tomllib.loads(PYPROJECT.read_text())
    required = config["tool"]["uv"].get("required-version")
    assert required, "pyproject.toml [tool.uv] is missing required-version"
    return SpecifierSet(required)


def test_image_uv_pin_satisfies_required_version() -> None:
    version = _dockerfile_uv_version()
    required = _required_version()
    assert version in required, (
        f"docker/Dockerfile pins uv {version}, which does not satisfy "
        f"required-version {required}; the image build would fail"
    )

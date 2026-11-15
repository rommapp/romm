"""Assert the dev and production images pin the same toolchain and assets."""

import re
import tomllib
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
DOCKERFILES = ("docker/Dockerfile", "Dockerfile")
JSDOS_RUNTIME = "frontend/src/views/Player/jsDosRuntime.ts"

ARG_PATTERN = re.compile(r"^ARG ([A-Z0-9_]+)=(\S+)", re.M)

# Lower bound admits Dependabot's bundled uv; upper bound caps the minor so a
# lockfile format change can't slip in.
RANGE_PATTERN = r">=(\d+(?:\.\d+)*),<(\d+(?:\.\d+)*)"


def _pins(dockerfile: str) -> dict[str, set[str]]:
    pins: dict[str, set[str]] = defaultdict(set)
    for name, value in ARG_PATTERN.findall((REPO_ROOT / dockerfile).read_text()):
        pins[name].add(value)
    return pins


def _pin(dockerfile: str, name: str) -> str:
    values = _pins(dockerfile).get(name)
    assert values, f"{dockerfile} is missing ARG {name}"
    assert len(values) == 1, f"{dockerfile} sets ARG {name} to {sorted(values)}"
    return values.pop()


def _shared_pins() -> list[str]:
    root, production = (_pins(path) for path in DOCKERFILES)
    return sorted(root.keys() & production.keys())


def _version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def _required_uv_range() -> tuple[tuple[int, ...], tuple[int, ...]]:
    config = tomllib.loads(PYPROJECT.read_text())
    required = str(config["tool"]["uv"].get("required-version", ""))
    match = re.fullmatch(RANGE_PATTERN, required)
    assert match, f"required-version must look like '>=X.Y.Z,<X.Y', got {required!r}"
    return _version(match.group(1)), _version(match.group(2))


def test_images_share_the_core_pins() -> None:
    # Guards the parametrized test below against a parser that matches nothing.
    shared = set(_shared_pins())
    for name in ("ALPINE_VERSION", "PYTHON_VERSION", "UV_VERSION", "JSDOS_VERSION"):
        assert name in shared, f"ARG {name} is not pinned in both Dockerfiles"


@pytest.mark.parametrize("name", _shared_pins())
def test_images_pin_the_same_value(name: str) -> None:
    values = {path: _pin(path, name) for path in DOCKERFILES}
    assert len(set(values.values())) == 1, f"ARG {name} differs: {values}"


def test_required_uv_version_caps_at_the_next_minor() -> None:
    lower, upper = _required_uv_range()
    next_minor = (lower[0], lower[1] + 1)
    assert (
        upper == next_minor
    ), f"required-version upper bound must be {'.'.join(map(str, next_minor))}"


@pytest.mark.parametrize("dockerfile", DOCKERFILES)
def test_image_uv_pin_satisfies_required_version(dockerfile: str) -> None:
    pin = _pin(dockerfile, "UV_VERSION")
    lower, upper = _required_uv_range()
    assert lower <= _version(pin) < upper, (
        f"{dockerfile} pins uv {pin}, outside pyproject's required-version; "
        f"its build would fail"
    )


def test_jsdos_cdn_fallback_matches_the_image() -> None:
    image = _pin(DOCKERFILES[0], "JSDOS_VERSION")
    match = re.search(
        r"cdn\.jsdelivr\.net/npm/js-dos@([^/]+)/dist",
        (REPO_ROOT / JSDOS_RUNTIME).read_text(),
    )
    assert match, f"{JSDOS_RUNTIME} is missing the js-dos CDN URL"
    assert (
        match.group(1) == image
    ), f"{JSDOS_RUNTIME} loads js-dos {match.group(1)}, the image ships {image}"

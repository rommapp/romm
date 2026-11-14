"""Assert both images and the player's CDN fallback pin the same js-dos release."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILES = ("docker/Dockerfile", "Dockerfile")
CDN_RUNTIME = "frontend/src/views/Player/jsDosRuntime.ts"


def _pin(path: str, pattern: str) -> str:
    match = re.search(pattern, (REPO_ROOT / path).read_text(), re.M)
    assert match, f"{path} is missing a js-dos pin matching {pattern!r}"
    return match.group(1)


def test_images_pin_the_same_jsdos_release() -> None:
    pins = {
        path: (
            _pin(path, r"^ARG JSDOS_VERSION=(\S+)"),
            _pin(path, r"^ARG JSDOS_SHA256=(\S+)"),
        )
        for path in DOCKERFILES
    }
    assert (
        len(set(pins.values())) == 1
    ), f"images pin different js-dos releases (version, sha256): {pins}"


def test_cdn_fallback_matches_the_image_jsdos() -> None:
    image = _pin(DOCKERFILES[0], r"^ARG JSDOS_VERSION=(\S+)")
    cdn = _pin(CDN_RUNTIME, r"cdn\.jsdelivr\.net/npm/js-dos@([^/]+)/dist")
    assert cdn == image, f"{CDN_RUNTIME} loads js-dos {cdn}, the image ships {image}"

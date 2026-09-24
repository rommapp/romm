"""Assert the frontend precompresses its assets and only they are served as .gz."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = REPO_ROOT / "docker" / "nginx" / "default.conf"
NGINX_TEMPLATE = REPO_ROOT / "docker" / "nginx" / "templates" / "default.conf.template"
VITE_CONFIG = REPO_ROOT / "frontend" / "vite.config.js"
PRECOMPRESS_PLUGIN = REPO_ROOT / "frontend" / "scripts" / "precompress.ts"

# Served from the frontend build, where every .gz sibling is one the build wrote.
PRECOMPRESSED_LOCATIONS = ["/", "/assets"]

# The fingerprinted-bundle location is a regex, keyed by its opening so the
# test does not restate the pattern.
FINGERPRINTED_LOCATION = '~* "^/assets/'

# Internal download locations. A library may hold both `Game.nes` and
# `Game.nes.gz`, so gzip_static here would answer a request for one with the
# other's bytes under Content-Encoding: gzip.
RAW_LOCATIONS = ["/library/", "/cache/", "/assets/romm/resources/"]


def _strip_comments(config: str) -> str:
    return re.sub(r"#[^\n]*", "", config)


def _blocks(config: str) -> list[tuple[str, str, int, int]]:
    """Every location as (matcher, body, start, end), quoted regexes included."""
    found = []
    for match in re.finditer(r"\blocation\b", config):
        # The matcher may embed braces inside a quoted regex, so scan for the
        # opening brace rather than splitting on the first one.
        i, quoted = match.end(), False
        while config[i] != "{" or quoted:
            quoted ^= config[i] == '"'
            i += 1
        depth, j = 1, i + 1
        while depth:
            depth += (config[j] == "{") - (config[j] == "}")
            j += 1
        found.append(
            (config[match.end() : i].strip(), config[i + 1 : j - 1], match.start(), j)
        )
    return found


def _locations(config: str) -> dict[str, str]:
    return {matcher: body for matcher, body, _, _ in _blocks(_strip_comments(config))}


def _outside_locations(config: str) -> str:
    """The server-scope directives, with every location block removed."""
    stripped = _strip_comments(config)
    for _, _, start, end in reversed(_blocks(stripped)):
        stripped = stripped[:start] + stripped[end:]
    return stripped


def _matcher(config: str, key: str) -> str:
    """Resolve a location key to its matcher, exactly or by its opening."""
    locations = _locations(config)
    if key in locations:
        return key
    opening = [m for m in locations if m.startswith(key)]
    if len(opening) != 1:
        pytest.fail(f"{key!r} matched {sorted(opening)} in {sorted(locations)}")
    return opening[0]


def _body(config: str, key: str) -> str:
    return _locations(config)[_matcher(config, key)]


def _enables_gzip_static(body: str) -> bool:
    return bool(re.search(r"^\s*gzip_static\s+on;", body, re.M))


def test_gzip_static_is_not_enabled_above_the_locations() -> None:
    # At http or server scope every location inherits it, the internal
    # download locations included.
    assert not _enables_gzip_static(_strip_comments(NGINX_CONF.read_text()))
    assert not _enables_gzip_static(_outside_locations(NGINX_TEMPLATE.read_text()))


@pytest.mark.parametrize("key", [*PRECOMPRESSED_LOCATIONS, FINGERPRINTED_LOCATION])
def test_build_output_is_served_precompressed(key: str) -> None:
    body = _body(NGINX_TEMPLATE.read_text(), key)
    assert _enables_gzip_static(body), f"location {key} would ignore the .gz siblings"


def test_no_other_location_serves_a_gz_sibling() -> None:
    config = NGINX_TEMPLATE.read_text()
    enabled = {
        matcher
        for matcher, body in _locations(config).items()
        if _enables_gzip_static(body)
    }
    expected = {*PRECOMPRESSED_LOCATIONS, _matcher(config, FINGERPRINTED_LOCATION)}
    unexpected = enabled - expected
    assert not unexpected, (
        f"{sorted(unexpected)} serve files RomM did not precompress, so a "
        f"request for Game.nes would return Game.nes.gz's bytes"
    )


@pytest.mark.parametrize("path", RAW_LOCATIONS)
def test_downloads_are_never_served_from_a_gz_sibling(path: str) -> None:
    body = _body(NGINX_TEMPLATE.read_text(), path)
    assert not _enables_gzip_static(body), (
        f"gzip_static in {path} would serve a .gz sibling instead of the "
        f"requested file"
    )


def test_build_threshold_matches_nginx_gzip_min_length() -> None:
    build = re.search(r"MIN_BYTES\s*=\s*(\d+)", PRECOMPRESS_PLUGIN.read_text())
    served = re.search(r"gzip_min_length\s+(\d+);", NGINX_CONF.read_text())
    assert build and served
    assert build.group(1) == served.group(1), (
        "the build and nginx disagree on the smallest file worth compressing, "
        "so the precompressed set no longer matches the serving policy"
    )


def test_build_precompresses() -> None:
    config = VITE_CONFIG.read_text()
    assert re.search(r"\bprecompress\(\)", config), (
        "vite.config.js no longer runs the precompress plugin, so the "
        "gzip_static locations would have nothing to serve"
    )

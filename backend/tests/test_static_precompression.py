"""Assert the frontend precompresses its assets and only they are served as .gz."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = REPO_ROOT / "docker" / "nginx" / "default.conf"
NGINX_TEMPLATE = REPO_ROOT / "docker" / "nginx" / "templates" / "default.conf.template"
VITE_CONFIG = REPO_ROOT / "frontend" / "vite.config.js"

# Served from the frontend build, where every .gz sibling is one the build wrote.
PRECOMPRESSED_LOCATIONS = ["/", "/assets"]

# Internal download locations. A library may hold both `Game.nes` and
# `Game.nes.gz`, so gzip_static here would answer a request for one with the
# other's bytes under Content-Encoding: gzip.
RAW_LOCATIONS = ["/library/", "/cache/", "/assets/romm/resources/"]


def _location_body(config: str, path: str) -> str:
    start = config.index(f"location {path} {{") + len(f"location {path} {{")
    depth, i = 1, start
    while depth:
        if config[i] == "{":
            depth += 1
        elif config[i] == "}":
            depth -= 1
        i += 1
    return config[start : i - 1]


def _enables_gzip_static(body: str) -> bool:
    return bool(re.search(r"^\s*gzip_static\s+on;", body, re.M))


def test_gzip_static_is_not_inherited_by_every_location() -> None:
    # In the http block it would reach the internal download locations too.
    assert not _enables_gzip_static(NGINX_CONF.read_text())


@pytest.mark.parametrize("path", PRECOMPRESSED_LOCATIONS)
def test_build_output_is_served_precompressed(path: str) -> None:
    body = _location_body(NGINX_TEMPLATE.read_text(), path)
    assert _enables_gzip_static(body), f"location {path} would ignore the .gz siblings"


@pytest.mark.parametrize("path", RAW_LOCATIONS)
def test_downloads_are_never_served_from_a_gz_sibling(path: str) -> None:
    body = _location_body(NGINX_TEMPLATE.read_text(), path)
    assert not _enables_gzip_static(body), (
        f"gzip_static in {path} would serve a .gz sibling instead of the "
        f"requested file"
    )


def test_build_precompresses() -> None:
    config = VITE_CONFIG.read_text()
    assert re.search(r"\bprecompress\(\)", config), (
        "vite.config.js no longer runs the precompress plugin, so the "
        "gzip_static locations would have nothing to serve"
    )

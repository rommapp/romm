"""Assert the frontend precompresses its assets and nginx is set to serve them."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = REPO_ROOT / "docker" / "nginx" / "default.conf"
VITE_CONFIG = REPO_ROOT / "frontend" / "vite.config.js"


def test_nginx_serves_precompressed_assets() -> None:
    assert re.search(
        r"^\s*gzip_static\s+on;", NGINX_CONF.read_text(), re.M
    ), "gzip_static is off, so the .gz files the build writes would go unused"


def test_build_precompresses() -> None:
    config = VITE_CONFIG.read_text()
    assert "precompress" in config and re.search(r"\bprecompress\(\)", config), (
        "vite.config.js no longer runs the precompress plugin, so nginx's "
        "gzip_static would have nothing to serve"
    )

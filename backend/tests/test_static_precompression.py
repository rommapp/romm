"""Assert the frontend precompresses its assets and nginx is set to serve them."""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = REPO_ROOT / "docker" / "nginx" / "default.conf"
PACKAGE_JSON = REPO_ROOT / "frontend" / "package.json"


def test_nginx_serves_precompressed_assets() -> None:
    assert re.search(
        r"^\s*gzip_static\s+on;", NGINX_CONF.read_text(), re.M
    ), "gzip_static is off, so the .gz files the build writes would go unused"


def test_build_precompresses() -> None:
    # frontend/.npmrc sets ignore-scripts, so a postbuild hook would never fire
    # and the step has to stay chained into build itself.
    scripts = json.loads(PACKAGE_JSON.read_text())["scripts"]
    assert "precompress" in scripts["build"], (
        "npm run build no longer runs precompress, so nginx's gzip_static would "
        "have nothing to serve"
    )

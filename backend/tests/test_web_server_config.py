"""Guards two serving-layer settings that live outside Python.

* ``gzip_types`` in the nginx config must cover the compressible types the
  image actually serves. The emulator cores (``.wasm``) and logos (``.svg``)
  are the large ones, and neither type is in nginx's ``gzip_types`` default,
  so leaving them out ships them uncompressed.
* Gunicorn's keep-alive must outlive nginx's upstream idle timeout. Upstream
  keepalive is on by default since nginx 1.29.7, so a shorter gunicorn value
  lets nginx reuse a connection gunicorn is closing, surfacing as
  intermittent 502s under load.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = REPO_ROOT / "docker" / "nginx" / "default.conf"
INIT_SCRIPT = REPO_ROOT / "docker" / "init_scripts" / "init"
ENV_TEMPLATE = REPO_ROOT / "env.template"

# nginx's own default upstream keepalive_timeout, which gunicorn must outlive.
NGINX_UPSTREAM_IDLE_TIMEOUT = 60

REQUIRED_GZIP_TYPES = [
    "application/wasm",  # EmulatorJS, js-dos and FAKE-08 cores
    "image/svg+xml",  # player logos and favicons
    "application/json",
    "application/javascript",
    "text/css",
]


def _init_script_keepalive() -> int:
    """Return the gunicorn --keep-alive default baked into the init script."""
    match = re.search(
        r'--keep-alive "\$\{WEB_SERVER_KEEPALIVE:-(\d+)\}"', INIT_SCRIPT.read_text()
    )
    assert match, "could not read the gunicorn --keep-alive default"
    return int(match.group(1))


@pytest.fixture(scope="module")
def gzip_types() -> set[str]:
    match = re.search(r"\bgzip_types\s+([^;]+);", NGINX_CONF.read_text())
    assert match, "no gzip_types directive in the nginx config"
    return set(match.group(1).split())


@pytest.mark.parametrize("media_type", REQUIRED_GZIP_TYPES)
def test_compressible_types_are_gzipped(gzip_types: set[str], media_type: str) -> None:
    assert media_type in gzip_types, f"{media_type} would be served uncompressed"


def test_gunicorn_outlives_nginx_upstream_idle_timeout() -> None:
    assert _init_script_keepalive() > NGINX_UPSTREAM_IDLE_TIMEOUT


def test_env_template_documents_the_same_keepalive_default() -> None:
    match = re.search(r"^WEB_SERVER_KEEPALIVE=(\d+)", ENV_TEMPLATE.read_text(), re.M)
    assert match, "env.template is missing WEB_SERVER_KEEPALIVE"
    assert int(match.group(1)) == _init_script_keepalive()

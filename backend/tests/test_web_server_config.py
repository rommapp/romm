"""Guards the serving-layer settings that live outside Python."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = REPO_ROOT / "docker" / "nginx" / "default.conf"
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"
INIT_SCRIPT = REPO_ROOT / "docker" / "init_scripts" / "init"
ENV_TEMPLATE = REPO_ROOT / "env.template"

# nginx's own default upstream keepalive_timeout, which gunicorn must outlive.
NGINX_UPSTREAM_IDLE_TIMEOUT = 60

# nginx enables upstream keepalive by default from this release. Below it the
# pool is off entirely and the timeout invariant stops meaning anything.
NGINX_UPSTREAM_KEEPALIVE_SINCE = (1, 29, 7)

# njs 0.9.7 dropped the "js vm init njs" notice it logged on every start. nginx
# 1.30.0 also shipped builds bundling njs 0.9.6, so 1.30.1 is the first release
# that never logs it.
NJS_QUIET_STARTUP_SINCE = (1, 30, 1)

REQUIRED_GZIP_TYPES = [
    "application/wasm",  # EmulatorJS, js-dos and FAKE-08 cores
    "image/svg+xml",  # player logos and favicons
    "application/json",
    "application/javascript",
    "text/css",
]


def _init_script_keepalive() -> int:
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


def _format(version: tuple[int, ...]) -> str:
    return ".".join(str(part) for part in version)


def _nginx_version() -> tuple[int, ...]:
    match = re.search(r"^ARG NGINX_VERSION=(\S+)", DOCKERFILE.read_text(), re.M)
    assert match, "docker/Dockerfile is missing an ARG NGINX_VERSION pin"
    return tuple(int(part) for part in match.group(1).split("."))


def test_nginx_defaults_upstream_keepalive_on() -> None:
    version = _nginx_version()
    assert version >= NGINX_UPSTREAM_KEEPALIVE_SINCE, (
        f"nginx {_format(version)} does not pool upstream connections by default, "
        f"so every API request opens a new one"
    )


def test_nginx_starts_without_the_njs_notice() -> None:
    version = _nginx_version()
    assert version >= NJS_QUIET_STARTUP_SINCE, (
        f"nginx {_format(version)} bundles an njs that logs a 'js vm init njs' "
        f"notice on every start, because the config imports a VM at the http level"
    )


def test_gunicorn_outlives_nginx_upstream_idle_timeout() -> None:
    assert _init_script_keepalive() > NGINX_UPSTREAM_IDLE_TIMEOUT


def test_init_script_records_the_rq_worker_pid_at_launch() -> None:
    match = re.search(
        r"^start_rq_worker\(\) \{\n(.*?)^\}", INIT_SCRIPT.read_text(), re.M | re.S
    )
    assert match, "could not read start_rq_worker from the init script"
    body = match.group(1)
    assert not re.search(r"^\s*--pid\b", body, re.M), (
        "RQ writes --pid only after importing the worker class, so the watchdog "
        "would start duplicate workers while a slow import runs"
    )
    assert re.search(r'^\s*echo "\$!" >"/tmp/\$\{name\}\.pid"$', body, re.M)


def test_env_template_documents_the_same_keepalive_default() -> None:
    match = re.search(r"^WEB_SERVER_KEEPALIVE=(\d+)", ENV_TEMPLATE.read_text(), re.M)
    assert match, "env.template is missing WEB_SERVER_KEEPALIVE"
    assert int(match.group(1)) == _init_script_keepalive()

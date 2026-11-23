"""Guards docker/gunicorn/gunicorn.conf.py, the API's preload and garbage-collector hooks."""

import gc
import importlib.util
import threading
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

CONF = Path(__file__).resolve().parents[2] / "docker" / "gunicorn" / "gunicorn.conf.py"

# The dev container only mounts backend/, so docker/ isn't there.
pytestmark = pytest.mark.skipif(
    not CONF.exists(), reason="docker/ is not in this checkout"
)


@pytest.fixture(autouse=True)
def restore_gc() -> Iterator[None]:
    yield
    gc.unfreeze()
    gc.enable()


def _load(monkeypatch, **env: str) -> ModuleType:
    monkeypatch.delenv("WEB_SERVER_PRELOAD", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("gunicorn_conf", CONF)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_off_by_default(monkeypatch) -> None:
    conf = _load(monkeypatch)

    assert conf.preload_app is False
    assert gc.isenabled()
    conf.pre_fork(MagicMock(), None)
    assert gc.get_freeze_count() == 0


def test_preload_follows_its_setting(monkeypatch) -> None:
    assert _load(monkeypatch, WEB_SERVER_PRELOAD="true").preload_app is True


def test_gc_is_off_from_load_until_the_worker_starts(monkeypatch) -> None:
    conf = _load(monkeypatch, WEB_SERVER_PRELOAD="true")

    assert not gc.isenabled()
    conf.pre_fork(MagicMock(), None)
    assert gc.get_freeze_count() > 0
    conf.post_fork(MagicMock(), None)
    assert gc.isenabled()


def test_a_thread_alive_before_fork_is_named(monkeypatch) -> None:
    conf = _load(monkeypatch)
    server = MagicMock()
    stop = threading.Event()
    thread = threading.Thread(target=stop.wait, name="leftover-exporter")
    thread.start()
    try:
        conf.pre_fork(server, None)
    finally:
        stop.set()
        thread.join()

    assert server.log.warning.call_args is not None
    message, names = server.log.warning.call_args.args
    assert "Threads alive before fork" in message
    assert "leftover-exporter" in names


def test_no_threads_no_warning(monkeypatch) -> None:
    conf = _load(monkeypatch)
    server = MagicMock()
    stray = [t for t in threading.enumerate() if t is not threading.main_thread()]
    if stray:
        pytest.skip("the test runner has threads of its own")

    conf.pre_fork(server, None)

    server.log.warning.assert_not_called()

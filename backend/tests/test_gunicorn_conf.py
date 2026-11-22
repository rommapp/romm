"""Guards docker/gunicorn/gunicorn.conf.py, the API's preload and garbage-collector hooks."""

import gc
import importlib.util
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
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


@pytest.fixture(autouse=True)
def no_real_database(monkeypatch) -> None:
    # post_fork would otherwise dispose the test run's own engine.
    monkeypatch.delitem(sys.modules, "handler.database.base_handler", raising=False)


def _fake_engine(monkeypatch, connections: int) -> MagicMock:
    engine = MagicMock()
    engine.pool.checkedin.return_value = connections
    engine.pool.checkedout.return_value = 0
    monkeypatch.setitem(
        sys.modules,
        "handler.database.base_handler",
        SimpleNamespace(sync_engine=engine),
    )
    return engine


def _load(monkeypatch, **env: str) -> ModuleType:
    for name in ("_POC_WEB_SERVER_PRELOAD", "_POC_WEB_SERVER_GC_FREEZE"):
        monkeypatch.delenv(name, raising=False)
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
    assert _load(monkeypatch, _POC_WEB_SERVER_PRELOAD="true").preload_app is True


def test_gc_is_off_from_load_until_the_worker_starts(monkeypatch) -> None:
    conf = _load(
        monkeypatch, _POC_WEB_SERVER_PRELOAD="true", _POC_WEB_SERVER_GC_FREEZE="true"
    )

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


def test_a_database_connection_open_before_fork_is_reported(monkeypatch) -> None:
    conf = _load(monkeypatch)
    _fake_engine(monkeypatch, connections=2)
    server = MagicMock()

    conf.pre_fork(server, None)

    message, opened = server.log.warning.call_args.args
    assert "Database connections open before fork" in message
    assert opened == 2


def test_an_unused_pool_is_not_reported(monkeypatch) -> None:
    conf = _load(monkeypatch)
    _fake_engine(monkeypatch, connections=0)
    server = MagicMock()

    conf.pre_fork(server, None)

    assert not any(
        "Database" in call.args[0] for call in server.log.warning.call_args_list
    )


def test_each_worker_starts_its_own_pool_and_keeps_the_inherited_one(
    monkeypatch,
) -> None:
    conf = _load(monkeypatch)
    engine = _fake_engine(monkeypatch, connections=1)
    inherited = engine.pool

    conf.post_fork(MagicMock(), None)

    engine.dispose.assert_called_once_with(close=False)
    assert inherited in conf._inherited_pools


def test_without_the_app_loaded_post_fork_touches_no_database(monkeypatch) -> None:
    conf = _load(monkeypatch)

    conf.post_fork(MagicMock(), None)

    assert conf._inherited_pools == []

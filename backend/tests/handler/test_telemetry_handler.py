from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import psutil
import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from handler import telemetry_handler

valkey = telemetry_handler._valkey

INFO = {
    "memory": {
        "used_memory": 4_000_000,
        "used_memory_peak": 5_000_000,
        "maxmemory": 0,
        "maxmemory_policy": "noeviction",
    },
    "stats": {"evicted_keys": 7},
    "keyspace": {"db0": {"keys": 42, "expires": 3}},
}


@pytest.fixture
def reader(mocker) -> InMemoryMetricReader:
    # The real process list varies by machine, so it stays out of these tests.
    mocker.patch("handler.telemetry_handler.psutil.process_iter", return_value=[])
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    telemetry_handler.register_gauges(provider.get_meter("test"))
    return reader


def collected(reader: InMemoryMetricReader) -> dict[str, list[Any]]:
    data = reader.get_metrics_data()
    if data is None:
        return {}
    return {
        metric.name: list(metric.data.data_points)
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }


def test_reports_valkey_memory_queues_and_workers(mocker, reader) -> None:
    mocker.patch.object(valkey, "info", side_effect=INFO.__getitem__)
    mocker.patch.object(valkey, "llen", return_value=3)
    mocker.patch(
        "handler.telemetry_handler.ALL_QUEUES",
        (SimpleNamespace(name="scans", key="rq:queue:scans"),),
    )
    mocker.patch("handler.telemetry_handler.Worker.count", return_value=2)

    metrics = collected(reader)

    memory = {
        point.attributes["valkey.memory.state"]: point.value
        for point in metrics["romm.valkey.memory"]
    }
    assert memory == {"used": 4_000_000, "peak": 5_000_000, "limit": 0}
    assert metrics["romm.valkey.evicted_keys"][0].value == 7
    assert metrics["romm.valkey.keys"][0].value == 42
    assert dict(metrics["romm.valkey.keys"][0].attributes) == {"valkey.db": "db0"}
    depth = metrics["romm.rq.queue.depth"][0]
    assert depth.value == 3
    assert dict(depth.attributes) == {"messaging.destination.name": "scans"}
    assert metrics["romm.rq.workers"][0].value == 2


def test_unreachable_valkey_reports_no_points(mocker, reader) -> None:
    mocker.patch.object(valkey, "info", side_effect=RedisConnectionError())
    mocker.patch(
        "handler.telemetry_handler.Worker.count", side_effect=RedisConnectionError()
    )
    mocker.patch("handler.telemetry_handler.ALL_QUEUES", ())

    metrics = collected(reader)

    assert not any(metrics.values())


def test_valkey_reads_give_up_after_a_timeout() -> None:
    options = valkey.connection_pool.connection_kwargs

    assert options["socket_timeout"] == telemetry_handler.VALKEY_READ_TIMEOUT_SECONDS
    assert (
        options["socket_connect_timeout"]
        == telemetry_handler.VALKEY_READ_TIMEOUT_SECONDS
    )


def test_a_stalled_valkey_still_lets_process_memory_through(mocker) -> None:
    mocker.patch.object(valkey, "info", side_effect=RedisTimeoutError())
    mocker.patch.object(valkey, "llen", side_effect=RedisTimeoutError())
    mocker.patch(
        "handler.telemetry_handler.Worker.count", side_effect=RedisTimeoutError()
    )
    mocker.patch(
        "handler.telemetry_handler.ALL_QUEUES",
        (SimpleNamespace(name="scans", key="rq:queue:scans"),),
    )
    mocker.patch(
        "handler.telemetry_handler.psutil.process_iter",
        return_value=[
            _process(
                10,
                ["/src/.venv/bin/gunicorn", "main:app"],
                SimpleNamespace(rss=400, pss=300, uss=200, swap=0),
            )
        ],
    )
    reader = InMemoryMetricReader()
    telemetry_handler.register_gauges(
        MeterProvider(metric_readers=[reader]).get_meter("test")
    )

    metrics = collected(reader)

    assert not metrics.get("romm.valkey.memory")
    assert not metrics.get("romm.rq.queue.depth")
    assert len(metrics["romm.process.memory"]) == 4


def _process(pid: int, cmdline: list[str], memory: object) -> MagicMock:
    proc = MagicMock(pid=pid, info={"cmdline": cmdline, "ppid": 1})
    if isinstance(memory, Exception):
        proc.memory_full_info.side_effect = memory
    else:
        proc.memory_full_info.return_value = memory
    return proc


def test_process_memory_reports_rss_pss_and_uss_of_romm_processes_only(mocker) -> None:
    mocker.patch(
        "handler.telemetry_handler.psutil.process_iter",
        return_value=[
            _process(
                10,
                ["/src/.venv/bin/gunicorn", "main:app"],
                SimpleNamespace(rss=400, pss=300, uss=200, swap=0),
            ),
            _process(
                11,
                ["/usr/lib/firefox/firefox"],
                SimpleNamespace(rss=9, pss=9, uss=9, swap=0),
            ),
            _process(12, ["/src/.venv/bin/rq", "cron"], psutil.AccessDenied(12)),
        ],
    )

    observations = list(telemetry_handler._process_memory(MagicMock()))

    assert [
        (o.value, (o.attributes or {})["process.memory.kind"]) for o in observations
    ] == [
        (400, "rss"),
        (300, "pss"),
        (200, "uss"),
        (0, "swap"),
    ]
    attributes = observations[0].attributes
    assert attributes is not None
    assert attributes["romm.process.role"] == "api"
    assert attributes["process.pid"] == 10
    assert attributes["romm.process.kind"] == "master"


def _gunicorn(**readings: object) -> MagicMock:
    proc = MagicMock(pid=10, info={"cmdline": ["/src/.venv/bin/gunicorn"], "ppid": 1})
    for name, value in readings.items():
        getattr(proc, name).return_value = value
    return proc


@pytest.mark.parametrize(
    "callback,readings,expected",
    [
        (
            "_process_cpu_time",
            {"cpu_times": SimpleNamespace(user=1.5, system=0.5)},
            [(1.5, {"cpu.mode": "user"}), (0.5, {"cpu.mode": "system"})],
        ),
        ("_process_threads", {"num_threads": 12}, [(12, {})]),
        ("_process_open_fds", {"num_fds": 40}, [(40, {})]),
        (
            "_process_disk_io",
            {"io_counters": SimpleNamespace(read_bytes=4096, write_bytes=512)},
            [
                (4096, {"disk.io.direction": "read"}),
                (512, {"disk.io.direction": "write"}),
            ],
        ),
    ],
)
def test_process_readings_carry_the_process_role(
    mocker, callback, readings, expected
) -> None:
    mocker.patch(
        "handler.telemetry_handler.psutil.process_iter",
        return_value=[_gunicorn(**readings)],
    )

    observations = list(getattr(telemetry_handler, callback)(MagicMock()))

    base = {
        "process.pid": 10,
        "process.parent_pid": 1,
        "romm.process.role": "api",
        "romm.process.kind": "master",
    }
    assert [(o.value, dict(o.attributes or {})) for o in observations] == [
        (value, {**base, **extra}) for value, extra in expected
    ]


def test_a_process_that_exits_mid_read_is_skipped(mocker) -> None:
    proc = _gunicorn()
    proc.cpu_times.side_effect = psutil.NoSuchProcess(10)
    mocker.patch("handler.telemetry_handler.psutil.process_iter", return_value=[proc])

    assert list(telemetry_handler._process_cpu_time(MagicMock())) == []

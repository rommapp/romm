from types import SimpleNamespace
from typing import Any

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from redis.exceptions import ConnectionError as RedisConnectionError

from handler import telemetry_handler
from handler.redis_handler import redis_client

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
def reader() -> InMemoryMetricReader:
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
    mocker.patch.object(redis_client, "info", side_effect=INFO.__getitem__)
    mocker.patch(
        "handler.telemetry_handler.ALL_QUEUES",
        (SimpleNamespace(name="scans", count=3),),
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
    mocker.patch.object(redis_client, "info", side_effect=RedisConnectionError())
    mocker.patch(
        "handler.telemetry_handler.Worker.count", side_effect=RedisConnectionError()
    )
    mocker.patch("handler.telemetry_handler.ALL_QUEUES", ())

    metrics = collected(reader)

    assert not any(metrics.values())

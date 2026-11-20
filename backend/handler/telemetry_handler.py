"""Valkey and RQ gauges, read on each OpenTelemetry metric export."""

from collections.abc import Callable, Iterable

from opentelemetry import metrics
from opentelemetry.metrics import CallbackOptions, Meter, Observation
from redis.exceptions import RedisError
from rq import Worker

from handler.redis_handler import ALL_QUEUES, redis_client

ObservationCallback = Callable[[CallbackOptions], Iterable[Observation]]


def _skip_when_unreachable(callback: ObservationCallback) -> ObservationCallback:
    # A failed read yields no point, rather than an error log every interval.
    def observe(options: CallbackOptions) -> Iterable[Observation]:
        try:
            return list(callback(options))
        except RedisError:
            return []

    return observe


def _valkey_memory(_: CallbackOptions) -> Iterable[Observation]:
    info = redis_client.info("memory")
    yield Observation(int(info["used_memory"]), {"valkey.memory.state": "used"})
    yield Observation(int(info["used_memory_peak"]), {"valkey.memory.state": "peak"})
    # 0 when Valkey has no limit.
    yield Observation(
        int(info["maxmemory"]),
        {
            "valkey.memory.state": "limit",
            "valkey.maxmemory_policy": str(info["maxmemory_policy"]),
        },
    )


def _valkey_evicted_keys(_: CallbackOptions) -> Iterable[Observation]:
    yield Observation(int(redis_client.info("stats")["evicted_keys"]))


def _valkey_keys(_: CallbackOptions) -> Iterable[Observation]:
    for db, stats in redis_client.info("keyspace").items():
        yield Observation(int(stats["keys"]), {"valkey.db": db})


def _queue_depth(_: CallbackOptions) -> Iterable[Observation]:
    for queue in ALL_QUEUES:
        yield Observation(queue.count, {"messaging.destination.name": queue.name})


def _workers(_: CallbackOptions) -> Iterable[Observation]:
    yield Observation(Worker.count(connection=redis_client))


def register_gauges(meter: Meter | None = None) -> None:
    """Register the gauges. Call once per container, from one long-lived process."""
    meter = meter or metrics.get_meter(__name__)
    meter.create_observable_gauge(
        "romm.valkey.memory",
        [_skip_when_unreachable(_valkey_memory)],
        unit="By",
        description="Valkey memory in use, its peak, and its limit",
    )
    meter.create_observable_counter(
        "romm.valkey.evicted_keys",
        [_skip_when_unreachable(_valkey_evicted_keys)],
        description="Keys Valkey evicted to stay under its memory limit",
    )
    meter.create_observable_gauge(
        "romm.valkey.keys",
        [_skip_when_unreachable(_valkey_keys)],
        description="Keys per Valkey database",
    )
    meter.create_observable_gauge(
        "romm.rq.queue.depth",
        [_skip_when_unreachable(_queue_depth)],
        description="Jobs waiting in each RQ queue",
    )
    meter.create_observable_gauge(
        "romm.rq.workers",
        [_skip_when_unreachable(_workers)],
        description="Registered RQ workers",
    )

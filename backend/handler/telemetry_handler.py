"""Valkey, RQ and RomM process gauges, read on each OpenTelemetry export."""

from collections.abc import Callable, Iterable, Iterator
from typing import Final

import psutil
from opentelemetry import metrics
from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.metrics import CallbackOptions, Meter, Observation
from redis import Redis
from redis.exceptions import RedisError
from rq import Worker

from config import REDIS_URL
from handler.redis_handler import ALL_QUEUES, REDIS_CLIENT_OPTIONS
from utils.process_stats import process_kinds, romm_processes

ObservationCallback = Callable[[CallbackOptions], Iterable[Observation]]

# One stalled Valkey read would hold up every gauge in the collection, process
# memory included, and the shared client has no timeout.
VALKEY_READ_TIMEOUT_SECONDS: Final = 2
_valkey = Redis.from_url(
    REDIS_URL,
    socket_timeout=VALKEY_READ_TIMEOUT_SECONDS,
    socket_connect_timeout=VALKEY_READ_TIMEOUT_SECONDS,
    **REDIS_CLIENT_OPTIONS,
)


def _read_quietly(callback: ObservationCallback) -> ObservationCallback:
    # Each read would otherwise be traced as its own one-span Redis trace, and a
    # failed read yields no point rather than an error log every interval.
    def observe(options: CallbackOptions) -> Iterable[Observation]:
        try:
            with suppress_instrumentation():
                return list(callback(options))
        except RedisError:
            return []

    return observe


def _valkey_memory(_: CallbackOptions) -> Iterable[Observation]:
    info = _valkey.info("memory")
    yield Observation(int(info["used_memory"]), {"valkey.memory.state": "used"})
    yield Observation(int(info["used_memory_peak"]), {"valkey.memory.state": "peak"})
    # Valkey reports 0 when it has no limit.
    yield Observation(
        int(info["maxmemory"]),
        {
            "valkey.memory.state": "limit",
            "valkey.maxmemory_policy": str(info["maxmemory_policy"]),
        },
    )


def _valkey_evicted_keys(_: CallbackOptions) -> Iterable[Observation]:
    yield Observation(int(_valkey.info("stats")["evicted_keys"]))


def _valkey_keys(_: CallbackOptions) -> Iterable[Observation]:
    for db, stats in _valkey.info("keyspace").items():
        yield Observation(int(stats["keys"]), {"valkey.db": db})


def _queue_depth(_: CallbackOptions) -> Iterable[Observation]:
    for queue in ALL_QUEUES:
        # The same count as queue.count, read through the client with a timeout.
        depth = _valkey.llen(queue.key)
        yield Observation(depth, {"messaging.destination.name": queue.name})


def _workers(_: CallbackOptions) -> Iterable[Observation]:
    yield Observation(Worker.count(connection=_valkey))


def _romm_processes() -> Iterator[tuple[psutil.Process, dict[str, str | int]]]:
    processes = list(romm_processes())
    kinds = process_kinds(processes)
    for proc, role in processes:
        yield proc, {
            "process.pid": proc.pid,
            "process.parent_pid": proc.info["ppid"],
            "romm.process.role": role,
            "romm.process.kind": kinds[proc.pid],
        }


def _process_memory(_: CallbackOptions) -> Iterable[Observation]:
    for proc, attributes in _romm_processes():
        try:
            # These come from /proc/<pid>/smaps_rollup, which only Linux has.
            memory = proc.memory_full_info()
            kinds = {
                "rss": memory.rss,
                "pss": memory.pss,
                "uss": memory.uss,
                "swap": memory.swap,
            }
        except psutil.Error, AttributeError:
            continue
        for kind, value in kinds.items():
            yield Observation(value, {**attributes, "process.memory.kind": kind})


def _process_cpu_time(_: CallbackOptions) -> Iterable[Observation]:
    for proc, attributes in _romm_processes():
        try:
            cpu = proc.cpu_times()
        except psutil.Error:
            continue
        yield Observation(cpu.user, {**attributes, "cpu.mode": "user"})
        yield Observation(cpu.system, {**attributes, "cpu.mode": "system"})


def _process_threads(_: CallbackOptions) -> Iterable[Observation]:
    for proc, attributes in _romm_processes():
        try:
            yield Observation(proc.num_threads(), attributes)
        except psutil.Error:
            continue


def _process_open_fds(_: CallbackOptions) -> Iterable[Observation]:
    for proc, attributes in _romm_processes():
        try:
            yield Observation(proc.num_fds(), attributes)
        except psutil.Error, AttributeError:
            continue


def _process_disk_io(_: CallbackOptions) -> Iterable[Observation]:
    for proc, attributes in _romm_processes():
        try:
            io = proc.io_counters()
        except psutil.Error, AttributeError:
            continue
        yield Observation(io.read_bytes, {**attributes, "disk.io.direction": "read"})
        yield Observation(io.write_bytes, {**attributes, "disk.io.direction": "write"})


def register_gauges(meter: Meter | None = None) -> None:
    """Register the gauges, to be called from one long-lived process per container."""
    meter = meter or metrics.get_meter(__name__)
    meter.create_observable_gauge(
        "romm.valkey.memory",
        [_read_quietly(_valkey_memory)],
        unit="By",
        description="Valkey memory in use, its peak, and its limit",
    )
    meter.create_observable_counter(
        "romm.valkey.evicted_keys",
        [_read_quietly(_valkey_evicted_keys)],
        description="Keys Valkey evicted to stay under its memory limit",
    )
    meter.create_observable_gauge(
        "romm.valkey.keys",
        [_read_quietly(_valkey_keys)],
        description="Keys per Valkey database",
    )
    meter.create_observable_gauge(
        "romm.rq.queue.depth",
        [_read_quietly(_queue_depth)],
        description="Jobs waiting in each RQ queue",
    )
    meter.create_observable_gauge(
        "romm.rq.workers",
        [_read_quietly(_workers)],
        description="Registered RQ workers",
    )
    meter.create_observable_gauge(
        "romm.process.memory",
        [_process_memory],
        unit="By",
        description="RSS, PSS, USS and swap of each RomM process",
    )
    meter.create_observable_counter(
        "romm.process.cpu.time",
        [_process_cpu_time],
        unit="s",
        description="CPU time each RomM process has used, in user and system mode",
    )
    meter.create_observable_gauge(
        "romm.process.threads",
        [_process_threads],
        description="Threads in each RomM process",
    )
    meter.create_observable_gauge(
        "romm.process.open_fds",
        [_process_open_fds],
        description="Open file descriptors in each RomM process",
    )
    meter.create_observable_counter(
        "romm.process.disk.io",
        [_process_disk_io],
        unit="By",
        description="Bytes each RomM process has read from and written to storage",
    )

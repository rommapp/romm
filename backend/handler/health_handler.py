import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from typing import Final

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError
from rq import Queue, worker_registration
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from config import LIBRARY_BASE_PATH, REDIS_URL, RESOURCES_BASE_PATH
from config.config_manager import ConfigManager
from endpoints.responses.health import (
    CheckError,
    DatabaseStatus,
    HealthReadyResponse,
    HealthStatusResponse,
    LibraryCheck,
    MigrationStatus,
    ReadyCheck,
    ResourcesCheck,
    ValkeyStatus,
    WorkerStatus,
)
from handler.redis_handler import (
    REDIS_CLIENT_OPTIONS,
    SCAN_QUEUE_NAME,
    STREAMING_QUEUE_NAME,
    QueuePrio,
)

# Sized for a tailnet. The checks run in parallel, so this also bounds the probe.
PROBE_TIMEOUT_SECONDS: Final = 5

# Each driver names its connect timeout differently.
_CONNECT_TIMEOUT_ARG: Final[dict[str, str]] = {
    "mariadb+mariadbconnector": "connect_timeout",
    "mysql+mysqlconnector": "connection_timeout",
    "postgresql+psycopg": "connect_timeout",
}

_QUEUE_NAMES: Final = (
    *(prio.value for prio in QueuePrio),
    SCAN_QUEUE_NAME,
    STREAMING_QUEUE_NAME,
)

_BACKEND_DIR: Final = Path(__file__).resolve().parents[1]
_SCRIPTS: Final = ScriptDirectory(str(_BACKEND_DIR / "alembic"))
_HEAD_REVISION: Final = _SCRIPTS.get_current_head()
# Revisions this code ships with; any other database revision is newer.
_KNOWN_REVISIONS: Final = frozenset(rev.revision for rev in _SCRIPTS.walk_revisions())

_db_url = ConfigManager.get_db_engine()
_timeout_arg = _CONNECT_TIMEOUT_ARG.get(_db_url.drivername)

# Own engine and client, so probes never queue behind request traffic.
_probe_engine = create_engine(
    _db_url,
    poolclass=NullPool,
    connect_args={_timeout_arg: PROBE_TIMEOUT_SECONDS} if _timeout_arg else {},
)
_probe_redis = Redis.from_url(
    REDIS_URL,
    socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
    socket_timeout=PROBE_TIMEOUT_SECONDS,
    **REDIS_CLIENT_OPTIONS,
)


def ready_checks() -> HealthReadyResponse:
    report = status_report()
    return {
        "database": _verdict(report["database"]),
        "valkey": _verdict(report["valkey"]),
        "worker": _verdict(report["worker"]),
        "migration": _verdict(report["migration"]),
        "library": report["library"],
        "resources": report["resources"],
    }


def status_report() -> HealthStatusResponse:
    with ThreadPoolExecutor(max_workers=4) as pool:
        database = pool.submit(_database_check)
        valkey = pool.submit(_valkey_check)
        worker = pool.submit(_worker_check)
        migration = pool.submit(_migration_check)
        return {
            "database": database.result(),
            "valkey": valkey.result(),
            "worker": worker.result(),
            "migration": migration.result(),
            "library": _library_check(),
            "resources": _resources_check(),
        }


def metrics_text() -> str:
    report = status_report()
    lines = [
        f'romm_health_check_ok{{check="{name}"}} {int(report[name]["ok"])}'
        for name in (
            "database",
            "valkey",
            "worker",
            "migration",
            "library",
            "resources",
        )
    ]
    lines += [
        f'romm_health_check_latency_seconds{{check="{name}"}} '
        f'{report[name]["latency_ms"] / 1000}'
        for name in ("database", "valkey", "worker", "migration")
    ]
    workers = report["worker"]
    lines.append(f"romm_workers {workers['workers']}")
    lines += [
        f'romm_queue_depth{{queue="{queue}"}} {depth}'
        for queue, depth in workers["queues"].items()
    ]
    return "\n".join(lines) + "\n"


def _verdict(
    check: DatabaseStatus | ValkeyStatus | WorkerStatus | MigrationStatus,
) -> ReadyCheck:
    return {"ok": check["ok"], "error": check["error"]}


def _since(started: float) -> int:
    return round((perf_counter() - started) * 1000)


def _error_kind(exc: Exception) -> CheckError:
    if isinstance(exc, (TimeoutError, RedisTimeoutError)):
        return "timeout"
    if isinstance(exc, (ConnectionError, RedisConnectionError, OperationalError)):
        return "unreachable"
    return "error"


def _database_check() -> DatabaseStatus:
    started = perf_counter()
    try:
        with _probe_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return {"ok": False, "latency_ms": _since(started), "error": _error_kind(exc)}
    return {"ok": True, "latency_ms": _since(started), "error": None}


def _valkey_check() -> ValkeyStatus:
    started = perf_counter()
    try:
        ok = bool(_probe_redis.ping())
    except RedisError as exc:
        return {"ok": False, "latency_ms": _since(started), "error": _error_kind(exc)}
    return {"ok": ok, "latency_ms": _since(started), "error": None}


def _count_workers() -> int:
    # Worker.all() would raise this connection's socket timeout, so read the keys instead.
    keys = worker_registration.get_keys(connection=_probe_redis)
    return _probe_redis.exists(*keys) if keys else 0


def _worker_check() -> WorkerStatus:
    started = perf_counter()
    try:
        workers = _count_workers()
        queues = {
            name: Queue(name, connection=_probe_redis).count for name in _QUEUE_NAMES
        }
    except RedisError as exc:
        return {
            "ok": False,
            "latency_ms": _since(started),
            "error": _error_kind(exc),
            "workers": 0,
            "queues": {},
        }
    if not workers:
        return {
            "ok": False,
            "latency_ms": _since(started),
            "error": "no_workers",
            "workers": 0,
            "queues": queues,
        }
    return {
        "ok": True,
        "latency_ms": _since(started),
        "error": None,
        "workers": workers,
        "queues": queues,
    }


def _migration_check() -> MigrationStatus:
    started = perf_counter()
    try:
        with _probe_engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "latency_ms": _since(started),
            "error": _error_kind(exc),
            "current": None,
            "head": _HEAD_REVISION,
        }
    error: CheckError | None
    if current == _HEAD_REVISION:
        error = None
    elif current is None or current in _KNOWN_REVISIONS:
        error = "behind"
    else:
        error = "ahead"
    return {
        "ok": error is None,
        "latency_ms": _since(started),
        "error": error,
        "current": current,
        "head": _HEAD_REVISION,
    }


def _library_check() -> LibraryCheck:
    readable = os.access(LIBRARY_BASE_PATH, os.R_OK)
    return {
        "ok": readable,
        "readable": readable,
        "error": None if readable else "unreadable",
    }


def _resources_check() -> ResourcesCheck:
    readable = os.access(RESOURCES_BASE_PATH, os.R_OK)
    writable = os.access(RESOURCES_BASE_PATH, os.W_OK)
    error: CheckError | None
    if not readable:
        error = "unreadable"
    elif not writable:
        error = "unwritable"
    else:
        error = None
    return {
        "ok": error is None,
        "readable": readable,
        "writable": writable,
        "error": error,
    }

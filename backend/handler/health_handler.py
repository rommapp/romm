import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Final

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError
from rq import worker_registration
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from config import LIBRARY_BASE_PATH, REDIS_URL, RESOURCES_BASE_PATH
from config.config_manager import ConfigManager
from endpoints.responses.health import (
    CheckError,
    HealthReadyResponse,
    LibraryCheck,
    ReadyCheck,
    ResourcesCheck,
)
from handler.redis_handler import REDIS_CLIENT_OPTIONS

# Sized for a tailnet. The checks run in parallel, so this also bounds the probe.
PROBE_TIMEOUT_SECONDS: Final = 5

# Each driver names its connect timeout differently.
_CONNECT_TIMEOUT_ARG: Final[dict[str, str]] = {
    "mariadb+mariadbconnector": "connect_timeout",
    "mysql+mysqlconnector": "connection_timeout",
    "postgresql+psycopg": "connect_timeout",
}

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


def _error_kind(exc: Exception) -> CheckError:
    if isinstance(exc, (TimeoutError, RedisTimeoutError)):
        return "timeout"
    if isinstance(exc, (ConnectionError, RedisConnectionError, OperationalError)):
        return "unreachable"
    return "error"


def _database_check() -> ReadyCheck:
    try:
        with _probe_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return {"ok": False, "error": _error_kind(exc)}
    return {"ok": True, "error": None}


def _valkey_check() -> ReadyCheck:
    try:
        _probe_redis.ping()
    except RedisError as exc:
        return {"ok": False, "error": _error_kind(exc)}
    return {"ok": True, "error": None}


def _count_workers() -> int:
    # Worker.all() would raise this connection's socket timeout, so read the keys instead.
    keys = worker_registration.get_keys(connection=_probe_redis)
    return _probe_redis.exists(*keys) if keys else 0


def _worker_check() -> ReadyCheck:
    try:
        workers = _count_workers()
    except RedisError as exc:
        return {"ok": False, "error": _error_kind(exc)}
    if not workers:
        return {"ok": False, "error": "no_workers"}
    return {"ok": True, "error": None}


def _migration_check() -> ReadyCheck:
    try:
        with _probe_engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
    except SQLAlchemyError as exc:
        return {"ok": False, "error": _error_kind(exc)}
    if current == _HEAD_REVISION:
        return {"ok": True, "error": None}
    behind = current is None or current in _KNOWN_REVISIONS
    return {"ok": False, "error": "behind" if behind else "ahead"}


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

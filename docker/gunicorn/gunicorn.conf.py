"""Gunicorn settings for the API: optional preloading, fork-friendly GC, and fork-safety checks."""

import gc
import os
import sys
import threading

_TRUTHY = ("1", "true", "yes", "on")

# Looked up, not imported, so a master that never loaded the app doesn't load it
# here; handler/rq_worker.py finds the engine the same way.
_DATABASE_MODULE = "handler.database.base_handler"

# A worker's inherited pools stay referenced: collecting them would close the
# connections the master and the other workers still use.
_inherited_pools: list[object] = []


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() in _TRUTHY


def _database_engine():
    return getattr(sys.modules.get(_DATABASE_MODULE), "sync_engine", None)


GC_FREEZE = _env_flag("_POC_WEB_SERVER_GC_FREEZE")

# The master imports the app before forking, so the workers share its memory.
preload_app = _env_flag("_POC_WEB_SERVER_PRELOAD")

if GC_FREEZE:
    # Gunicorn reads this file before --preload imports the app; on_starting runs
    # after that import, too late to keep the collector from leaving holes.
    gc.disable()


def pre_fork(server, worker):
    # A thread alive here is not copied into the worker, and a lock it holds stays
    # locked there.
    others = [t.name for t in threading.enumerate() if t is not threading.main_thread()]
    if others:
        server.log.warning("Threads alive before fork: %s", ", ".join(others))
    engine = _database_engine()
    if engine is not None:
        opened = engine.pool.checkedin() + engine.pool.checkedout()
        if opened:
            server.log.warning(
                "Database connections open before fork: %d; each worker starts its "
                "own pool, but something connected during import",
                opened,
            )
    if GC_FREEZE:
        gc.freeze()


def post_fork(server, worker):
    if GC_FREEZE:
        gc.enable()
    engine = _database_engine()
    if engine is not None:
        # Two processes on one connection mix up each other's replies.
        _inherited_pools.append(engine.pool)
        engine.dispose(close=False)

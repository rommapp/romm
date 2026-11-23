"""Gunicorn settings for the API: optional preloading with fork-friendly garbage collection."""

import gc
import os
import threading

_TRUTHY = ("1", "true", "yes", "on")


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() in _TRUTHY


PRELOAD = _env_flag("WEB_SERVER_PRELOAD")

# The master imports the app before forking, so the workers share its memory.
preload_app = PRELOAD

if PRELOAD:
    # Gunicorn reads this file before --preload imports the app; on_starting runs
    # after that import, too late to keep the collector from leaving holes.
    gc.disable()


def pre_fork(server, worker):
    # A thread alive here is not copied into the worker, and a lock it holds stays
    # locked there.
    others = [t.name for t in threading.enumerate() if t is not threading.main_thread()]
    if others:
        server.log.warning("Threads alive before fork: %s", ", ".join(others))
    if PRELOAD:
        gc.freeze()


def post_fork(server, worker):
    if PRELOAD:
        gc.enable()

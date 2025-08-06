import sentry_sdk
from config import (
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SENTRY_DSN,
)
from handler.redis_handler import redis_client
from logger.logger import log, unify_logger
from rq import Queue, Worker
from tasks.scheduled.scan_library import scan_library_task
from tasks.scheduled.update_launchbox_metadata import update_launchbox_metadata_task
from tasks.scheduled.update_switch_titledb import update_switch_titledb_task
from utils import get_version

unify_logger("rq.worker")

listen = ("high", "default", "low")

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release=f"romm@{get_version()}",
)

if __name__ == "__main__":
    # Initialize scheduled tasks
    if ENABLE_SCHEDULED_RESCAN:
        log.info("Starting scheduled rescan")
        scan_library_task.init()

    if ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB:
        log.info("Starting scheduled update switch titledb")
        update_switch_titledb_task.init()

    if ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA:
        log.info("Starting scheduled update launchbox metadata")
        update_launchbox_metadata_task.init()

    worker = Worker([Queue(name, connection=redis_client) for name in listen])
    worker.work()

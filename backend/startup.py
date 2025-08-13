"""Startup script to run tasks before the main application is started."""

import asyncio

import sentry_sdk
from config import (
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SENTRY_DSN,
)
from logger.logger import log
from opentelemetry import trace
from tasks.scheduled.scan_library import scan_library_task
from tasks.scheduled.update_launchbox_metadata import update_launchbox_metadata_task
from tasks.scheduled.update_switch_titledb import update_switch_titledb_task
from utils import get_version
from utils.context import initialize_context

tracer = trace.get_tracer(__name__)


@tracer.start_as_current_span("main")
async def main() -> None:
    """Run startup tasks."""

    async with initialize_context():
        log.info("Running startup tasks")

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

        log.info("Startup tasks completed")


if __name__ == "__main__":
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release=f"romm@{get_version()}",
    )

    asyncio.run(main())

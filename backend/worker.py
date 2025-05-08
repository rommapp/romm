import logging

import sentry_sdk
from config import SENTRY_DSN
from handler.redis_handler import redis_client
from logger.formatter import common_date_format, common_log_format
from rq import Queue, Worker
from utils import get_version

listen = ("high", "default", "low")

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release=f"romm@{get_version()}",
)

# Set up custom logging for Worker logging
logging.basicConfig(format=common_log_format, datefmt=common_date_format)

if __name__ == "__main__":
    # Start the worker
    worker = Worker([Queue(name, connection=redis_client) for name in listen])
    worker.work()

import logging

import sentry_sdk
from config import SENTRY_DSN
from handler.redis_handler import redis_client
from logger.logger import log
from rq import Queue, Worker
from utils import get_version

# logger formatting
rq_logger = logging.getLogger("rq.worker")
rq_logger.setLevel(log.level)

if not rq_logger.hasHandlers():
    for handler in log.handlers:
        rq_logger.addHandler(handler)
else:
    for handler in rq_logger.handlers:
        handler.setFormatter(log.handlers[0].formatter)

listen = ("high", "default", "low")

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release=f"romm@{get_version()}",
)

if __name__ == "__main__":
    worker = Worker([Queue(name, connection=redis_client) for name in listen])
    worker.work()

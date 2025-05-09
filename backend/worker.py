import logging

import sentry_sdk
from config import SENTRY_DSN
from handler.redis_handler import redis_client
from logger.logger import log
from rq import Queue, Worker
from utils import get_version

# Get the rq.worker logger
rq_logger = logging.getLogger("rq.worker")

# Set its level (optional; you can match your app's LOGLEVEL if you want)
rq_logger.setLevel(log.level)

# Apply the same formatter to rq.worker handlers
if not rq_logger.hasHandlers():
    # You can reuse the same handler as your app logger OR create a new one
    for handler in log.handlers:
        rq_logger.addHandler(handler)
else:
    # If rq.worker already has handlers, just update their formatter
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

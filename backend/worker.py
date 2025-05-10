import sentry_sdk
from config import SENTRY_DSN
from handler.redis_handler import redis_client
from logger.logger import unify_logger
from rq import Queue, Worker
from utils import get_version

unify_logger("rq.worker")

listen = ("high", "default", "low")

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release=f"romm@{get_version()}",
)

if __name__ == "__main__":
    worker = Worker([Queue(name, connection=redis_client) for name in listen])
    worker.work()

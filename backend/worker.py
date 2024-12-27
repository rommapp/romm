import sentry_sdk
from config import SENTRY_DSN
from handler.redis_handler import redis_client
from rq import Connection, Queue, Worker
from utils import get_version

listen = ["high", "default", "low"]

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release="romm@" + get_version(),
)


if __name__ == "__main__":
    # Start the worker
    with Connection(redis_client):
        worker = Worker(map(Queue, listen))
        worker.work()

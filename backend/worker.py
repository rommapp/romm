import sys

from config import ENABLE_EXPERIMENTAL_REDIS
from rq import Connection, Queue, Worker
from handler.redis_handler import redis_client

listen = ["high", "default", "low"]

if __name__ == "__main__":
    # Exit if Redis is not enabled
    if not ENABLE_EXPERIMENTAL_REDIS:
        sys.exit(0)

    # Start the worker
    with Connection(redis_client):
        worker = Worker(map(Queue, listen))
        worker.work()

import sys
from rq import Worker, Queue, Connection

from config import ENABLE_EXPERIMENTAL_REDIS
from utils.cache import redis_client

listen = ["high", "default", "low"]

if __name__ == "__main__":
    # Exit if Redis is not enabled
    if not ENABLE_EXPERIMENTAL_REDIS:
        sys.exit(0)

    with Connection(redis_client):
        worker = Worker(map(Queue, listen))
        worker.work()

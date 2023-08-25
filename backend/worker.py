import sys
from rq import Worker, Queue, Connection

from utils.cache import redis_client, use_redis_connection

listen = ["high", "default", "low"]

if __name__ == "__main__":
    # Exit if Redis is not connectable
    if not use_redis_connection:
        sys.exit(0)

    with Connection(redis_client):
        worker = Worker(map(Queue, listen))
        worker.work()

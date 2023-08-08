import sys
from rq import Worker, Queue, Connection

from utils.cache import redis_client, redis_connectable

listen = ["high", "default", "low"]

if __name__ == "__main__":
    if not redis_connectable:
        sys.exit(2)

    with Connection(redis_client):
        worker = Worker(map(Queue, listen))
        worker.work()

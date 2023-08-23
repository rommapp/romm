import sys
from rq import Worker, Queue, Connection

from utils.redis import redis_client, redis_connectable

listen = ["high", "default", "low"]

if __name__ == "__main__":
    # Exit if Redis is not connectable
    if not redis_connectable:
        sys.exit(0)

    with Connection(redis_client):
        worker = Worker(map(Queue, listen))
        worker.work()

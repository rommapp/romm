import redis
from rq import Worker, Queue, Connection

from config import REDIS_HOST, REDIS_PORT

listen = ["high", "default", "low"]
redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}"
redis_conn = redis.from_url(redis_url)

if __name__ == "__main__":
    with Connection(redis_conn):
        worker = Worker(map(Queue, listen))
        worker.work()

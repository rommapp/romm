from rq import Connection, Queue, Worker
from handler.redis_handler import redis_client

listen = ["high", "default", "low"]

if __name__ == "__main__":
    # Start the worker
    with Connection(redis_client):
        worker = Worker(map(Queue, listen))
        worker.work()

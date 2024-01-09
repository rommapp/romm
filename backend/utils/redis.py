from config import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT
from redis import Redis
from rq import Queue

redis_client = Redis(
    host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD, db=0
)
redis_url = (
    f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"
    if REDIS_PASSWORD
    else f"redis://{REDIS_HOST}:{REDIS_PORT}"
)


high_prio_queue = Queue(name="high", connection=redis_client)
default_queue = Queue(name="default", connection=redis_client)
low_prio_queue = Queue(name="low", connection=redis_client)

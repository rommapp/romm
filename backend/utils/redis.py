from redis import Redis
from rq import Queue

from config import REDIS_HOST, REDIS_PORT


redis_client = Redis(host=REDIS_HOST, port=int(REDIS_PORT), db=0)
redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

high_prio_queue = Queue(name="high", connection=redis_client)
default_queue = Queue(name="default", connection=redis_client)
low_prio_queue = Queue(name="low", connection=redis_client)

import logging

import sentry_sdk
from config import SENTRY_DSN
from handler.redis_handler import redis_client
from logger.formatter import BLUE, CYAN, GREEN, LIGHTMAGENTA, RESET, RESET_ALL
from rq import Queue, Worker
from utils import get_version

listen = ("high", "default", "low")

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release=f"romm@{get_version()}",
)

# Set up custom logging
log_format = f"{GREEN}INFO{RESET}:\t  {BLUE}[RomM]{LIGHTMAGENTA}[%(module)s]{CYAN}[%(asctime)s] {RESET_ALL}%(message)s"
logging.basicConfig(format=log_format, datefmt="%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    # Start the worker
    worker = Worker([Queue(name, connection=redis_client) for name in listen])
    worker.work()

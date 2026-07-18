import logging
import sys

from config import IS_PYTEST_RUN, LOGLEVEL
from logger.formatter import Formatter
from logger.log_stream_handler import LogStreamHandler

# Set up logger
log = logging.getLogger("romm")
log.setLevel(LOGLEVEL)
log.propagate = False

# Define stdout handler
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(Formatter())
log.addHandler(stdout_handler)

# Mirror records to Redis for the real-time admin log viewer. Skipped under
# pytest, where there is no live Redis to stream to.
if not IS_PYTEST_RUN:
    stream_handler = LogStreamHandler()
    stream_handler.setLevel(LOGLEVEL)
    log.addHandler(stream_handler)

# Hush passlib warnings
logging.getLogger("passlib").setLevel(logging.ERROR)


def unify_logger(logger: str) -> None:
    """
    Unify the logger to use the same format and level as the main logger.

    Args:
        logger (str): The name of the logger to unify.
    """
    alembic_logger = logging.getLogger(logger)
    alembic_logger.setLevel(log.level)

    if not alembic_logger.hasHandlers():
        for handler in log.handlers:
            alembic_logger.addHandler(handler)
    else:
        for handler in alembic_logger.handlers:
            handler.setFormatter(log.handlers[0].formatter)

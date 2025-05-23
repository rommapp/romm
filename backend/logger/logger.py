import logging
import sys

from config import LOGLEVEL
from logger.formatter import Formatter

# Set up logger
log = logging.getLogger("romm")
log.setLevel(LOGLEVEL)

# Define stdout handler
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(Formatter())
log.addHandler(stdout_handler)

# Hush passlib warnings
logging.getLogger("passlib").setLevel(logging.ERROR)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "romm": {
            "()": "logger.formatter.Formatter",
        }
    },
    "handlers": {
        "default": {
            "formatter": "romm",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {
        "handlers": ["default"],
        "level": "DEBUG",
    },
    "loggers": {
        "uvicorn": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False,
        },
        "uvicorn.error": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False,
        },
    },
}


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

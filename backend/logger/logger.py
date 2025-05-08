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

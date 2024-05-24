import logging
import sys

from logger.stdout_formatter import StdoutFormatter

# Set up logger
log = logging.getLogger("romm")
log.setLevel(logging.DEBUG)

# Set up sqlachemy logger
sql_log = logging.getLogger("sqlalchemy.engine")
sql_log.setLevel(logging.DEBUG)

# Define stdout handler
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(StdoutFormatter())
log.addHandler(stdout_handler)
sql_log.addHandler(stdout_handler)

# Hush passlib warnings
logging.getLogger("passlib").setLevel(logging.ERROR)

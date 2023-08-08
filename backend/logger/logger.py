import logging
import sys
from datetime import datetime
from pathlib import Path

from config import LOGS_BASE_PATH
from logger.stdout_formatter import StdoutFormatter
from logger.file_formatter import FileFormatter

# Create logs folder if not exists
Path(LOGS_BASE_PATH).mkdir(parents=True, exist_ok=True)
now = datetime.now()
logs_file = f"{LOGS_BASE_PATH}/{now.strftime('%Y%m%d_%H%M%S')}.log"

# Get logger
log = logging.getLogger("romm")
log.setLevel(logging.DEBUG)

# Define stdout handler
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(StdoutFormatter())
log.addHandler(stdout_handler)

# Define file handler
file_handler = logging.FileHandler(logs_file)
file_handler.setFormatter(FileFormatter())
log.addHandler(file_handler)

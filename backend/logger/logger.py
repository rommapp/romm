import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Final

from config import ROMM_BASE_PATH
from .stdout_formatter import StdoutFormatter
from .file_formatter import FileFormatter

LOGS_BASE_PATH: Final = f"{ROMM_BASE_PATH}/logs"

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

# Hush passlib warnings
logging.getLogger('passlib').setLevel(logging.ERROR)

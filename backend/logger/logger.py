import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from logger.stdout_formatter import StdoutFormatter
from logger.file_formatter import FileFormatter

# Create logs folder if not exists
logs_path = f"{os.getenv('ROMM_BASE_PATH')}/logs"
Path(logs_path).mkdir(parents=True, exist_ok=True)
now = datetime.now()
logs_file = f"{logs_path}/{now.strftime('%Y%m%d_%H%M%S')}.log"

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

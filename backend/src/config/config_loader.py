import os
import sys
from urllib.parse import quote_plus

from config import ROMM_DB_DRIVER, SUPPORTED_DB_DRIVERS, SQLITE_DB_BASE_PATH
from logger.logger import log


def get_db_engine():
    if ROMM_DB_DRIVER in SUPPORTED_DB_DRIVERS:

        if ROMM_DB_DRIVER == 'mariadb':
            DB_HOST: str = os.getenv('DB_HOST')
            try:
                DB_PORT: int = int(os.getenv('DB_PORT'))
            except TypeError:
                log.critical(f"DB_PORT variable not set properly")
                sys.exit(3)
            DB_USER: str = os.getenv('DB_USER')
            DB_PASSWD: str = os.getenv('DB_PASSWD')
            DB_NAME: str = os.getenv('DB_NAME', 'romm')
        
            return f"mariadb+mariadbconnector://{DB_USER}:%s@{DB_HOST}:{DB_PORT}/{DB_NAME}" % quote_plus(DB_PASSWD)

        elif ROMM_DB_DRIVER == 'sqlite':
            if not os.path.exists(SQLITE_DB_BASE_PATH): os.makedirs(SQLITE_DB_BASE_PATH)
            return f"sqlite:////{SQLITE_DB_BASE_PATH}/romm.db"

    else:
        log.critical(f"{ROMM_DB_DRIVER} database not supported")
        sys.exit(3)

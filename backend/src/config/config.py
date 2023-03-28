import os
import sys
import pathlib

from logger.logger import log

# Uvicorn
DEV_PORT: int = 5000
DEV_HOST: str = "0.0.0.0"

# PATHS
LIBRARY_BASE_PATH: str = f"{pathlib.Path(__file__).parent.parent.parent.parent.resolve()}/library"

DEFAULT_URL_LOGO: str = "https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png"
DEFAULT_PATH_LOGO: str = f"/assets/library/resources/default/logo_l.png"

DEFAULT_URL_COVER_L: str = "https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png"
DEFAULT_PATH_COVER_L: str = f"/assets/library/resources/default/cover_l.png"
DEFAULT_URL_COVER_S: str = "https://images.igdb.com/igdb/image/upload/t_cover_small/nocover.png"
DEFAULT_PATH_COVER_S: str = f"/assets/library/resources/default/cover_s.png"

# IGDB
CLIENT_ID: str = os.getenv('CLIENT_ID')
CLIENT_SECRET: str = os.getenv('CLIENT_SECRET')
# STEAMGRIDDB
STEAMGRIDDB_API_KEY: str = os.getenv('STEAMGRIDDB_API_KEY')


RESERVED_FOLDERS: list = ['resources', 'database']


# DB DRIVERS
SUPPORTED_DB_DRIVERS: list = ['sqlite', 'mariadb']
ROMM_DB_DRIVER: str = os.getenv('ROMM_DB_DRIVER', 'sqlite')


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
        
            return f"mariadb+mariadbconnector://{DB_USER}:{DB_PASSWD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

        elif ROMM_DB_DRIVER == 'sqlite':
            SQLITE_PATH: str = f"{LIBRARY_BASE_PATH}/database"
            if not os.path.exists(SQLITE_PATH): os.makedirs(SQLITE_PATH)
            return f"sqlite:////{SQLITE_PATH}/romm.db"

    else:
        log.critical(f"Not supported {ROMM_DB_DRIVER} database")
        sys.exit(3)

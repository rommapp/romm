import os
import pathlib

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

# DB
DB_HOST: str = os.getenv('DB_HOST')
DB_PORT: int = int(os.getenv('DB_PORT'))
DB_ROOT_PASSWD: str = os.getenv('DB_ROOT_PASSWD')
DB_USER: str = os.getenv('DB_USER')
DB_PASSWD: str = os.getenv('DB_PASSWD')
DB_NAME: str = 'romm'

# DB DRIVERS
SQLITE_PATH: str = f"{LIBRARY_BASE_PATH}/database"
if not os.path.exists(SQLITE_PATH): os.makedirs(SQLITE_PATH)
ROMM_DB_DRIVER: str = os.getenv('ROMM_DB_DRIVER', 'sqlite')
DB_DRIVERS: dict = {
    'mariadb': f"mariadb+mariadbconnector://{DB_USER}:{DB_PASSWD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    'sqlite': f"sqlite:////{SQLITE_PATH}/romm.db"
}

RESERVED_FOLDERS: list = ['resources', 'database']

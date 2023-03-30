import os
import pathlib
import yaml
from yaml.loader import SafeLoader


# Uvicorn
DEV_PORT: int = 5000
DEV_HOST: str = "0.0.0.0"

# PATHS
LIBRARY_BASE_PATH: str = f"{pathlib.Path(__file__).parent.parent.parent.parent.resolve()}/library"
ROMM_USER_CONFIG_PATH: str = f"{pathlib.Path(__file__).parent.parent.parent.parent.resolve()}/romm/config.yml"

# ROMM RESERVED FOLDERS
RESERVED_FOLDERS: list = ['resources', 'database']

# DEFAULT RESOURCES
DEFAULT_URL_COVER_L: str = "https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png"
DEFAULT_PATH_COVER_L: str = f"/assets/library/resources/default/cover_l.png"
DEFAULT_URL_COVER_S: str = "https://images.igdb.com/igdb/image/upload/t_cover_small/nocover.png"
DEFAULT_PATH_COVER_S: str = f"/assets/library/resources/default/cover_s.png"

# IGDB
CLIENT_ID: str = os.getenv('CLIENT_ID')
CLIENT_SECRET: str = os.getenv('CLIENT_SECRET')
# STEAMGRIDDB
STEAMGRIDDB_API_KEY: str = os.getenv('STEAMGRIDDB_API_KEY')

# USER CONFIG
try:
    with open(ROMM_USER_CONFIG_PATH) as config: config = yaml.load(config, Loader=SafeLoader)
except FileNotFoundError:
    config = None
user_config: dict = {} if not config else config

# DB DRIVERS
SUPPORTED_DB_DRIVERS: list = ['sqlite', 'mariadb']
ROMM_DB_DRIVER: str = os.getenv('ROMM_DB_DRIVER', 'sqlite')

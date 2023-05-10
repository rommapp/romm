from handler.db_handler import DBHandler
from handler.igdb_handler import IGDBHandler
from handler.sgdb_handler import SGDBHandler
from config.config_loader import ConfigLoader

igdbh: IGDBHandler = IGDBHandler()
sgdbh: SGDBHandler = SGDBHandler()
dbh: DBHandler = DBHandler(ConfigLoader())

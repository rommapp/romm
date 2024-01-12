from handler.auth_handler.auth_handler import AuthHandler, OAuthHandler
from handler.db_handler import DBHandler
from handler.fs_handler.platforms_handler import PlatformsHandler
from handler.fs_handler.roms_handler import RomsHandler
from handler.fs_handler.assets_handler import AssetsHandler
from handler.fs_handler.resources_handler import ResourceHandler
from handler.gh_handler import GHHandler
from handler.igdb_handler import IGDBHandler
from handler.sgdb_handler import SGDBHandler
from handler.socket_handler import SocketHandler

igdbh = IGDBHandler()
sgdbh = SGDBHandler()
dbh = DBHandler()
ghh = GHHandler()
authh = AuthHandler()
oauthh = OAuthHandler()
socketh = SocketHandler()
platformh = PlatformsHandler()
romh = RomsHandler()
asseth = AssetsHandler()
resourceh = ResourceHandler()

from typing import Final

ALGORITHM: Final = "HS256"
DEFAULT_OAUTH_TOKEN_EXPIRY: Final = 15

DEFAULT_SCOPES_MAP: Final = {
    "me.read": "View your profile",
    "me.write": "Modify your profile",
    "roms.read": "View ROMs",
    "platforms.read": "View platforms",
    "assets.read": "View assets",
}

WRITE_SCOPES_MAP: Final = {
    "roms.write": "Modify ROMs",
    "platforms.write": "Modify platforms",
    "assets.write": "Modify assets",
}

FULL_SCOPES_MAP: Final = {
    "users.read": "View users",
    "users.write": "Modify users",
    "tasks.run": "Run tasks",
}

DEFAULT_SCOPES: Final = list(DEFAULT_SCOPES_MAP.keys())
WRITE_SCOPES: Final = DEFAULT_SCOPES + list(WRITE_SCOPES_MAP.keys())
FULL_SCOPES: Final = WRITE_SCOPES + list(FULL_SCOPES_MAP.keys())

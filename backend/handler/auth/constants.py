import enum
from datetime import timedelta
from typing import Final

ALGORITHM: Final = "HS256"
DEFAULT_OAUTH_TOKEN_EXPIRY: Final = timedelta(minutes=15)


class Scope(enum.StrEnum):
    ME_READ = "me.read"
    ME_WRITE = "me.write"
    ROMS_READ = "roms.read"
    ROMS_WRITE = "roms.write"
    ROMS_USER_READ = "roms.user.read"
    ROMS_USER_WRITE = "roms.user.write"
    PLATFORMS_READ = "platforms.read"
    PLATFORMS_WRITE = "platforms.write"
    ASSETS_READ = "assets.read"
    ASSETS_WRITE = "assets.write"
    FIRMWARE_READ = "firmware.read"
    FIRMWARE_WRITE = "firmware.write"
    COLLECTIONS_READ = "collections.read"
    COLLECTIONS_WRITE = "collections.write"
    USERS_READ = "users.read"
    USERS_WRITE = "users.write"
    TASKS_RUN = "tasks.run"


READ_SCOPES_MAP: Final = {
    Scope.ME_READ: "View your profile",
    Scope.ROMS_READ: "View ROMs",
    Scope.PLATFORMS_READ: "View platforms",
    Scope.ASSETS_READ: "View assets",
    Scope.FIRMWARE_READ: "View firmware",
    Scope.ROMS_USER_READ: "View user-rom properties",
    Scope.COLLECTIONS_READ: "View collections",
}

WRITE_SCOPES_MAP: Final = {
    Scope.ME_WRITE: "Modify your profile",
    Scope.ASSETS_WRITE: "Modify assets",
    Scope.ROMS_USER_WRITE: "Modify user-rom properties",
    Scope.COLLECTIONS_WRITE: "Modify collections",
}

EDIT_SCOPES_MAP: Final = {
    Scope.ROMS_WRITE: "Modify ROMs",
    Scope.PLATFORMS_WRITE: "Modify platforms",
    Scope.FIRMWARE_WRITE: "Modify firmware",
}

FULL_SCOPES_MAP: Final = {
    Scope.USERS_READ: "View users",
    Scope.USERS_WRITE: "Modify users",
    Scope.TASKS_RUN: "Run tasks",
}

READ_SCOPES: Final = list(READ_SCOPES_MAP.keys())
WRITE_SCOPES: Final = READ_SCOPES + list(WRITE_SCOPES_MAP.keys())
EDIT_SCOPES: Final = WRITE_SCOPES + list(EDIT_SCOPES_MAP.keys())
FULL_SCOPES: Final = EDIT_SCOPES + list(FULL_SCOPES_MAP.keys())


class TokenPurpose(enum.StrEnum):
    INVITE = "invite"
    RESET = "reset"

"""The `owned_on_steam` filter over each user's Steam library."""

import pytest
from tests.factories import make_platform, make_rom

from handler.database import (
    db_rom_handler,
    db_steam_library_handler,
    db_user_handler,
)
from models.platform import Platform
from models.rom import Rom
from models.steam_library import SteamLibraryEntry
from models.user import User

STEAM_ID = "76561197960287930"


@pytest.fixture
def win() -> Platform:
    return make_platform("win")


def _own(user: User, rom: Rom) -> None:
    assert rom.steam_id is not None
    db_user_handler.update_user(user.id, {"steam_id": STEAM_ID})
    db_steam_library_handler.replace_entries(
        user.id, STEAM_ID, [SteamLibraryEntry(rom_id=rom.id, steam_app_id=rom.steam_id)]
    )


def _rom_ids(user: User, owned_on_steam: bool) -> set[int]:
    return {
        rom.id
        for rom in db_rom_handler.get_roms_scalar(
            user_id=user.id, owned_on_steam=owned_on_steam
        )
    }


def test_matches_the_users_owned_games(win: Platform, admin_user: User):
    owned = make_rom(win, "Half-Life 2", steam_id=220)
    not_owned = make_rom(win, "Portal", steam_id=400)
    _own(admin_user, owned)

    assert _rom_ids(admin_user, True) == {owned.id}
    assert not_owned.id in _rom_ids(admin_user, False)
    assert owned.id not in _rom_ids(admin_user, False)


def test_matches_every_copy_of_an_owned_app(win: Platform, admin_user: User):
    linked = make_rom(win, "Portal 2", steam_id=620)
    other_copy = make_rom(make_platform("linux"), "Portal 2", steam_id=620)
    _own(admin_user, linked)

    assert _rom_ids(admin_user, True) == {linked.id, other_copy.id}


def test_another_users_library_does_not_count(
    win: Platform, admin_user: User, editor_user: User
):
    rom = make_rom(win, "Half-Life 2", steam_id=220)
    _own(editor_user, rom)

    assert _rom_ids(admin_user, True) == set()

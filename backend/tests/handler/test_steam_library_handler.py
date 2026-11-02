from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import event
from tests.factories import STEAM_ID, make_platform, make_rom

from adapters.services.steam import SteamWebAPIError
from adapters.services.steam_types import SteamOwnedGame
from handler.database import (
    db_collection_handler,
    db_platform_handler,
    db_rom_handler,
    db_steam_library_handler,
    db_user_handler,
)
from handler.database.base_handler import sync_engine
from handler.metadata import meta_igdb_handler
from handler.steam_library_handler import (
    STEAM_FS_SUBDIR,
    SteamLibraryError,
    parse_steam_profile,
    resolve_steam_profile,
    steam_library_platform,
    steam_web_api,
    sync_steam_library,
    unlink_steam_profile,
)
from models.collection import SmartCollection
from models.platform import Platform
from models.rom import RomStorefront
from models.user import User


@pytest.mark.parametrize(
    "profile, expected",
    [
        (STEAM_ID, (STEAM_ID, None)),
        (f"  {STEAM_ID}  ", (STEAM_ID, None)),
        (f"https://steamcommunity.com/profiles/{STEAM_ID}/", (STEAM_ID, None)),
        (f"steamcommunity.com/profiles/{STEAM_ID}", (STEAM_ID, None)),
        ("https://steamcommunity.com/id/gabelogannewell/", (None, "gabelogannewell")),
        ("https://STEAMCOMMUNITY.com/id/gabe?l=english", (None, "gabe")),
        ("gabelogannewell", (None, "gabelogannewell")),
    ],
)
def test_parses_ids_links_and_custom_names(
    profile: str, expected: tuple[str | None, str | None]
):
    assert parse_steam_profile(profile) == expected


@pytest.mark.parametrize(
    "profile",
    [
        "",
        "not a profile!",
        "https://example.com/id/gabe",
        "https://steamcommunity.com/profiles/gabe",
    ],
)
def test_rejects_anything_else(profile: str):
    with pytest.raises(SteamLibraryError):
        parse_steam_profile(profile)


@pytest.fixture
def steam_api():
    api = MagicMock()
    api.resolve_vanity_url = AsyncMock(return_value=STEAM_ID)
    api.get_player_summary = AsyncMock(
        return_value={"steamid": STEAM_ID, "personaname": "Gabe"}
    )
    api.get_owned_games = AsyncMock(return_value=[])
    with patch("handler.steam_library_handler.steam_web_api", return_value=api):
        yield api


async def test_resolves_a_custom_name_to_its_account(steam_api: MagicMock):
    summary = await resolve_steam_profile("gabe")

    assert summary["steamid"] == STEAM_ID
    steam_api.resolve_vanity_url.assert_awaited_once_with("gabe")
    steam_api.get_player_summary.assert_awaited_once_with(STEAM_ID)


async def test_an_unused_custom_name_is_an_error(steam_api: MagicMock):
    steam_api.resolve_vanity_url.return_value = None

    with pytest.raises(SteamLibraryError, match="custom URL 'gabe'"):
        await resolve_steam_profile("gabe")


async def test_an_unknown_id_is_an_error(steam_api: MagicMock):
    steam_api.get_player_summary.return_value = None

    with pytest.raises(SteamLibraryError, match=STEAM_ID):
        await resolve_steam_profile(STEAM_ID)


async def test_a_steam_failure_is_reported_as_a_library_error(steam_api: MagicMock):
    steam_api.get_player_summary.side_effect = SteamWebAPIError("Steam rejected it")

    with pytest.raises(SteamLibraryError, match="Steam rejected it"):
        await resolve_steam_profile(STEAM_ID)


@patch("handler.steam_library_handler.STEAM_API_KEY", None)
def test_needs_an_api_key():
    with pytest.raises(SteamLibraryError, match="STEAM_API_KEY"):
        steam_web_api()


@pytest.fixture
def steam_user(admin_user: User) -> User:
    db_user_handler.update_user(admin_user.id, {"steam_id": STEAM_ID})
    user = db_user_handler.get_user(admin_user.id)
    assert user is not None
    return user


@pytest.fixture
def win() -> Platform:
    return make_platform("win")


def _game(
    app_id: int, name: str, playtime: int = 0, last_played: int = 0
) -> SteamOwnedGame:
    return {
        "appid": app_id,
        "name": name,
        "playtime_forever": playtime,
        "rtime_last_played": last_played,
    }


async def test_creates_store_only_roms_for_games_not_in_the_library(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000)
    ]

    result = await sync_steam_library(steam_user)

    assert (result.owned, result.linked, result.created, result.removed) == (1, 0, 1, 0)
    [entry] = db_steam_library_handler.get_entries(steam_user.id)
    rom = db_rom_handler.get_rom(entry.rom_id)
    assert rom is not None
    assert rom.platform_id == win.id
    assert rom.name == "Half-Life 2"
    assert rom.steam_id == 220
    assert rom.storefront == RomStorefront.STEAM
    assert rom.fs_name == "Half-Life 2 (steam-220)"
    assert rom.fs_path.endswith(f"/{STEAM_FS_SUBDIR}")
    assert not rom.has_file_on_disk
    assert entry.playtime_minutes == 90
    assert entry.last_played_at is not None
    assert entry.last_played_at.replace(tzinfo=None) == datetime.fromtimestamp(
        1_700_000_000, timezone.utc
    ).replace(tzinfo=None)
    assert result.unmatched_rom_ids == [rom.id]


async def test_links_a_rom_already_in_the_library(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    owned_copy = make_rom(win, "Portal", steam_id=400)
    steam_api.get_owned_games.return_value = [_game(400, "Portal")]

    result = await sync_steam_library(steam_user)

    assert (result.linked, result.created) == (1, 0)
    [entry] = db_steam_library_handler.get_entries(steam_user.id)
    assert entry.rom_id == owned_copy.id
    assert entry.last_played_at is None
    assert result.unmatched_rom_ids == []


async def test_prefers_a_rom_with_a_file_over_a_store_only_one(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    make_rom(
        win,
        "Portal 2",
        fs_stem="Portal 2 (steam-620)",
        steam_id=620,
        storefront="steam",
    )
    with_file = make_rom(make_platform("linux"), "Portal 2", steam_id=620)
    steam_api.get_owned_games.return_value = [_game(620, "Portal 2")]

    await sync_steam_library(steam_user)

    [entry] = db_steam_library_handler.get_entries(steam_user.id)
    assert entry.rom_id == with_file.id


async def test_a_second_sync_reuses_the_store_only_rom(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [_game(220, "Half-Life 2")]
    await sync_steam_library(steam_user)

    result = await sync_steam_library(steam_user)

    assert (result.linked, result.created) == (1, 0)
    assert len(db_steam_library_handler.get_entries(steam_user.id)) == 1


async def test_a_store_only_rom_that_lost_its_steam_id_is_relinked(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [_game(220, "Half-Life 2")]
    await sync_steam_library(steam_user)
    [entry] = db_steam_library_handler.get_entries(steam_user.id)
    db_rom_handler.update_rom(entry.rom_id, {"steam_id": None})

    result = await sync_steam_library(steam_user)

    assert result.created == 0
    [relinked] = db_steam_library_handler.get_entries(steam_user.id)
    assert relinked.rom_id == entry.rom_id
    rom = db_rom_handler.get_rom(entry.rom_id)
    assert rom is not None and rom.steam_id == 220


async def test_forgets_games_no_longer_owned(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2"),
        _game(400, "Portal"),
    ]
    await sync_steam_library(steam_user)
    steam_api.get_owned_games.return_value = [_game(400, "Portal", playtime=30)]

    result = await sync_steam_library(steam_user)

    assert result.removed == 1
    [entry] = db_steam_library_handler.get_entries(steam_user.id)
    assert (entry.steam_app_id, entry.playtime_minutes) == (400, 30)


async def test_an_unchanged_library_writes_no_entry(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000)
    ]
    await sync_steam_library(steam_user)
    statements: list[str] = []

    def record(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        statements.append(statement)

    event.listen(sync_engine, "before_cursor_execute", record)
    try:
        await sync_steam_library(steam_user)
    finally:
        event.remove(sync_engine, "before_cursor_execute", record)

    assert not [s for s in statements if s.startswith("UPDATE steam_library_entries")]


async def test_a_matched_store_only_rom_is_not_scanned_again(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [_game(220, "Half-Life 2")]
    [rom_id] = (await sync_steam_library(steam_user)).unmatched_rom_ids
    db_rom_handler.update_rom(rom_id, {"url_cover": "https://example.com/cover.jpg"})

    result = await sync_steam_library(steam_user)

    assert result.unmatched_rom_ids == []


async def test_a_sync_moves_an_owned_on_steam_smart_collection(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    rom = make_rom(win, "Portal", steam_id=400)
    smart_collection = db_collection_handler.add_smart_collection(
        SmartCollection(
            name="Owned on Steam",
            description="",
            user_id=steam_user.id,
            filter_criteria={"owned_on_steam": True},
        )
    )
    steam_api.get_owned_games.return_value = [_game(400, "Portal")]

    await sync_steam_library(steam_user)

    after = db_collection_handler.get_smart_collection(smart_collection.id)
    assert after is not None and after.rom_ids == [rom.id]


async def test_a_sync_checks_only_the_owners_owned_on_steam_collections(
    steam_api: MagicMock, steam_user: User, editor_user: User, win: Platform
):
    rom = make_rom(win, "Portal", steam_id=400)
    owners, _, _ = (
        db_collection_handler.add_smart_collection(
            SmartCollection(
                name=name, description="", user_id=user.id, filter_criteria=criteria
            )
        )
        for name, user, criteria in (
            ("Owned", steam_user, {"owned_on_steam": True}),
            ("Theirs", editor_user, {"owned_on_steam": True}),
            ("Portal", steam_user, {"search_term": "Portal"}),
        )
    )
    steam_api.get_owned_games.return_value = [_game(400, "Portal")]

    with patch.object(
        db_rom_handler,
        "get_smart_collection_matches",
        wraps=db_rom_handler.get_smart_collection_matches,
    ) as matches:
        await sync_steam_library(steam_user)

    checked = {call.kwargs["smart_collection"].id for call in matches.call_args_list}
    assert checked == {owners.id}
    after = db_collection_handler.get_smart_collection(owners.id)
    assert after is not None and after.rom_ids == [rom.id]


async def test_an_account_unlinked_mid_sync_keeps_its_games_forgotten(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    async def unlink_while_fetching(steam_id: str) -> list[SteamOwnedGame]:
        unlink_steam_profile(steam_user)
        return [_game(220, "Half-Life 2")]

    steam_api.get_owned_games.side_effect = unlink_while_fetching

    with pytest.raises(SteamLibraryError, match="changed during the sync"):
        await sync_steam_library(steam_user)
    assert db_steam_library_handler.get_entries(steam_user.id) == []


async def test_a_private_library_is_an_error(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = None

    with pytest.raises(SteamLibraryError, match="Game details"):
        await sync_steam_library(steam_user)


async def test_an_unlinked_user_is_an_error(admin_user: User):
    with pytest.raises(SteamLibraryError, match="no linked Steam account"):
        await sync_steam_library(admin_user)


async def test_uses_the_existing_win_platform(win: Platform):
    platform = await steam_library_platform()

    assert platform.id == win.id


async def test_creates_the_win_platform_and_its_folder():
    with (
        patch(
            "handler.steam_library_handler.fs_platform_handler.add_platform",
            new_callable=AsyncMock,
        ) as add_folder,
        patch.object(
            meta_igdb_handler,
            "get_platform_discovery",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        platform = await steam_library_platform()

    add_folder.assert_awaited_once_with(fs_slug="win")
    assert (platform.slug, platform.fs_slug) == ("win", "win")
    assert db_platform_handler.get_platform_by_slug("win") is not None


async def test_a_folder_that_cannot_be_created_is_an_error():
    with patch(
        "handler.steam_library_handler.fs_platform_handler.add_platform",
        new_callable=AsyncMock,
        side_effect=PermissionError("read-only"),
    ):
        with pytest.raises(SteamLibraryError, match="platform folder"):
            await steam_library_platform()

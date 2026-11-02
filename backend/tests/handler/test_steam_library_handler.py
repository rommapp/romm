from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.factories import make_platform, make_rom

from adapters.services.steam import SteamWebAPIError
from adapters.services.steam_types import (
    SteamOwnedGame,
    SteamPlayerAchievement,
    SteamPlayerSummary,
)
from endpoints.responses.identity import UserSchema
from handler.database import (
    db_collection_handler,
    db_platform_handler,
    db_rom_handler,
    db_steam_library_handler,
    db_user_handler,
)
from handler.metadata import meta_igdb_handler
from handler.steam_library_handler import (
    STEAM_FS_SUBDIR,
    SteamLibraryError,
    SteamUserGameProgression,
    is_steam_game_completed,
    link_steam_profile,
    parse_steam_profile,
    resolve_steam_profile,
    steam_library_platform,
    steam_web_api,
    sync_steam_library,
    unlink_steam_profile,
)
from models.collection import SmartCollection
from models.platform import Platform
from models.rom import RomStorefront, RomUserStatus
from models.user import User

STEAM_ID = "76561197960287930"


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
    api.get_player_achievements = AsyncMock(return_value=[])
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


def _unlocks(*states: bool) -> list[SteamPlayerAchievement]:
    return [
        {"apiname": f"ACH_{i}", "achieved": int(done), "unlocktime": 1_700_000_000 + i}
        for i, done in enumerate(states)
    ]


def _progression(user: User) -> dict[str, Any]:
    stored = db_user_handler.get_user(user.id)
    assert stored is not None
    return stored.steam_progression or {}


async def test_a_sync_stores_unlocks_and_completes_fully_unlocked_games(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    regional_copy = make_rom(win, "Half-Life 2 (EU)", steam_id=220)
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000),
        _game(400, "Portal", playtime=30, last_played=1_700_000_500),
    ]
    steam_api.get_player_achievements.side_effect = lambda _id, app_id: (
        _unlocks(True, True) if app_id == 220 else _unlocks(True, False)
    )

    await sync_steam_library(steam_user)

    results = {g["rom_steam_id"]: g for g in _progression(steam_user)["results"]}
    assert (results[220]["num_unlocked"], results[220]["num_achievements"]) == (2, 2)
    assert (results[400]["num_unlocked"], results[400]["num_achievements"]) == (1, 2)
    assert results[400]["earned_achievements"] == [
        {"api_name": "ACH_0", "unlock_time": 1_700_000_000}
    ]
    assert results[220]["rtime_last_played"] == 1_700_000_000
    completed = db_rom_handler.get_rom_user(regional_copy.id, steam_user.id)
    assert completed is not None and completed.status == RomUserStatus.COMPLETED_100
    portal = db_steam_library_handler.get_entries(steam_user.id)
    portal_rom_id = next(e.rom_id for e in portal if e.steam_app_id == 400)
    started = db_rom_handler.get_rom_user(portal_rom_id, steam_user.id)
    assert started is None or started.status is None


async def test_a_game_not_played_since_the_last_sync_is_not_read_again(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000)
    ]
    steam_api.get_player_achievements.return_value = _unlocks(True)
    await sync_steam_library(steam_user)
    user = db_user_handler.get_user(steam_user.id)
    assert user is not None

    await sync_steam_library(user)
    assert steam_api.get_player_achievements.await_count == 1

    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=120, last_played=1_700_009_000)
    ]
    await sync_steam_library(user)
    assert steam_api.get_player_achievements.await_count == 2


async def test_a_game_never_played_is_not_read(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [_game(220, "Half-Life 2")]

    await sync_steam_library(steam_user)

    steam_api.get_player_achievements.assert_not_awaited()
    assert _progression(steam_user)["results"] == []


async def test_a_game_without_stats_is_kept_so_it_is_not_read_again(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000)
    ]

    await sync_steam_library(steam_user)

    [game] = _progression(steam_user)["results"]
    assert (game["num_achievements"], game["num_unlocked"]) == (0, 0)


async def test_a_failed_read_keeps_what_the_last_sync_stored(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000)
    ]
    steam_api.get_player_achievements.return_value = _unlocks(True, False)
    await sync_steam_library(steam_user)
    user = db_user_handler.get_user(steam_user.id)
    assert user is not None
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=95, last_played=1_700_000_900)
    ]
    steam_api.get_player_achievements.side_effect = SteamWebAPIError(
        "Steam answered with HTTP 500", status=500
    )

    await sync_steam_library(user)

    [game] = _progression(user)["results"]
    assert (game["num_unlocked"], game["playtime_forever"]) == (1, 90)


async def test_malformed_unlocks_are_coerced_or_dropped(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000)
    ]
    steam_api.get_player_achievements.return_value = [
        {"apiname": "WIN", "achieved": 1, "unlocktime": "1700000000"},
        {"apiname": "LATE", "achieved": 1, "unlocktime": None},
        {"apiname": "LOCKED", "achieved": "0", "unlocktime": 0},
        {"apiname": 5, "achieved": 1, "unlocktime": 1},
        {"achieved": 1},
        "NOT_AN_ACHIEVEMENT",
    ]

    await sync_steam_library(steam_user)

    UserSchema.model_validate(db_user_handler.get_user(steam_user.id))
    [game] = _progression(steam_user)["results"]
    assert game["earned_achievements"] == [
        {"api_name": "WIN", "unlock_time": 1_700_000_000},
        {"api_name": "LATE", "unlock_time": 0},
    ]
    assert (game["num_achievements"], game["num_unlocked"]) == (3, 2)


async def test_refused_achievements_leave_the_library_sync_intact(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000)
    ]
    steam_api.get_player_achievements.side_effect = SteamWebAPIError(
        "Steam rejected the API key", status=403
    )

    result = await sync_steam_library(steam_user)

    assert result.owned == 1
    assert len(db_steam_library_handler.get_entries(steam_user.id)) == 1
    assert _progression(steam_user) == {}


async def test_progression_read_for_an_unlinked_account_is_not_stored(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000)
    ]

    async def unlink_while_reading(
        _steam_id: str, _app_id: int
    ) -> list[SteamPlayerAchievement]:
        unlink_steam_profile(steam_user)
        return _unlocks(True)

    steam_api.get_player_achievements.side_effect = unlink_while_reading

    await sync_steam_library(steam_user)

    assert _progression(steam_user) == {}


def _summary(steam_id: str, name: str) -> SteamPlayerSummary:
    return {
        "steamid": steam_id,
        "personaname": name,
        "profileurl": f"https://steamcommunity.com/profiles/{steam_id}/",
        "communityvisibilitystate": 3,
    }


def test_linking_another_account_or_unlinking_drops_the_progression(steam_user: User):
    stored = {"total": 1, "results": []}
    db_user_handler.update_user(steam_user.id, {"steam_progression": stored})

    link_steam_profile(steam_user, _summary(STEAM_ID, "Gabe"))
    assert _progression(steam_user) == stored

    user = db_user_handler.get_user(steam_user.id)
    assert user is not None
    link_steam_profile(user, _summary("76561197960265728", "Other"))
    assert _progression(user) == {}

    db_user_handler.update_user(user.id, {"steam_progression": stored})
    unlink_steam_profile(user)
    assert _progression(user) == {}


@pytest.mark.parametrize(
    ("total", "unlocked", "expected"),
    [(2, 2, True), (2, 1, False), (0, 0, False)],
)
def test_a_game_is_completed_only_with_every_achievement(
    total: int, unlocked: int, expected: bool
):
    game: SteamUserGameProgression = {
        "rom_steam_id": 220,
        "rtime_last_played": None,
        "playtime_forever": 1,
        "num_achievements": total,
        "num_unlocked": unlocked,
        "earned_achievements": [],
    }
    assert is_steam_game_completed(game) is expected


async def test_games_past_the_read_budget_wait_for_the_next_sync(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(220, "Half-Life 2", playtime=90, last_played=1_700_000_000),
        _game(400, "Portal", playtime=30, last_played=1_700_000_500),
    ]
    steam_api.get_player_achievements.return_value = _unlocks(True)

    with patch("handler.steam_library_handler.STEAM_ACHIEVEMENT_READS_PER_SYNC", 1):
        await sync_steam_library(steam_user)
        assert len(_progression(steam_user)["results"]) == 1

        user = db_user_handler.get_user(steam_user.id)
        assert user is not None
        await sync_steam_library(user)

    assert {g["rom_steam_id"] for g in _progression(user)["results"]} == {220, 400}
    assert steam_api.get_player_achievements.await_count == 2


async def test_reads_stop_after_several_failures_in_a_row(
    steam_api: MagicMock, steam_user: User, win: Platform
):
    steam_api.get_owned_games.return_value = [
        _game(app_id, f"Game {app_id}", playtime=10, last_played=1_700_000_000)
        for app_id in range(1, 6)
    ]
    steam_api.get_player_achievements.side_effect = SteamWebAPIError(
        "Steam did not answer in time"
    )

    await sync_steam_library(steam_user)

    assert steam_api.get_player_achievements.await_count == 3

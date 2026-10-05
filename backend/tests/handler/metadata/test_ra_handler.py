"""Tests for the RetroAchievements metadata handler."""

import json
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status
from tests.timezones import local_timezone

from adapters.services.retroachievements_types import RAGameExtendedDetails
from handler.filesystem import fs_resource_handler
from handler.metadata import ra_handler
from handler.metadata.ra_handler import RA_PLATFORM_LIST, RAHandler
from utils.platform_slugs import UniversalPlatformSlug as UPS


@pytest.fixture
def handler() -> RAHandler:
    return RAHandler()


def test_get_platform_unsupported_returns_none(handler: RAHandler):
    platform = handler.get_platform("not-a-real-platform")
    assert platform["ra_id"] is None
    assert platform["slug"] == "not-a-real-platform"


def test_platform_list_uses_ups_keys():
    """Every entry in RA_PLATFORM_LIST should be a UniversalPlatformSlug."""
    for key in RA_PLATFORM_LIST.keys():
        assert isinstance(key, UPS)


def test_release_date_is_utc_midnight_whatever_the_host_timezone():
    # CI runs in UTC, so a naive timestamp only shows its drift under another zone.
    details = cast(RAGameExtendedDetails, {"Released": "1991-08-23 00:00:00"})
    with local_timezone("Asia/Tokyo"):
        metadata = ra_handler.extract_metadata_from_rom_details(
            MagicMock(), details, hash_match=False
        )

    expected = datetime(1991, 8, 23, tzinfo=timezone.utc).timestamp()
    assert metadata["first_release_date"] == int(expected)


class TestSearchRom:
    """The hash index must only map hashes of games that actually have a set."""

    @pytest.fixture(autouse=True)
    def _pin_cache_ttl(self, monkeypatch: pytest.MonkeyPatch):
        """A local .env may set this to 0, which would force a refresh every time."""
        monkeypatch.setattr(ra_handler, "REFRESH_RETROACHIEVEMENTS_CACHE_DAYS", 30)

    @pytest.fixture
    def resources_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
        """Back the platform resources directory with a real one, so mtime is real too."""

        def resolve(file_path: str) -> Path:
            return tmp_path / Path(file_path).name

        def write_file(file: bytes, path: str, filename: str) -> None:
            (tmp_path / filename).write_bytes(file)

        monkeypatch.setattr(
            fs_resource_handler,
            "get_platform_resources_path",
            lambda _platform_id: "roms/1",
        )
        monkeypatch.setattr(
            fs_resource_handler,
            "file_exists",
            AsyncMock(side_effect=lambda file_path: resolve(file_path).is_file()),
        )
        monkeypatch.setattr(fs_resource_handler, "validate_path", resolve)
        monkeypatch.setattr(
            fs_resource_handler,
            "read_file",
            AsyncMock(side_effect=lambda file_path: resolve(file_path).read_bytes()),
        )
        monkeypatch.setattr(
            fs_resource_handler,
            "write_file",
            AsyncMock(side_effect=write_file),
        )
        return tmp_path

    def _make_rom(self) -> MagicMock:
        rom = MagicMock()
        rom.platform.id = 1
        rom.platform.ra_id = 2
        return rom

    async def test_skips_games_without_achievements(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch, resources_dir: Path
    ):
        get_game_list = AsyncMock(
            return_value=[{"ID": 10210, "Hashes": ["ABCDEF", "123456"]}]
        )
        monkeypatch.setattr(handler.ra_service, "get_game_list", get_game_list)

        ra_id = await handler._search_rom(self._make_rom(), "abcdef")

        get_game_list.assert_awaited_once_with(
            system_id=2,
            only_games_with_achievements=True,
            include_hashes=True,
        )
        assert ra_id == 10210

        cached = resources_dir / handler.HASHES_FILE_NAME
        assert json.loads(cached.read_bytes()) == {"abcdef": 10210, "123456": 10210}

    async def test_reads_the_cached_index_without_refetching(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch, resources_dir: Path
    ):
        cache_file = resources_dir / handler.HASHES_FILE_NAME
        cache_file.write_bytes(json.dumps({"abcdef": 10210}).encode("utf-8"))

        get_game_list = AsyncMock()
        monkeypatch.setattr(handler.ra_service, "get_game_list", get_game_list)

        ra_id = await handler._search_rom(self._make_rom(), "ABCDEF")

        assert ra_id == 10210
        get_game_list.assert_not_awaited()

    async def test_parses_the_cached_index_once_until_it_changes(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch, resources_dir: Path
    ):
        cache_file = resources_dir / handler.HASHES_FILE_NAME
        cache_file.write_bytes(json.dumps({"abcdef": 10210}).encode("utf-8"))
        read_file = fs_resource_handler.read_file

        assert await handler._search_rom(self._make_rom(), "abcdef") == 10210
        assert await handler._search_rom(self._make_rom(), "abcdef") == 10210
        assert read_file.await_count == 1  # type: ignore[attr-defined]

        cache_file.write_bytes(json.dumps({"abcdef": 10211}).encode("utf-8"))
        stat = cache_file.stat()
        os.utime(cache_file, (stat.st_atime, stat.st_mtime + 1))

        assert await handler._search_rom(self._make_rom(), "abcdef") == 10211
        assert read_file.await_count == 2  # type: ignore[attr-defined]

    async def test_ignores_an_unfiltered_index_from_an_older_version(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch, resources_dir: Path
    ):
        """Freshness is an mtime test, so a filter change has to come with a new filename."""
        legacy_cache = resources_dir / "ra_hashes_v2.json"
        legacy_cache.write_bytes(json.dumps({"abcdef": 10138}).encode("utf-8"))

        get_game_list = AsyncMock(return_value=[{"ID": 10210, "Hashes": ["ABCDEF"]}])
        monkeypatch.setattr(handler.ra_service, "get_game_list", get_game_list)

        ra_id = await handler._search_rom(self._make_rom(), "abcdef")

        get_game_list.assert_awaited_once()
        assert ra_id == 10210

    async def test_does_not_cache_a_failed_download(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch, resources_dir: Path
    ):
        """The service answers a failed request with {}, not a game list."""
        monkeypatch.setattr(
            handler.ra_service, "get_game_list", AsyncMock(return_value={})
        )

        with pytest.raises(HTTPException):
            await handler._search_rom(self._make_rom(), "abcdef")
        assert not (resources_dir / handler.HASHES_FILE_NAME).exists()

    async def test_returns_none_without_a_platform_ra_id(self, handler: RAHandler):
        rom = self._make_rom()
        rom.platform.ra_id = None

        assert await handler._search_rom(rom, "abcdef") is None


class TestHashMatch:
    """`hash_match` says whether RA lists the ROM's RA hash for the matched game."""

    GAME_DETAILS = {"ID": 17353, "Title": "Game", "Achievements": {}}

    @pytest.fixture
    def rom(self) -> MagicMock:
        rom = MagicMock()
        rom.fs_name = "game.nds"
        rom.platform.id = 1
        rom.platform.ra_id = 18
        return rom

    @pytest.fixture(autouse=True)
    def _stub_service(self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            handler.ra_service,
            "get_game_extended_details",
            AsyncMock(return_value=self.GAME_DETAILS),
        )
        monkeypatch.setattr(
            handler,
            "_search_rom",
            AsyncMock(side_effect=lambda _rom, ra_hash: {"abcdef": 17353}.get(ra_hash)),
        )

    async def test_a_hash_lookup_match_is_a_hash_match(
        self, handler: RAHandler, rom: MagicMock
    ):
        result = await handler.get_rom(rom, ra_hash="abcdef")

        assert result["ra_id"] == 17353
        assert result["ra_metadata"]["hash_match"] is True

    async def test_a_failed_details_request_stays_a_failure(
        self, handler: RAHandler, rom: MagicMock, monkeypatch: pytest.MonkeyPatch
    ):
        unavailable = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        monkeypatch.setattr(
            handler.ra_service,
            "get_game_extended_details",
            AsyncMock(side_effect=unavailable),
        )

        with pytest.raises(HTTPException) as exc_info:
            await handler.get_rom(rom, ra_hash="abcdef")

        assert exc_info.value is unavailable

    async def test_a_game_ra_retired_since_the_index_is_a_miss(
        self, handler: RAHandler, rom: MagicMock, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            handler.ra_service,
            "get_game_extended_details",
            AsyncMock(return_value=None),
        )

        assert (await handler.get_rom(rom, ra_hash="abcdef"))["ra_id"] is None

    async def test_an_id_match_whose_hash_ra_lists_is_a_hash_match(
        self, handler: RAHandler, rom: MagicMock
    ):
        """A Hasheous-supplied RA id still counts when RA lists the ROM's hash."""
        result = await handler.get_rom_by_id(rom, ra_id=17353, ra_hash="abcdef")

        assert result["ra_metadata"]["hash_match"] is True

    @pytest.mark.parametrize("ra_hash", [None, "", "ffffff"])
    async def test_an_id_match_without_a_listed_hash_is_not(
        self, handler: RAHandler, rom: MagicMock, ra_hash: str | None
    ):
        result = await handler.get_rom_by_id(rom, ra_id=17353, ra_hash=ra_hash)

        assert result["ra_id"] == 17353
        assert result["ra_metadata"]["hash_match"] is False

    async def test_a_hash_listed_for_another_game_is_not(
        self, handler: RAHandler, rom: MagicMock
    ):
        result = await handler.get_rom_by_id(rom, ra_id=1, ra_hash="abcdef")

        assert result["ra_metadata"]["hash_match"] is False

    async def test_a_failed_hash_check_still_returns_the_game(
        self, handler: RAHandler, rom: MagicMock, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            handler, "_search_rom", AsyncMock(side_effect=HTTPException(503))
        )
        rom.ra_id = None

        result = await handler.get_rom_by_id(rom, ra_id=17353, ra_hash="abcdef")

        assert result["ra_id"] == 17353
        assert result["ra_metadata"]["hash_match"] is False

    async def test_a_failed_hash_check_keeps_the_recorded_match(
        self, handler: RAHandler, rom: MagicMock, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            handler, "_search_rom", AsyncMock(side_effect=HTTPException(503))
        )
        rom.ra_id = 17353
        rom.ra_hash = "abcdef"
        rom.ra_metadata = {"hash_match": True}

        result = await handler.get_rom_by_id(rom, ra_id=17353, ra_hash="abcdef")

        assert result["ra_metadata"]["hash_match"] is True

    async def test_a_failed_hash_check_drops_the_match_for_a_new_hash(
        self, handler: RAHandler, rom: MagicMock, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            handler, "_search_rom", AsyncMock(side_effect=HTTPException(503))
        )
        rom.ra_id = 17353
        rom.ra_hash = "abcdef"
        rom.ra_metadata = {"hash_match": True}

        result = await handler.get_rom_by_id(rom, ra_id=17353, ra_hash="ffffff")

        assert result["ra_metadata"]["hash_match"] is False


def _rom(fs_name: str = "game.gba", ra_id: int | None = 5) -> MagicMock:
    rom = MagicMock()
    rom.id = 7
    rom.fs_name = fs_name
    rom.platform.id = 3
    rom.platform.ra_id = ra_id
    return rom


DETAILS = {
    "ID": 42,
    "Title": "Game",
    "ImageTitle": "/Images/title.png",
    "ImageIngame": "/Images/ingame.png",
    "Released": "1992-11-21 00:00:00",
    "Publisher": "Pub",
    "Developer": "Dev",
    "Genre": None,
    "Achievements": {
        "1": {
            "ID": 1,
            "Title": "First",
            "Description": "Do it",
            "Points": 5,
            "NumAwarded": 10,
            "NumAwardedHardcore": 4,
            "BadgeName": "123",
            "DisplayOrder": 0,
            "type": "progression",
        }
    },
}


class TestHeartbeat:
    async def test_a_reply_is_healthy(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch
    ):
        call = AsyncMock(return_value={"Achievement": {}})
        monkeypatch.setattr(handler.ra_service, "get_achievement_of_the_week", call)

        assert await handler.heartbeat() is True

    @pytest.mark.parametrize(
        "reply", [{}, None, HTTPException(503)], ids=["empty", "none", "error"]
    )
    async def test_no_reply_is_unhealthy(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch, reply: object
    ):
        call = AsyncMock(
            side_effect=reply if isinstance(reply, Exception) else None,
            return_value=reply,
        )
        monkeypatch.setattr(handler.ra_service, "get_achievement_of_the_week", call)

        assert await handler.heartbeat() is False

    async def test_without_a_key_nothing_is_asked(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ra_handler, "RETROACHIEVEMENTS_API_KEY", "")
        call = AsyncMock()
        monkeypatch.setattr(handler.ra_service, "get_achievement_of_the_week", call)

        assert await handler.heartbeat() is False
        call.assert_not_awaited()


class TestHelpers:
    @pytest.mark.parametrize(
        ("fs_name", "ra_id"),
        [("Game (ra-123).gba", 123), ("Game (RA-9).gba", 9), ("Game.gba", None)],
    )
    def test_reads_the_ra_id_tag(self, fs_name: str, ra_id: int | None):
        assert RAHandler.extract_ra_id_from_filename(fs_name) == ra_id

    def test_a_supported_platform_has_its_ra_id(self, handler: RAHandler):
        assert handler.get_platform("gba") == {
            "ra_id": 5,
            "slug": "gba",
            "name": "Game Boy Advance",
        }

    @pytest.mark.parametrize("released", [None, "", "   "])
    def test_a_missing_release_date_is_none(self, released: str | None):
        details = cast(RAGameExtendedDetails, {"Released": released})

        metadata = ra_handler.extract_metadata_from_rom_details(
            _rom(), details, hash_match=False
        )

        assert metadata["first_release_date"] is None

    def test_metadata_carries_credits_and_achievement_badges(self):
        metadata = ra_handler.extract_metadata_from_rom_details(
            _rom(), cast(RAGameExtendedDetails, DETAILS), hash_match=True
        )

        assert metadata["genres"] == []
        assert metadata["publishers"] == ["Pub"]
        assert metadata["developers"] == ["Dev"]
        assert metadata["companies"] == ["Pub", "Dev"]
        [achievement] = metadata["achievements"]
        badges = fs_resource_handler.get_ra_badges_path(3, 7)
        assert achievement == {
            "ra_id": 1,
            "title": "First",
            "description": "Do it",
            "points": 5,
            "num_awarded": 10,
            "num_awarded_hardcore": 4,
            "badge_id": "123",
            "badge_url_lock": "https://media.retroachievements.org/Badge/123_lock.png",
            "badge_path_lock": f"{badges}/123_lock.png",
            "badge_url": "https://media.retroachievements.org/Badge/123.png",
            "badge_path": f"{badges}/123.png",
            "display_order": 0,
            "type": "progression",
        }


class TestGetRom:
    @pytest.fixture
    def details(self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
        call = AsyncMock(return_value=DETAILS)
        monkeypatch.setattr(handler.ra_service, "get_game_extended_details", call)
        return call

    @pytest.fixture
    def search(self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
        call = AsyncMock(return_value=42)
        monkeypatch.setattr(handler, "_search_rom", call)
        return call

    async def test_a_hash_match_returns_the_game_with_its_images(
        self, handler: RAHandler, details: AsyncMock, search: AsyncMock
    ):
        result = await handler.get_rom(_rom(), "abcdef")

        assert result["ra_id"] == 42
        assert result["name"] == "Game"
        assert result["url_cover"] == "https://retroachievements.org/Images/title.png"
        assert result["url_screenshots"] == [
            "https://retroachievements.org/Images/ingame.png"
        ]
        details.assert_awaited_once_with(42)

    async def test_a_platform_ra_does_not_know_is_skipped(
        self, handler: RAHandler, details: AsyncMock, search: AsyncMock
    ):
        assert await handler.get_rom(_rom(ra_id=None), "abcdef") == {"ra_id": None}
        search.assert_not_awaited()

    async def test_a_filename_tag_is_looked_up_by_id(
        self, handler: RAHandler, details: AsyncMock, search: AsyncMock
    ):
        result = await handler.get_rom(_rom("Game (ra-42).gba"), "abcdef")

        assert result["ra_id"] == 42
        assert result["url_cover"] == (
            "https://media.retroachievements.org/Images/title.png"
        )
        details.assert_awaited_once_with(42)

    async def test_an_unknown_filename_tag_falls_back_to_the_hash(
        self, handler: RAHandler, details: AsyncMock, search: AsyncMock
    ):
        details.side_effect = [None, DETAILS]

        result = await handler.get_rom(_rom("Game (ra-999).gba"), "abcdef")

        assert result["ra_id"] == 42
        assert [c.args for c in details.await_args_list] == [(999,), (42,)]

    async def test_without_a_hash_there_is_no_match(
        self, handler: RAHandler, details: AsyncMock, search: AsyncMock
    ):
        assert await handler.get_rom(_rom(), "") == {"ra_id": None}
        search.assert_not_awaited()

    async def test_a_hash_ra_does_not_list_is_no_match(
        self, handler: RAHandler, details: AsyncMock, search: AsyncMock
    ):
        search.return_value = None

        assert await handler.get_rom(_rom(), "abcdef") == {"ra_id": None}
        details.assert_not_awaited()

    async def test_details_without_an_id_are_no_match(
        self, handler: RAHandler, details: AsyncMock, search: AsyncMock
    ):
        details.return_value = {"Title": "Game"}

        assert await handler.get_rom(_rom(), "abcdef") == {"ra_id": None}

    @pytest.mark.parametrize(
        "reply", [None, {"Title": "Game"}], ids=["unknown", "no_id"]
    )
    async def test_an_id_ra_cannot_resolve_is_no_match(
        self, handler: RAHandler, details: AsyncMock, reply: object
    ):
        details.return_value = reply

        assert await handler.get_rom_by_id(_rom(), 42) == {"ra_id": None}

    async def test_no_id_asks_nothing(self, handler: RAHandler, details: AsyncMock):
        assert await handler.get_rom_by_id(_rom(), 0) == {"ra_id": None}
        details.assert_not_awaited()


def _completion(game_id: int, **overrides: object) -> dict[str, object]:
    return {
        "GameID": game_id,
        "MaxPossible": 10,
        "NumAwarded": 2,
        "NumAwardedHardcore": 1,
        "MostRecentAwardedDate": "2026-01-02T00:00:00+00:00",
        "HighestAwardKind": None,
        **overrides,
    }


class TestUserProgression:
    @pytest.fixture
    def completion(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch
    ) -> list[dict[str, object]]:
        games: list[dict[str, object]] = []

        async def iterate(_username: str) -> AsyncIterator[dict[str, object]]:
            for game in games:
                yield game

        monkeypatch.setattr(
            handler.ra_service, "iter_user_completion_progress", iterate
        )
        return games

    @pytest.fixture
    def game_progress(
        self, handler: RAHandler, monkeypatch: pytest.MonkeyPatch
    ) -> AsyncMock:
        call = AsyncMock(
            return_value={
                "Achievements": {
                    "1": {"BadgeName": "a", "DateEarned": "2026-01-01"},
                    "2": {
                        "BadgeName": "b",
                        "DateEarned": "2026-01-02",
                        "DateEarnedHardcore": "2026-01-02",
                    },
                    "3": {"BadgeName": "c"},
                }
            }
        )
        monkeypatch.setattr(handler.ra_service, "get_user_game_progress", call)
        return call

    async def test_reads_each_games_earned_achievements(
        self,
        handler: RAHandler,
        completion: list[dict[str, object]],
        game_progress: AsyncMock,
    ):
        completion.append(_completion(42, HighestAwardKind="beaten-softcore"))

        progression = await handler.get_user_progression("me")

        assert progression == {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": 42,
                    "max_possible": 10,
                    "num_awarded": 2,
                    "num_awarded_hardcore": 1,
                    "most_recent_awarded_date": "2026-01-02T00:00:00+00:00",
                    "highest_award_kind": "beaten-softcore",
                    "earned_achievements": [
                        {"id": "a", "date": "2026-01-01"},
                        {
                            "id": "b",
                            "date": "2026-01-02",
                            "date_hardcore": "2026-01-02",
                        },
                    ],
                }
            ],
        }
        game_progress.assert_awaited_once_with(username="me", game_id=42)

    async def test_an_unchanged_game_is_reused_with_its_latest_award(
        self,
        handler: RAHandler,
        completion: list[dict[str, object]],
        game_progress: AsyncMock,
    ):
        completion.append(_completion(42, HighestAwardKind="mastered"))
        previous = await handler.get_user_progression("me")
        previous["results"][0]["highest_award_kind"] = "beaten-hardcore"
        game_progress.reset_mock()

        progression = await handler.get_user_progression("me", previous)

        game_progress.assert_not_awaited()
        [game] = progression["results"]
        assert game["highest_award_kind"] == "mastered"
        assert len(game["earned_achievements"]) == 2

    @pytest.mark.parametrize(
        "change",
        [
            {"NumAwarded": 3},
            {"NumAwardedHardcore": 2},
            {"MostRecentAwardedDate": "2026-02-01T00:00:00+00:00"},
        ],
        ids=["awarded", "hardcore", "date"],
    )
    async def test_a_changed_game_is_read_again(
        self,
        handler: RAHandler,
        completion: list[dict[str, object]],
        game_progress: AsyncMock,
        change: dict[str, object],
    ):
        completion.append(_completion(42))
        previous = await handler.get_user_progression("me")
        completion[0] = _completion(42, **change)
        game_progress.reset_mock()

        await handler.get_user_progression("me", previous)

        game_progress.assert_awaited_once()

    @pytest.mark.parametrize("reply", [None, {}], ids=["none", "no_achievements"])
    async def test_a_game_without_progress_has_no_earned_achievements(
        self,
        handler: RAHandler,
        completion: list[dict[str, object]],
        game_progress: AsyncMock,
        reply: object,
    ):
        completion.append(_completion(42))
        game_progress.return_value = reply

        progression = await handler.get_user_progression("me")

        assert progression["results"][0]["earned_achievements"] == []

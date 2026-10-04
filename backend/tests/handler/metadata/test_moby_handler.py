"""Tests for the MobyGames metadata handler."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from adapters.services.mobygames_types import MobyGame
from handler.metadata import moby_handler
from handler.metadata.base_handler import PS1_SERIAL_INDEX_KEY
from handler.metadata.moby_handler import (
    PS1_MOBY_ID,
    PS2_MOBY_ID,
    PSP_MOBY_ID,
    SWITCH_MOBY_ID,
    MobyGamesHandler,
)
from handler.redis_handler import async_cache
from models.rom import Rom


class TestSonySerialFilenames:
    """Tests for Sony serial resolution in get_rom."""

    @pytest.mark.asyncio
    async def test_serial_at_filename_start_resolves_title(self):
        """A serial in the first two characters of the filename must still hit
        the serial index. Regression: re.IGNORECASE was passed as the ``pos``
        argument of ``Pattern.search()``, skipping the first two characters,
        so files named by their serial (e.g. ``SCUS-94163.bin``) were never
        resolved."""
        handler = MobyGamesHandler()

        with (
            patch(
                "handler.metadata.moby_handler.MobyGamesHandler.is_enabled",
                return_value=True,
            ),
            patch.object(async_cache, "hget", new_callable=AsyncMock) as mock_hget,
            patch.object(
                MobyGamesHandler,
                "_search_rom",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_hget.return_value = json.dumps({"title": "Gran Turismo"})
            result = await handler.get_rom(
                Rom(fs_name="SCUS-94163.bin"), "SCUS-94163.bin", PS1_MOBY_ID
            )

        mock_hget.assert_awaited_once_with(PS1_SERIAL_INDEX_KEY, "SCUS-94163")
        assert result.get("name") == "Gran Turismo"
        assert result["moby_id"] is None


class TestSearchTermEncoding:
    """Tests that search terms are passed to the service layer unencoded."""

    @pytest.mark.asyncio
    async def test_search_rom_does_not_pre_encode_special_characters(self):
        """The service layer URL-encodes the title exactly once via
        ``with_query``. Regression: the handler pre-quoted the term, so titles
        containing "&", "+" or "'" were double-encoded ("&" -> "%2526") and
        never matched (e.g. "Sonic & Knuckles",
        "Super Mario 3D World + Bowser's Fury")."""
        handler = MobyGamesHandler()

        with patch.object(
            handler.moby_service,
            "list_games",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list_games:
            await handler._search_rom("Sonic & Knuckles", platform_moby_id=16)

        mock_list_games.assert_awaited_once()
        await_args = mock_list_games.await_args
        assert await_args is not None
        title = await_args.kwargs["title"]
        assert title == "Sonic & Knuckles"
        assert "%" not in title

    @pytest.mark.asyncio
    async def test_get_matched_roms_by_name_does_not_pre_encode(self):
        """Same double-encoding regression for the manual-search path."""
        handler = MobyGamesHandler()

        with (
            patch(
                "handler.metadata.moby_handler.MobyGamesHandler.is_enabled",
                return_value=True,
            ),
            patch.object(
                handler.moby_service,
                "list_games",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_list_games,
        ):
            await handler.get_matched_roms_by_name(
                "Super Mario 3D World + Bowser's Fury", platform_moby_id=203
            )

        mock_list_games.assert_awaited_once()
        await_args = mock_list_games.await_args
        assert await_args is not None
        title = await_args.kwargs["title"]
        assert title == "Super Mario 3D World + Bowser's Fury"
        assert "%" not in title


def _game(game_id: int, title: str) -> MobyGame:
    return {
        "game_id": game_id,
        "title": title,
        "description": f"About {title}",
        "moby_score": 7.5,
        "moby_url": f"https://moby/{game_id}",
        "num_votes": 1,
        "official_url": None,
        "genres": [
            {
                "genre_name": "Action",
                "genre_id": 1,
                "genre_category": "Basic Genres",
                "genre_category_id": 1,
            }
        ],
        "alternate_titles": [{"title": f"{title} DX", "description": "Alt"}],
        "platforms": [
            {
                "platform_id": 15,
                "platform_name": "SNES",
                "first_release_date": "1991",
            }
        ],
        "sample_cover": {
            "image": f"https://moby/{game_id}/cover.jpg",
            "thumbnail_image": f"https://moby/{game_id}/cover-thumb.jpg",
            "height": 1,
            "width": 1,
            "platforms": ["SNES"],
        },
        "sample_screenshots": [
            {
                "image": f"https://moby/{game_id}/shot.jpg",
                "thumbnail_image": f"https://moby/{game_id}/shot-thumb.jpg",
                "caption": "",
                "height": 1,
                "width": 1,
            }
        ],
    }


@pytest.fixture
def moby(monkeypatch: pytest.MonkeyPatch) -> tuple[MobyGamesHandler, AsyncMock]:
    """A handler with a key, its list_games answering by title or id."""
    monkeypatch.setattr(moby_handler, "MOBYGAMES_API_KEY", "key")
    handler = MobyGamesHandler()
    by_title: dict[str, list[MobyGame]] = {}
    by_id: dict[int, list[MobyGame]] = {}

    async def list_games(**query: Any) -> list[MobyGame]:
        if query.get("game_id"):
            return by_id.get(query["game_id"], [])
        return by_title.get(query.get("title") or "", [])

    list_games_mock = AsyncMock(side_effect=list_games)
    list_games_mock.by_title = by_title
    list_games_mock.by_id = by_id
    monkeypatch.setattr(handler.moby_service, "list_games", list_games_mock)
    return handler, list_games_mock


SNES = 15


class TestHeartbeat:
    @pytest.mark.parametrize(
        ("reply", "healthy"),
        [([{"group_id": 1}], True), ([], False), (RuntimeError("down"), False)],
        ids=["groups", "empty", "error"],
    )
    async def test_reports_whether_mobygames_answers(
        self,
        moby: tuple[MobyGamesHandler, AsyncMock],
        monkeypatch: pytest.MonkeyPatch,
        reply: object,
        healthy: bool,
    ):
        handler, _ = moby
        call = AsyncMock(
            side_effect=reply if isinstance(reply, Exception) else None,
            return_value=reply,
        )
        monkeypatch.setattr(handler.moby_service, "list_groups", call)

        assert await handler.heartbeat() is healthy

    async def test_without_a_key_nothing_is_asked(
        self, moby: tuple[MobyGamesHandler, AsyncMock], monkeypatch: pytest.MonkeyPatch
    ):
        handler, list_games = moby
        monkeypatch.setattr(moby_handler, "MOBYGAMES_API_KEY", "")
        groups = AsyncMock()
        monkeypatch.setattr(handler.moby_service, "list_groups", groups)

        assert await handler.heartbeat() is False
        assert await handler.get_rom(Rom(fs_name="a.sfc"), "a.sfc", SNES) == {
            "moby_id": None
        }
        assert await handler.get_rom_by_id(1) == {"moby_id": None}
        assert await handler.get_matched_rom_by_id(1) is None
        assert await handler.get_matched_roms_by_name("a", SNES) == []
        groups.assert_not_awaited()
        list_games.assert_not_awaited()


class TestHelpers:
    @pytest.mark.parametrize(
        ("fs_name", "moby_id"),
        [("Game (moby-123).sfc", 123), ("Game (MOBY-9).sfc", 9), ("Game.sfc", None)],
    )
    def test_reads_the_moby_id_tag(self, fs_name: str, moby_id: int | None):
        assert MobyGamesHandler.extract_mobygames_id_from_filename(fs_name) == moby_id

    def test_a_supported_platform_has_its_moby_id(self):
        assert MobyGamesHandler().get_platform("snes") == {
            "moby_id": 15,
            "slug": "snes",
            "moby_slug": "snes",
            "name": "SNES",
        }

    def test_an_unknown_platform_has_none(self):
        assert MobyGamesHandler().get_platform("not-a-platform") == {
            "moby_id": None,
            "slug": "not-a-platform",
        }

    def test_metadata_carries_score_genres_titles_and_platforms(self):
        metadata = moby_handler.extract_metadata_from_moby_rom(_game(1, "Zelda"))

        assert metadata == {
            "moby_score": "7.5",
            "genres": ["Action"],
            "alternate_titles": ["Zelda DX"],
            "platforms": [{"moby_id": 15, "name": "SNES"}],
        }

    def test_a_game_without_a_score_has_none(self):
        unscored: MobyGame = {**_game(1, "Zelda"), "moby_score": None}

        metadata = moby_handler.extract_metadata_from_moby_rom(unscored)

        assert metadata["moby_score"] is None


class TestGetRom:
    async def test_a_title_match_returns_the_game(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby
        list_games.by_title["zelda"] = [_game(2, "Zelda")]

        result = await handler.get_rom(
            Rom(fs_name="Zelda (USA).sfc"), "Zelda (USA).sfc", SNES
        )

        assert result == {
            "moby_id": 2,
            "name": "Zelda",
            "summary": "About Zelda",
            "url_cover": "https://moby/2/cover.jpg",
            "url_screenshots": ["https://moby/2/shot.jpg"],
            "moby_metadata": moby_handler.extract_metadata_from_moby_rom(
                _game(2, "Zelda")
            ),
        }
        # The search drops the tags and is lowercased.
        assert list_games.await_args_list[0].kwargs == {
            "platform_ids": [SNES],
            "title": "zelda",
        }

    async def test_empty_fields_are_left_out(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby
        list_games.by_title["Zelda"] = [
            {
                **_game(2, "Zelda"),
                "description": "",
                "sample_cover": None,
                "sample_screenshots": [],
            }
        ]

        result = await handler.get_rom(Rom(fs_name="Zelda.sfc"), "Zelda.sfc", SNES)

        assert set(result) == {"moby_id", "name", "moby_metadata"}

    async def test_of_games_sharing_a_title_the_oldest_wins(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby
        list_games.by_title["Zelda"] = [_game(9, "Zelda"), _game(4, "Zelda")]

        result = await handler.get_rom(Rom(fs_name="Zelda.sfc"), "Zelda.sfc", SNES)

        assert result["moby_id"] == 4

    async def test_a_subtitle_is_searched_alone_when_the_full_title_misses(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby
        list_games.by_title["Link's Awakening"] = [_game(5, "Link's Awakening")]

        result = await handler.get_rom(
            Rom(fs_name="Zelda - Link's Awakening.gb"),
            "Zelda - Link's Awakening.gb",
            SNES,
        )

        assert result["moby_id"] == 5
        assert [c.kwargs["title"] for c in list_games.await_args_list] == [
            "zelda: link's awakening",
            "Link's Awakening",
        ]

    async def test_a_loose_match_is_no_match(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby
        list_games.by_title["Zelda"] = [_game(2, "Something Else Entirely")]

        assert await handler.get_rom(Rom(fs_name="Zelda.sfc"), "Zelda.sfc", SNES) == {
            "moby_id": None
        }

    async def test_a_platform_mobygames_lacks_is_skipped(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby

        assert await handler.get_rom(Rom(fs_name="a.sfc"), "a.sfc", 0) == {
            "moby_id": None
        }
        assert await handler._search_rom("a", 0) is None
        list_games.assert_not_awaited()

    async def test_a_filename_tag_is_looked_up_by_id(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby
        list_games.by_id[7] = [_game(7, "Tagged")]

        result = await handler.get_rom(
            Rom(fs_name="Zelda (moby-7).sfc"), "Zelda (moby-7).sfc", SNES
        )

        assert result["moby_id"] == 7
        assert list_games.await_count == 1

    async def test_an_unknown_filename_tag_falls_back_to_the_title(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby
        list_games.by_title["Zelda"] = [_game(2, "Zelda")]

        result = await handler.get_rom(
            Rom(fs_name="Zelda (moby-7).sfc"), "Zelda (moby-7).sfc", SNES
        )

        assert result["moby_id"] == 2

    async def test_an_arcade_set_is_searched_by_its_mame_title(
        self, moby: tuple[MobyGamesHandler, AsyncMock], monkeypatch: pytest.MonkeyPatch
    ):
        handler, list_games = moby
        monkeypatch.setattr(
            handler, "_mame_format", AsyncMock(return_value="Street Fighter II")
        )
        list_games.by_title["Street Fighter II"] = [_game(3, "Street Fighter II")]

        result = await handler.get_rom(Rom(fs_name="sf2.zip"), "sf2.zip", 143)

        assert result["moby_id"] == 3

    async def test_an_unmatched_arcade_set_keeps_its_mame_title(
        self, moby: tuple[MobyGamesHandler, AsyncMock], monkeypatch: pytest.MonkeyPatch
    ):
        handler, _ = moby
        monkeypatch.setattr(
            handler, "_mame_format", AsyncMock(return_value="Street Fighter II")
        )

        assert await handler.get_rom(Rom(fs_name="sf2.zip"), "sf2.zip", 36) == {
            "moby_id": None,
            "name": "Street Fighter II",
        }

    async def test_a_ps2_opl_name_is_searched_by_its_title(
        self, moby: tuple[MobyGamesHandler, AsyncMock], monkeypatch: pytest.MonkeyPatch
    ):
        handler, _ = moby
        opl = AsyncMock(return_value="Okami")
        monkeypatch.setattr(handler, "_ps2_opl_format", opl)

        result = await handler.get_rom(
            Rom(fs_name="SLUS_215.15.Okami.iso"), "SLUS_215.15.Okami.iso", PS2_MOBY_ID
        )

        assert result == {"moby_id": None, "name": "Okami"}
        opl.assert_awaited_once()

    @pytest.mark.parametrize(
        ("platform", "formatter"),
        [(PS2_MOBY_ID, "_ps2_serial_format"), (PSP_MOBY_ID, "_psp_serial_format")],
        ids=["ps2", "psp"],
    )
    async def test_a_sony_serial_is_searched_by_its_title(
        self,
        moby: tuple[MobyGamesHandler, AsyncMock],
        monkeypatch: pytest.MonkeyPatch,
        platform: int,
        formatter: str,
    ):
        handler, _ = moby
        monkeypatch.setattr(handler, formatter, AsyncMock(return_value="Okami"))

        result = await handler.get_rom(
            Rom(fs_name="SLUS-21515.iso"), "SLUS-21515.iso", platform
        )

        assert result == {"moby_id": None, "name": "Okami"}

    @pytest.mark.parametrize(
        ("fs_name", "formatter"),
        [
            ("Game 70010000000025.nsp", "_switch_titledb_format"),
            ("Game.nsp", "_switch_productid_format"),
        ],
        ids=["title_id", "product_id"],
    )
    async def test_an_unmatched_switch_game_keeps_the_titledb_entry(
        self,
        moby: tuple[MobyGamesHandler, AsyncMock],
        monkeypatch: pytest.MonkeyPatch,
        fs_name: str,
        formatter: str,
    ):
        handler, _ = moby
        entry = {
            "name": "Odyssey",
            "description": "Cappy",
            "iconUrl": "https://icon",
            "screenshots": ["https://shot"],
        }
        no_entry = AsyncMock(side_effect=lambda *a: (a[-1], None))
        monkeypatch.setattr(handler, "_switch_titledb_format", no_entry)
        monkeypatch.setattr(handler, "_switch_productid_format", no_entry)
        monkeypatch.setattr(
            handler, formatter, AsyncMock(return_value=("Odyssey", entry))
        )

        result = await handler.get_rom(Rom(fs_name=fs_name), fs_name, SWITCH_MOBY_ID)

        assert result == {
            "moby_id": None,
            "name": "Odyssey",
            "summary": "Cappy",
            "url_cover": "https://icon",
            "url_screenshots": ["https://shot"],
        }


class TestLookupsById:
    async def test_returns_the_game(self, moby: tuple[MobyGamesHandler, AsyncMock]):
        handler, list_games = moby
        list_games.by_id[7] = [_game(7, "Zelda")]

        result = await handler.get_rom_by_id(7)

        assert result["moby_id"] == 7
        assert result["url_screenshots"] == ["https://moby/7/shot.jpg"]
        assert await handler.get_matched_rom_by_id(7) == result

    async def test_an_unknown_id_is_no_match(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, _ = moby

        assert await handler.get_rom_by_id(7) == {"moby_id": None}
        assert await handler.get_matched_rom_by_id(7) is None


class TestMatchedRomsByName:
    async def test_lists_every_game_found(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby
        list_games.by_title["Zelda"] = [_game(2, "Zelda"), _game(3, "Zelda II")]

        results = await handler.get_matched_roms_by_name("Zelda", SNES)

        assert [(r["moby_id"], r["name"]) for r in results] == [
            (2, "Zelda"),
            (3, "Zelda II"),
        ]

    async def test_without_a_platform_nothing_is_searched(
        self, moby: tuple[MobyGamesHandler, AsyncMock]
    ):
        handler, list_games = moby

        assert await handler.get_matched_roms_by_name("Zelda", None) == []
        list_games.assert_not_awaited()

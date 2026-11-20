"""Earned-achievement join: only unlocked badges that exist on a library ROM."""

from typing import Any

from config import FRONTEND_RESOURCES_PATH
from handler.metadata.earned_achievements import (
    AchievementSource,
    build_achievement_overview,
    build_earned_achievements,
    earned_game_ids,
    ra_art_paths,
    ra_image_icon_url,
)

YUGI_ICON = "/Images/047227.png"
YUGI_ICON_URL = f"https://media.retroachievements.org{YUGI_ICON}"


def _rom(
    rom_id: int,
    ra_id: int,
    achievements: list[dict[str, Any]],
    *,
    name: str = "Super Mario World",
    platform_name: str = "SNES",
) -> AchievementSource:
    return {
        "id": rom_id,
        "name": name,
        "ra_id": ra_id,
        "platform_id": 1,
        "min_age": None,
        "platform_name": platform_name,
        "achievements": achievements,
    }


def _badge(badge_id: str, *, title: str = "First steps", points: int = 5) -> dict:
    return {
        "badge_id": badge_id,
        "title": title,
        "description": "Finish the first level",
        "points": points,
        "badge_url": f"https://media.retroachievements.org/Badge/{badge_id}.png",
        "badge_path": f"roms/1/{badge_id}.png",
        "type": "progression",
    }


def test_an_unlinked_account_is_empty():
    payload = build_earned_achievements(
        ra_username="  ",
        ra_progression={"results": [{"rom_ra_id": 1, "earned_achievements": []}]},
        roms=[],
    )

    assert payload == {"linked": False, "synced": False, "items": []}


def test_a_linked_account_that_never_synced_is_empty():
    payload = build_earned_achievements(
        ra_username="player",
        ra_progression={},
        roms=[],
    )

    assert payload["linked"] is True
    assert payload["synced"] is False
    assert payload["items"] == []


def test_a_sync_with_nothing_earned_stays_empty():
    payload = build_earned_achievements(
        ra_username="player",
        ra_progression={"total": 0, "results": []},
        roms=[],
    )

    assert payload["linked"] is True
    assert payload["synced"] is True
    assert payload["items"] == []


def test_only_earned_badges_are_returned_with_rom_details():
    rom = _rom(
        7,
        42,
        [
            _badge("earned-badge", title="Opened the door", points=10),
            _badge("still-locked", title="Secret", points=25),
        ],
    )
    payload = build_earned_achievements(
        ra_username="player",
        ra_progression={
            "total": 1,
            "results": [
                {
                    "rom_ra_id": 42,
                    "earned_achievements": [
                        {"id": "earned-badge", "date": "2024-03-02 10:00:00"}
                    ],
                }
            ],
        },
        roms=[rom],
    )

    assert payload["synced"] is True
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["id"] == "earned-badge"
    assert item["title"] == "Opened the door"
    assert item["points"] == 10
    assert item["rom_id"] == 7
    assert item["rom_name"] == "Super Mario World"
    assert item["rom_ra_id"] == 42
    assert item["platform_name"] == "SNES"
    assert item["earned_at"] == "2024-03-02 10:00:00"
    assert item["badge_url"].endswith("/earned-badge.png")
    assert item["badge_path"] == f"{FRONTEND_RESOURCES_PATH}/roms/1/earned-badge.png"


def test_a_badge_missing_from_the_catalog_is_skipped():
    payload = build_earned_achievements(
        ra_username="player",
        ra_progression={
            "results": [
                {
                    "rom_ra_id": 42,
                    "earned_achievements": [
                        {"id": "not-in-library", "date": "2024-01-01 00:00:00"}
                    ],
                }
            ]
        },
        roms=[_rom(7, 42, [_badge("other")])],
    )

    assert payload["items"] == []


def test_duplicate_roms_keep_the_lowest_id_that_has_the_badge():
    early = _rom(3, 42, [_badge("badge")], name="USA")
    later = _rom(9, 42, [_badge("badge")], name="Europe")
    payload = build_earned_achievements(
        ra_username="player",
        ra_progression={
            "results": [
                {
                    "rom_ra_id": 42,
                    "earned_achievements": [{"id": "badge", "date": "2020-01-01"}],
                }
            ]
        },
        roms=[later, early],
    )

    assert len(payload["items"]) == 1
    assert payload["items"][0]["rom_id"] == 3
    assert payload["items"][0]["rom_name"] == "USA"


def test_hardcore_date_is_used_when_the_regular_date_is_missing():
    payload = build_earned_achievements(
        ra_username="player",
        ra_progression={
            "results": [
                {
                    "rom_ra_id": 42,
                    "earned_achievements": [
                        {"id": "badge", "date": "", "date_hardcore": "2021-05-05"}
                    ],
                }
            ]
        },
        roms=[_rom(1, 42, [_badge("badge")])],
    )

    assert payload["items"][0]["earned_at"] == "2021-05-05"


def test_overview_includes_locked_badges_and_games_at_zero():
    opened = _badge("earned-badge", title="Opened the door", points=10)
    opened["display_order"] = 1
    opened["badge_path_lock"] = "roms/1/earned-badge_lock.png"
    secret = _badge("still-locked", title="Secret", points=25)
    secret["type"] = "missable"
    secret["display_order"] = 2
    plain = _badge("plain", title="Anything", points=0)
    plain["type"] = ""
    played = dict(_rom(7, 42, [opened, secret, plain], name="Played"))
    played["path_cover_s"] = "covers/played.jpg"
    played["image_icon"] = YUGI_ICON
    played["updated_at"] = "9"
    zero_badge = _badge("zero", title="Nope", points=5)
    zero_badge["type"] = "win_condition"
    zero = _rom(8, 99, [zero_badge], name="Zero", platform_name="GBA")
    empty = _rom(1, 5, [], name="No catalog")

    payload = build_achievement_overview(
        ra_username="player",
        ra_progression={
            "results": [
                {
                    "rom_ra_id": 42,
                    "earned_achievements": [
                        {"id": "earned-badge", "date": "2024-03-02 10:00:00"}
                    ],
                }
            ]
        },
        roms=[empty, zero, played],
    )

    assert [game["name"] for game in payload["games"]] == ["Played", "Zero"]
    played_game = payload["games"][0]
    assert played_game["earned"] == 1
    assert played_game["total"] == 3
    assert played_game["points_earned"] == 10
    assert played_game["points_total"] == 35
    assert played_game["earned_by_type"] == {
        "progression": 1,
        "missable": 0,
        "win_condition": 0,
        "other": 0,
    }
    assert played_game["cover_url"] == YUGI_ICON_URL
    assert payload["games"][1]["cover_url"] is None
    by_id = {item["id"]: item for item in played_game["achievements"]}
    assert by_id["earned-badge"]["earned"] is True
    assert by_id["earned-badge"]["earned_at"] == "2024-03-02 10:00:00"
    assert by_id["earned-badge"]["badge_path_lock"] == (
        f"{FRONTEND_RESOURCES_PATH}/roms/1/earned-badge_lock.png"
    )
    assert by_id["still-locked"]["earned"] is False
    assert by_id["still-locked"]["earned_at"] is None
    assert by_id["plain"]["type"] is None
    assert payload["games"][1]["earned"] == 0
    assert payload["games"][1]["total"] == 1
    assert payload["games"][1]["platform_name"] == "GBA"
    assert payload["earned"] == 1
    assert payload["total"] == 4
    assert payload["points_earned"] == 10
    assert payload["points_total"] == 40
    assert payload["earned_by_type"]["win_condition"] == 0


def test_overview_uses_a_sibling_icon_when_the_catalog_rom_has_none():
    bare = dict(_rom(3, 42, [_badge("a")], name="USA"))
    bare["path_cover_s"] = "covers/usa.jpg"
    bare["image_icon"] = YUGI_ICON
    bare["updated_at"] = "1"
    rich = dict(_rom(9, 42, [_badge("a"), _badge("b")], name="Europe"))
    rich["path_cover_s"] = "covers/europe.jpg"

    payload = build_achievement_overview(
        ra_username="player",
        ra_progression={"total": 0, "results": []},
        roms=[bare, rich],
    )

    assert len(payload["games"]) == 1
    game = payload["games"][0]
    assert game["rom_id"] == 9
    assert game["name"] == "Europe"
    assert game["earned"] == 0
    assert game["total"] == 2
    assert game["cover_url"] == YUGI_ICON_URL


def test_overview_screen_art_uses_the_stored_api_paths():
    rom = dict(
        _rom(24, 11246, [_badge("a")], name="Yu-Gi-Oh! Forbidden Memories")
    )
    rom["image_icon"] = "/Images/027033.png"
    rom["image_title"] = "/Images/026546.png"
    rom["image_ingame"] = "/Images/026547.png"
    rom["image_box_art"] = "/Images/026548.png"

    payload = build_achievement_overview(
        ra_username="player",
        ra_progression={"total": 0, "results": []},
        roms=[rom],
    )

    game = payload["games"][0]
    base = "https://media.retroachievements.org"
    assert game["cover_url"] == f"{base}/Images/027033.png"
    assert game["title_url"] == f"{base}/Images/026546.png"
    assert game["ingame_url"] == f"{base}/Images/026547.png"
    assert game["box_art_url"] == f"{base}/Images/026548.png"
    invented = f"{base}/Images/{11246:06d}.png"
    assert invented not in {
        game["cover_url"],
        game["title_url"],
        game["ingame_url"],
        game["box_art_url"],
    }


def test_overview_background_uses_the_library_cover():
    rom = dict(
        _rom(24, 11246, [_badge("a")], name="Yu-Gi-Oh! Forbidden Memories")
    )
    rom["image_icon"] = "/Images/027033.png"
    rom["path_cover_l"] = "roms/1/24/cover/big.png"
    rom["path_cover_s"] = "roms/1/24/cover/small.png"
    rom["url_cover"] = "https://images.igdb.com/igdb/image/upload/abc.jpg"
    rom["updated_at"] = "9"

    payload = build_achievement_overview(
        ra_username="player",
        ra_progression={"total": 0, "results": []},
        roms=[rom],
    )

    game = payload["games"][0]
    assert game["path_cover_large"] == (
        f"{FRONTEND_RESOURCES_PATH}/roms/1/24/cover/big.png?ts=9"
    )
    assert game["path_cover_small"].endswith("/roms/1/24/cover/small.png?ts=9")
    assert game["url_cover"].startswith("https://images.igdb.com/")
    assert game["cover_url"].endswith("/Images/027033.png")


def test_overview_leaves_missing_screen_art_empty():
    rom = dict(_rom(24, 11246, [_badge("a")]))
    rom["image_icon"] = "/Images/027033.png"

    payload = build_achievement_overview(
        ra_username="player",
        ra_progression={"total": 0, "results": []},
        roms=[rom],
    )

    game = payload["games"][0]
    assert game["title_url"] is None
    assert game["ingame_url"] is None
    assert game["box_art_url"] is None
    assert game["cover_url"] == "https://media.retroachievements.org/Images/027033.png"


def test_overview_uses_a_sibling_screen_when_the_catalog_rom_has_none():
    bare = dict(_rom(3, 42, [_badge("a")], name="USA"))
    bare["image_title"] = "/Images/010001.png"
    bare["image_ingame"] = ""
    bare["image_box_art"] = "/Images/010003.png"
    rich = dict(_rom(9, 42, [_badge("a"), _badge("b")], name="Europe"))

    payload = build_achievement_overview(
        ra_username="player",
        ra_progression={"total": 0, "results": []},
        roms=[bare, rich],
    )

    game = payload["games"][0]
    assert game["rom_id"] == 9
    assert game["title_url"] == "https://media.retroachievements.org/Images/010001.png"
    assert game["ingame_url"] is None
    assert game["box_art_url"] == "https://media.retroachievements.org/Images/010003.png"


def test_art_paths_keep_the_api_path_and_drop_anything_else():
    assert ra_art_paths(None) is None
    assert ra_art_paths(
        {
            "ImageTitle": "https://media.retroachievements.org/Images/026546.png",
            "ImageIngame": "",
            "ImageBoxArt": "/Images/not a path.png",
        }
    ) == {
        "image_title": "/Images/026546.png",
        "image_ingame": "",
        "image_box_art": "",
    }


def test_overview_without_an_icon_does_not_invent_one():
    rom = dict(_rom(7, 42, [_badge("a")]))
    rom["path_cover_s"] = "covers/igdb.jpg"

    payload = build_achievement_overview(
        ra_username="player",
        ra_progression={"total": 0, "results": []},
        roms=[rom],
    )

    assert payload["games"][0]["cover_url"] is None
    assert ra_image_icon_url(42) is None
    assert ra_image_icon_url("/Images/000042.png") == (
        "https://media.retroachievements.org/Images/000042.png"
    )


def test_overview_unlinked_account_has_no_games():
    payload = build_achievement_overview(
        ra_username="  ",
        ra_progression={"results": []},
        roms=[_rom(1, 1, [_badge("a")])],
    )

    assert payload["linked"] is False
    assert payload["synced"] is False
    assert payload["games"] == []
    assert payload["points_earned"] == 0


def test_earned_game_ids_ignore_games_with_no_unlocks():
    assert earned_game_ids(
        {
            "results": [
                {"rom_ra_id": 1, "earned_achievements": []},
                {"rom_ra_id": 2, "earned_achievements": [{"id": "a", "date": "d"}]},
                {"rom_ra_id": 2, "earned_achievements": [{"id": "b", "date": "d"}]},
                {"rom_ra_id": None, "earned_achievements": [{"id": "c", "date": "d"}]},
            ]
        }
    ) == [2]
    assert earned_game_ids(None) == []
    assert earned_game_ids({}) == []

"""Join earned RetroAchievements with the achievement catalog stored on ROMs.

``ra_progression`` only records badge id and date. Title, points and the badge
image live on ``Rom.ra_metadata``, matched the same way as the per-game tab:
``EarnedAchievement.id`` equals ``RAGameRomAchievement.badge_id``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict

from config import FRONTEND_RESOURCES_PATH

# RetroAchievements publishes ImageIcon as a path, not as the game id.
_RA_MEDIA = "https://media.retroachievements.org"
_RA_ICON_PATH = re.compile(r"/Images/[A-Za-z0-9_-]+\.png\Z")
_RA_ICON_HOSTS = (
    "https://media.retroachievements.org",
    "http://media.retroachievements.org",
    "https://retroachievements.org",
    "http://retroachievements.org",
)


class AchievementSource(TypedDict):
    id: int
    name: str
    ra_id: int
    platform_id: int
    min_age: int | None
    platform_name: str | None
    achievements: list[dict[str, Any]]


class EarnedAchievementItem(TypedDict):
    id: str
    title: str | None
    description: str | None
    points: int | None
    badge_url: str | None
    badge_path: str | None
    type: str | None
    earned_at: str | None
    rom_id: int
    rom_name: str
    rom_ra_id: int
    platform_name: str | None


class EarnedAchievementsPayload(TypedDict):
    linked: bool
    synced: bool
    items: list[EarnedAchievementItem]


class AchievementTypeCounts(TypedDict):
    progression: int
    missable: int
    win_condition: int
    other: int


class CatalogAchievement(TypedDict):
    id: str
    title: str | None
    description: str | None
    points: int | None
    badge_url: str | None
    badge_path: str | None
    badge_url_lock: str | None
    badge_path_lock: str | None
    type: str | None
    display_order: int | None
    earned: bool
    earned_at: str | None


class AchievementGame(TypedDict):
    rom_id: int
    name: str
    platform_name: str | None
    platform_slug: str | None
    platform_fs_slug: str | None
    cover_url: str | None
    path_cover_large: str | None
    path_cover_small: str | None
    url_cover: str | None
    title_url: str | None
    ingame_url: str | None
    box_art_url: str | None
    earned: int
    total: int
    points_earned: int
    points_total: int
    earned_by_type: AchievementTypeCounts
    achievements: list[CatalogAchievement]


class AchievementOverview(TypedDict):
    linked: bool
    synced: bool
    earned: int
    total: int
    points_earned: int
    points_total: int
    earned_by_type: AchievementTypeCounts
    games: list[AchievementGame]


def earned_game_ids(ra_progression: dict[str, Any] | None) -> list[int]:
    """RetroAchievements game ids that have at least one earned achievement."""
    if not isinstance(ra_progression, dict):
        return []
    results = ra_progression.get("results")
    if not isinstance(results, list):
        return []

    ids: list[int] = []
    for game in results:
        if not isinstance(game, dict):
            continue
        ra_id = game.get("rom_ra_id")
        earned = game.get("earned_achievements")
        if isinstance(ra_id, int) and isinstance(earned, list) and earned:
            ids.append(ra_id)
    return list(dict.fromkeys(ids))


def build_earned_achievements(
    *,
    ra_username: str | None,
    ra_progression: dict[str, Any] | None,
    roms: Sequence[Mapping[str, Any]],
) -> EarnedAchievementsPayload:
    """Earned achievements that match a library ROM.

    An account with no RetroAchievements username, or one that has never
    synced, comes back with an empty list and the matching flags. Nothing
    here is invented: a badge with no catalog entry is left out.
    """
    if not (ra_username or "").strip():
        return {"linked": False, "synced": False, "items": []}

    progression = ra_progression if isinstance(ra_progression, dict) else None
    synced = progression is not None and "results" in progression
    if not synced or progression is None:
        return {"linked": True, "synced": False, "items": []}

    by_game = _roms_by_game(roms)
    items: list[EarnedAchievementItem] = []
    seen: set[tuple[int, str]] = set()
    results = progression.get("results")
    if not isinstance(results, list):
        results = []

    for game in results:
        if not isinstance(game, dict):
            continue
        rom_ra_id = game.get("rom_ra_id")
        earned = game.get("earned_achievements")
        if not isinstance(rom_ra_id, int) or not isinstance(earned, list):
            continue
        for entry in earned:
            if not isinstance(entry, dict):
                continue
            badge_id = _text(entry.get("id"))
            if badge_id is None or (rom_ra_id, badge_id) in seen:
                continue
            match = _match(by_game.get(rom_ra_id, []), badge_id)
            if match is None:
                continue
            rom, achievement = match
            seen.add((rom_ra_id, badge_id))
            items.append(
                {
                    "id": badge_id,
                    "title": _text(achievement.get("title")),
                    "description": _text(achievement.get("description")),
                    "points": _points(achievement.get("points")),
                    "badge_url": _text(achievement.get("badge_url")),
                    "badge_path": _public_badge_path(achievement.get("badge_path")),
                    "type": _text(achievement.get("type")),
                    "earned_at": _earned_at(entry),
                    "rom_id": rom["id"],
                    "rom_name": rom["name"],
                    "rom_ra_id": rom_ra_id,
                    "platform_name": rom.get("platform_name"),
                }
            )

    items.sort(key=lambda item: item["earned_at"] or "", reverse=True)
    return {"linked": True, "synced": True, "items": items}


def _roms_by_game(
    roms: Sequence[Mapping[str, Any]],
) -> dict[int, list[Mapping[str, Any]]]:
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for rom in roms:
        ra_id = rom.get("ra_id")
        if isinstance(ra_id, int):
            grouped.setdefault(ra_id, []).append(rom)
    for group in grouped.values():
        group.sort(key=lambda rom: rom["id"])
    return grouped


def _match(
    roms: Sequence[Mapping[str, Any]], badge_id: str
) -> tuple[Mapping[str, Any], dict[str, Any]] | None:
    """Lowest ROM id whose catalog contains this badge."""
    for rom in roms:
        achievements = rom.get("achievements")
        if not isinstance(achievements, list):
            continue
        for achievement in achievements:
            if (
                isinstance(achievement, dict)
                and _text(achievement.get("badge_id")) == badge_id
            ):
                return rom, achievement
    return None


def _earned_at(entry: dict[str, Any]) -> str | None:
    for key in ("date", "date_hardcore"):
        value = _text(entry.get(key))
        if value:
            return value
    return None


def _points(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text(value: object) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _public_badge_path(value: object) -> str | None:
    path = _text(value)
    if path is None:
        return None
    if path.startswith(("http://", "https://", "/")):
        return path
    return f"{FRONTEND_RESOURCES_PATH}/{path}"


def _empty_counts() -> AchievementTypeCounts:
    return {"progression": 0, "missable": 0, "win_condition": 0, "other": 0}


def _empty_overview(*, linked: bool, synced: bool) -> AchievementOverview:
    return {
        "linked": linked,
        "synced": synced,
        "earned": 0,
        "total": 0,
        "points_earned": 0,
        "points_total": 0,
        "earned_by_type": _empty_counts(),
        "games": [],
    }


def _type_bucket(
    value: str | None,
) -> Literal["progression", "missable", "win_condition", "other"]:
    if value == "progression":
        return "progression"
    if value == "missable":
        return "missable"
    if value == "win_condition":
        return "win_condition"
    return "other"


def _add_counts(total: AchievementTypeCounts, extra: AchievementTypeCounts) -> None:
    total["progression"] += extra["progression"]
    total["missable"] += extra["missable"]
    total["win_condition"] += extra["win_condition"]
    total["other"] += extra["other"]


def ra_image_icon_path(value: object) -> str | None:
    """RetroAchievements ``ImageIcon`` path, such as ``/Images/047227.png``.

    The game id is not the filename. A missing or unfamiliar value stays empty
    so the list can show a neutral box instead of another game's art.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for host in _RA_ICON_HOSTS:
        if text.startswith(host):
            text = text[len(host) :]
            break
    else:
        if text.startswith(("http://", "https://")):
            return None
    text = text.split("?", 1)[0].split("#", 1)[0]
    if not text.startswith("/"):
        text = f"/{text}"
    if _RA_ICON_PATH.fullmatch(text) is None:
        return None
    return text


def ra_image_icon_url(value: object) -> str | None:
    """Absolute media URL for a stored RetroAchievements image path."""
    path = ra_image_icon_path(value)
    if path is None:
        return None
    return f"{_RA_MEDIA}{path}"


# Title screen, in-game shot and box art. Same path shape as ImageIcon.
RA_ART_KEYS = ("image_title", "image_ingame", "image_box_art")
_RA_ART_FIELDS = {
    "image_title": "ImageTitle",
    "image_ingame": "ImageIngame",
    "image_box_art": "ImageBoxArt",
}


def ra_art_paths(details: Mapping[str, Any] | None) -> dict[str, str] | None:
    """Paths for ``ImageTitle``, ``ImageIngame`` and ``ImageBoxArt``.

    A reply from RetroAchievements has all three keys. An image the game
    does not publish is an empty string, so the next read does not ask
    again. A failed request is None. The filename is the path in the reply.
    """
    if not isinstance(details, dict):
        return None
    paths: dict[str, str] = {}
    for key, field in _RA_ART_FIELDS.items():
        paths[key] = ra_image_icon_path(details.get(field)) or ""
    return paths


def stored_ra_art(source: Mapping[str, Any]) -> dict[str, str] | None:
    """The three art paths when this ROM was already asked, else None."""
    record: dict[str, str] = {}
    for key in RA_ART_KEYS:
        value = source.get(key)
        if not isinstance(value, str):
            return None
        if value == "":
            record[key] = ""
            continue
        path = ra_image_icon_path(value)
        if path is None:
            return None
        record[key] = path
    return record


def _stored_media_url(roms: Sequence[Mapping[str, Any]], key: str) -> str | None:
    """First stored RetroAchievements image in the group."""
    for rom in roms:
        url = ra_image_icon_url(rom.get(key))
        if url:
            return url
    return None


def _stored_icon_url(roms: Sequence[Mapping[str, Any]]) -> str | None:
    """First stored ImageIcon in the group. Never the library cover."""
    return _stored_media_url(roms, "image_icon")


def _library_cover(path: object, updated_at: object) -> str | None:
    """Public cover path, the same shape ``Rom.path_cover_large`` builds."""
    text = _text(path)
    if text is None:
        return None
    if text.startswith(("http://", "https://", "/")):
        return text
    stamp = "" if updated_at is None else str(updated_at)
    return f"{FRONTEND_RESOURCES_PATH}/{text}?ts={stamp}"


def _group_covers(
    roms: Sequence[Mapping[str, Any]],
) -> tuple[str | None, str | None, str | None]:
    """Large cover, small cover and remote cover for the first ROM that has one.

    The open game prefers its own files. A sibling supplies them only when
    the catalog ROM has none, so the backdrop still has art.
    """
    for rom in roms:
        large = _library_cover(rom.get("path_cover_l"), rom.get("updated_at"))
        small = _library_cover(rom.get("path_cover_s"), rom.get("updated_at"))
        remote = _text(rom.get("url_cover"))
        if large or small or remote:
            return large, small, remote
    return None, None, None


def _earned_index(
    ra_progression: dict[str, Any] | None,
) -> dict[int, dict[str, str | None]]:
    """badge id -> earned date, per RetroAchievements game id."""
    indexed: dict[int, dict[str, str | None]] = {}
    if not isinstance(ra_progression, dict):
        return indexed
    results = ra_progression.get("results")
    if not isinstance(results, list):
        return indexed
    for game in results:
        if not isinstance(game, dict):
            continue
        rom_ra_id = game.get("rom_ra_id")
        earned = game.get("earned_achievements")
        if not isinstance(rom_ra_id, int) or not isinstance(earned, list):
            continue
        bucket = indexed.setdefault(rom_ra_id, {})
        for entry in earned:
            if not isinstance(entry, dict):
                continue
            badge_id = _text(entry.get("id"))
            if badge_id is None or badge_id in bucket:
                continue
            bucket[badge_id] = _earned_at(entry)
    return indexed


def _catalog_size(rom: Mapping[str, Any]) -> int:
    achievements = rom.get("achievements")
    if not isinstance(achievements, list):
        return 0
    return sum(
        1
        for achievement in achievements
        if isinstance(achievement, dict) and _text(achievement.get("badge_id"))
    )


def _completion_rank(earned: int, total: int) -> int:
    """Sort key only. The same rounding the page uses for the big percent."""
    if total <= 0 or earned <= 0:
        return 0
    if earned >= total:
        return 100
    return (earned * 100 + total // 2) // total


def build_achievement_overview(
    *,
    ra_username: str | None,
    ra_progression: dict[str, Any] | None,
    roms: Sequence[Mapping[str, Any]],
) -> AchievementOverview:
    """One row per library game that has a RetroAchievements catalog.

    Games with nothing earned stay in the list at 0%. Locked badges are the
    catalog entries missing from the sync. Counts are that join: no rarity
    tiers and no points that the catalog does not store.
    """
    if not (ra_username or "").strip():
        return _empty_overview(linked=False, synced=False)

    progression = ra_progression if isinstance(ra_progression, dict) else None
    synced = progression is not None and "results" in progression
    if not synced or progression is None:
        return _empty_overview(linked=True, synced=False)

    earned_by_game = _earned_index(progression)
    grouped = _roms_by_game(roms)
    games: list[AchievementGame] = []
    summary_counts = _empty_counts()
    summary_earned = 0
    summary_total = 0
    summary_points_earned = 0
    summary_points_total = 0

    for rom_ra_id, group in grouped.items():
        catalog = max(group, key=lambda rom: (_catalog_size(rom), -rom["id"]))
        if _catalog_size(catalog) == 0:
            continue
        earned_map = earned_by_game.get(rom_ra_id, {})
        achievements = catalog.get("achievements")
        if not isinstance(achievements, list):
            continue

        items: list[CatalogAchievement] = []
        counts = _empty_counts()
        seen: set[str] = set()
        earned_n = 0
        points_earned = 0
        points_total = 0
        for achievement in achievements:
            if not isinstance(achievement, dict):
                continue
            badge_id = _text(achievement.get("badge_id"))
            if badge_id is None or badge_id in seen:
                continue
            seen.add(badge_id)
            points = _points(achievement.get("points"))
            if points is not None:
                points_total += points
            earned = badge_id in earned_map
            bucket = _type_bucket(_text(achievement.get("type")))
            if earned:
                earned_n += 1
                counts[bucket] += 1
                if points is not None:
                    points_earned += points
            items.append(
                {
                    "id": badge_id,
                    "title": _text(achievement.get("title")),
                    "description": _text(achievement.get("description")),
                    "points": points,
                    "badge_url": _text(achievement.get("badge_url")),
                    "badge_path": _public_badge_path(achievement.get("badge_path")),
                    "badge_url_lock": _text(achievement.get("badge_url_lock")),
                    "badge_path_lock": _public_badge_path(
                        achievement.get("badge_path_lock")
                    ),
                    "type": _text(achievement.get("type")),
                    "display_order": _points(achievement.get("display_order")),
                    "earned": earned,
                    "earned_at": earned_map.get(badge_id) if earned else None,
                }
            )
        if not items:
            continue

        cover_large, cover_small, cover_remote = _group_covers((catalog, *group))
        games.append(
            {
                "rom_id": catalog["id"],
                "name": catalog["name"],
                "platform_name": catalog.get("platform_name"),
                "platform_slug": _text(catalog.get("platform_slug")),
                "platform_fs_slug": _text(catalog.get("platform_fs_slug")),
                "cover_url": _stored_icon_url((catalog, *group)),
                "path_cover_large": cover_large,
                "path_cover_small": cover_small,
                "url_cover": cover_remote,
                "title_url": _stored_media_url((catalog, *group), "image_title"),
                "ingame_url": _stored_media_url((catalog, *group), "image_ingame"),
                "box_art_url": _stored_media_url((catalog, *group), "image_box_art"),
                "earned": earned_n,
                "total": len(items),
                "points_earned": points_earned,
                "points_total": points_total,
                "earned_by_type": counts,
                "achievements": items,
            }
        )
        summary_earned += earned_n
        summary_total += len(items)
        summary_points_earned += points_earned
        summary_points_total += points_total
        _add_counts(summary_counts, counts)

    games.sort(
        key=lambda game: (
            -_completion_rank(game["earned"], game["total"]),
            -game["points_earned"],
            game["name"].casefold(),
        )
    )
    return {
        "linked": True,
        "synced": True,
        "earned": summary_earned,
        "total": summary_total,
        "points_earned": summary_points_earned,
        "points_total": summary_points_total,
        "earned_by_type": summary_counts,
        "games": games,
    }

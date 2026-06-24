#!/usr/bin/env python3
"""Generate a large, prod-like RomM library for load and UI testing.

Builds platforms, users, devices, firmware, roms (with per-provider fake
metadata), rom files, saves, states, screenshots, notes, play stats,
collections and sync data, then bulk-inserts everything.

Run from the backend directory:

    uv run tools/generate_test_data.py --roms 100000

The script talks straight to the database configured by the usual env vars
(DB_HOST, DB_NAME, ...). It assigns primary keys explicitly so foreign keys
can be wired without round-trips, which keeps it fast at six-figure scale.
This is a TEST tool: point it at a throwaway/dev database, not production.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

# Allow running as `python3 tools/generate_test_data.py` from backend/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# isort: off
# Import order matters here: the metadata package must load before
# `adapters.services.igdb` so the base_handler <-> igdb import cycle resolves
# (igdb must not be the entrypoint). Keep isort from reordering these.
from handler.metadata.base_handler import (  # noqa: E402,F401
    UniversalPlatformSlug as UPS,
)
from adapters.services.igdb import IGDB_PLATFORM_LIST  # noqa: E402

# isort: on
from PIL import Image  # noqa: E402

from config import RESOURCES_BASE_PATH  # noqa: E402
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST  # noqa: E402
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST  # noqa: E402
from models.assets import Save, Screenshot, State  # noqa: E402
from models.base import compute_file_name_parts  # noqa: E402
from models.client_token import ClientToken  # noqa: E402
from models.collection import (  # noqa: E402
    Collection,
    CollectionRom,
    SmartCollection,
)
from models.device import Device, SyncMode  # noqa: E402
from models.device_save_sync import DeviceSaveSync  # noqa: E402
from models.firmware import Firmware  # noqa: E402
from models.platform import Platform  # noqa: E402
from models.play_session import PlaySession  # noqa: E402

# NOTE: `roms_metadata` and `sibling_roms` are DB VIEWS, not tables: the
# aggregated metadata and sibling links are derived from each rom's provider
# columns, so we populate those columns instead of inserting into the views.
from models.rom import (  # noqa: E402
    Rom,
    RomFile,
    RomFileCategory,
    RomNote,
    RomUser,
    RomUserStatus,
    compute_name_sort_key,
)
from models.sync_session import SyncSession, SyncSessionStatus  # noqa: E402
from models.user import Role, User  # noqa: E402

# ---------------------------------------------------------------------------
# Static data pools used to fabricate believable metadata.
# ---------------------------------------------------------------------------

TITLE_PREFIXES = [
    "Super",
    "Legend of",
    "Final",
    "Dark",
    "Cosmic",
    "Shadow",
    "Eternal",
    "Ultimate",
    "Mega",
    "Hyper",
    "Galactic",
    "Mystic",
    "Crimson",
    "Golden",
    "Silent",
    "Savage",
    "Phantom",
    "Turbo",
    "Neo",
    "Quantum",
    "Astral",
    "Iron",
    "Blazing",
    "Frozen",
    "Twilight",
    "Radiant",
    "Rogue",
    "Sacred",
]

TITLE_NOUNS = [
    "Quest",
    "Warriors",
    "Racing",
    "Fantasy",
    "Kingdom",
    "Empire",
    "Galaxy",
    "Dungeon",
    "Chronicles",
    "Legends",
    "Saga",
    "Adventure",
    "Heroes",
    "Force",
    "Strike",
    "Tactics",
    "Odyssey",
    "Realm",
    "Wars",
    "Brigade",
    "Hunters",
    "Conquest",
    "Frontier",
    "Eclipse",
    "Horizon",
    "Rampage",
    "Circuit",
    "Nightmare",
    "Paradise",
    "Inferno",
    "Crusade",
    "Arena",
    "Drifters",
]

TITLE_SUBTITLES = [
    "The Awakening",
    "Reborn",
    "Final Strike",
    "Lost Worlds",
    "New Dawn",
    "Bloodlines",
    "Revolution",
    "The Last Stand",
    "Ascension",
    "Origins",
    "Vengeance",
    "Eternal Night",
    "Broken Seal",
    "Rising Sun",
    "Cold War",
    "The Reckoning",
    "Shattered Dreams",
    "Wild Hunt",
    "Iron Throne",
]

SEQUEL_TAGS = ["", "", "", "II", "III", "IV", "2", "3", "64", "Advance", "DX"]

GENRES = [
    "Action",
    "Adventure",
    "Role-playing (RPG)",
    "Shooter",
    "Platform",
    "Puzzle",
    "Racing",
    "Sport",
    "Strategy",
    "Fighting",
    "Simulator",
    "Arcade",
    "Indie",
    "Hack and slash/Beat 'em up",
    "Music",
    "Pinball",
    "Point-and-click",
    "Real Time Strategy (RTS)",
    "Tactical",
    "Card & Board Game",
]

COMPANIES = [
    "Nintendo",
    "Sega",
    "Capcom",
    "Konami",
    "Square Enix",
    "Bandai Namco",
    "Atari",
    "Sony Interactive Entertainment",
    "Electronic Arts",
    "Ubisoft",
    "Activision",
    "SNK",
    "Taito",
    "Hudson Soft",
    "Rare",
    "Naughty Dog",
    "Treasure",
    "Technos",
    "Irem",
    "Tecmo",
    "Data East",
    "Midway",
]

FRANCHISES = [
    "Super Mario",
    "The Legend of Zelda",
    "Final Fantasy",
    "Sonic the Hedgehog",
    "Mega Man",
    "Castlevania",
    "Metroid",
    "Street Fighter",
    "Dragon Quest",
    "Metal Gear",
    "Resident Evil",
    "Gran Turismo",
    "Tekken",
    "Contra",
    "Kirby",
    "Donkey Kong",
    "Fire Emblem",
    "Pokemon",
    "Bomberman",
]

GAME_MODES = [
    "Single player",
    "Multiplayer",
    "Co-operative",
    "Split screen",
    "Massively Multiplayer Online (MMO)",
    "Battle Royale",
]

AGE_RATINGS = [
    "ESRB:E",
    "ESRB:T",
    "ESRB:M",
    "PEGI:7",
    "PEGI:12",
    "PEGI:16",
    "PEGI:18",
    "CERO:A",
    "CERO:B",
    "CERO:C",
]

REGIONS = ["USA", "Europe", "Japan", "World", "Asia", "Korea", "Australia", "Brazil"]

LANGUAGES = ["en", "ja", "fr", "de", "es", "it", "pt", "nl", "ko", "zh"]

EMULATORS = [
    "retroarch",
    "mednafen",
    "mame",
    "snes9x",
    "mupen64plus",
    "pcsx2",
    "ppsspp",
    "dolphin",
    "mgba",
    "desmume",
    "duckstation",
    "flycast",
    "melonds",
]

DEVICE_CLIENTS = [
    ("Web", "web", "1.0.0"),
    ("muOS", "grout", "2.3.1"),
    ("Android", "argosy-launcher", "0.9.4"),
    ("Steam Deck", "emudeck", "2.1.0"),
    ("ROCKNIX", "knulli-sync", "1.4.2"),
]

SAVE_EXTENSIONS = ["srm", "sav", "state", "mcr", "ldci"]
STATE_EXTENSIONS = ["state", "ss0", "ss1", "auto"]

# A handful of well-known slug -> rom extension maps; everything else falls
# back to a generic pool weighted toward the platform's storage medium.
EXTENSIONS_BY_SLUG: dict[str, list[str]] = {
    "n64": ["z64", "n64", "v64"],
    "snes": ["sfc", "smc"],
    "nes": ["nes"],
    "gb": ["gb"],
    "gbc": ["gbc"],
    "gba": ["gba"],
    "nds": ["nds"],
    "3ds": ["3ds", "cia"],
    "genesis-slash-megadrive": ["md", "bin", "gen"],
    "sega-master-system-mark-iii": ["sms"],
    "gamegear": ["gg"],
    "psx": ["chd", "cue", "bin"],
    "ps2": ["chd", "iso"],
    "psp": ["iso", "cso"],
    "dc": ["chd", "gdi", "cdi"],
    "saturn": ["chd", "cue", "bin"],
    "segacd": ["chd", "cue", "bin"],
    "ngc": ["rvz", "iso"],
    "wii": ["rvz", "wbfs"],
    "arcade": ["zip"],
    "neogeoaes": ["zip"],
}

DISC_HINTS = ("ps", "dc", "saturn", "cd", "ngc", "wii", "psp", "3do", "cdi")


# ---------------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------------


def rand_hex(rng: random.Random, nbytes: int) -> str:
    return "%0*x" % (nbytes * 2, rng.getrandbits(nbytes * 8))


# Cover/screenshot output dimensions (px) and their low-res mosaic block grid.
# A few random blocks upscaled with NEAREST give a unique, abstract image per
# rom that PNG compresses to ~1-2 KB; this is the fastest believable artwork.
COVER_BIG = ((264, 396), (6, 9))
COVER_SMALL = ((132, 198), (4, 6))
SCREENSHOT = ((320, 240), (8, 6))


def _write_mosaic(rng: random.Random, path: str, spec: tuple) -> None:
    (w, h), (bw, bh) = spec
    buf = bytes(rng.getrandbits(8) for _ in range(bw * bh * 3))
    img = Image.frombytes("RGB", (bw, bh), buf).resize((w, h), Image.Resampling.NEAREST)
    img.save(path, "PNG")


def generate_rom_images(
    rng: random.Random, resources_base: str, platform_id: int, rom_id: int, n_shots: int
) -> tuple[str, str, list[str]]:
    """Write mosaic PNG covers (+screenshots) and return their resource-relative
    paths, matching RomM's roms/{platform_id}/{rom_id} layout."""
    rel = f"roms/{platform_id}/{rom_id}"
    cover_dir = os.path.join(resources_base, rel, "cover")
    os.makedirs(cover_dir, exist_ok=True)
    _write_mosaic(rng, os.path.join(cover_dir, "big.png"), COVER_BIG)
    _write_mosaic(rng, os.path.join(cover_dir, "small.png"), COVER_SMALL)

    shot_paths: list[str] = []
    if n_shots:
        shot_dir = os.path.join(resources_base, rel, "screenshots")
        os.makedirs(shot_dir, exist_ok=True)
        for i in range(n_shots):
            _write_mosaic(rng, os.path.join(shot_dir, f"{i}.png"), SCREENSHOT)
            shot_paths.append(f"{rel}/screenshots/{i}.png")

    return f"{rel}/cover/small.png", f"{rel}/cover/big.png", shot_paths


def slugify(value: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in value)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:380]


class Ids:
    """Hands out monotonically increasing integer primary keys per table."""

    def __init__(self, start: dict[str, int]):
        self._next = dict(start)

    def take(self, table: str, count: int = 1) -> int:
        first = self._next[table]
        self._next[table] = first + count
        return first


# ---------------------------------------------------------------------------
# Platform pool.
# ---------------------------------------------------------------------------


def build_platform_pool() -> list[dict[str, Any]]:
    """Real platform definitions joined across IGDB/Moby/ScreenScraper."""
    pool: list[dict[str, Any]] = []
    for ups, igdb in IGDB_PLATFORM_LIST.items():
        moby = MOBYGAMES_PLATFORM_LIST.get(ups)
        ss = SCREENSAVER_PLATFORM_LIST.get(ups)
        slug = igdb["slug"]
        pool.append(
            {
                "ups": ups,
                "slug": slug,
                "name": igdb["name"],
                "category": igdb.get("category") or "",
                "generation": igdb.get("generation"),
                "family_name": igdb.get("family_name") or "",
                "family_slug": igdb.get("family_slug") or "",
                "url": igdb.get("url") or "",
                "url_logo": igdb.get("url_logo") or "",
                "igdb_id": igdb.get("id"),
                "moby_id": moby.get("id") if moby else None,
                "ss_id": ss.get("id") if ss else None,
                "extensions": EXTENSIONS_BY_SLUG.get(
                    slug,
                    (
                        ["chd", "iso", "cue"]
                        if any(h in slug for h in DISC_HINTS)
                        else ["zip", "bin", "rom"]
                    ),
                ),
            }
        )
    return pool


# ---------------------------------------------------------------------------
# Per-game "facts" and provider metadata builders.
# ---------------------------------------------------------------------------


def make_title(rng: random.Random) -> str:
    title = f"{rng.choice(TITLE_PREFIXES)} {rng.choice(TITLE_NOUNS)}"
    if rng.random() < 0.45:
        title += f": {rng.choice(TITLE_SUBTITLES)}"
    seq = rng.choice(SEQUEL_TAGS)
    if seq:
        title += f" {seq}"
    return title[:300]


def make_facts(rng: random.Random, platform: dict[str, Any]) -> dict[str, Any]:
    title = make_title(rng)
    year = rng.randint(1983, 2024)
    release_dt = datetime(
        year, rng.randint(1, 12), rng.randint(1, 28), tzinfo=timezone.utc
    )
    genres = rng.sample(GENRES, k=rng.randint(1, 3))
    companies = rng.sample(COMPANIES, k=rng.randint(1, 2))
    modes = rng.sample(GAME_MODES, k=rng.randint(1, 2))
    franchise = rng.choice(FRANCHISES) if rng.random() < 0.35 else None
    max_players = rng.choice([1, 1, 1, 2, 2, 4, 8])
    player_count = "1" if max_players == 1 else f"1-{max_players}"
    region = rng.choice(REGIONS)
    revision = f"Rev {rng.randint(1, 3)}" if rng.random() < 0.2 else None

    return {
        "title": title,
        "slug": slugify(title),
        "summary": (
            f"{title} is a {genres[0].lower()} game"
            + (f" in the {franchise} franchise" if franchise else "")
            + f", released in {year} by {companies[0]}."
        ),
        "year": year,
        "release_ts": int(release_dt.timestamp()),
        "genres": genres,
        "companies": companies,
        "game_modes": modes,
        "franchises": [franchise] if franchise else [],
        "age_ratings": rng.sample(AGE_RATINGS, k=rng.randint(1, 2)),
        "max_players": max_players,
        "player_count": player_count,
        "rating": round(rng.uniform(40, 98), 2),
        "region": region,
        "revision": revision,
        "languages": rng.sample(LANGUAGES, k=rng.randint(1, 4)),
    }


def _cover_url(rng: random.Random) -> str:
    return (
        f"https://images.igdb.com/igdb/image/upload/t_cover_big/{rand_hex(rng, 6)}.jpg"
    )


def build_igdb_metadata(rng: random.Random, f: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_rating": str(f["rating"]),
        "aggregated_rating": str(round(f["rating"] - rng.uniform(0, 8), 2)),
        "first_release_date": f["release_ts"],
        "youtube_video_id": rand_hex(rng, 6),
        "genres": f["genres"],
        "franchises": f["franchises"],
        "alternative_names": [f["title"].split(":")[0]],
        "collections": [f["franchises"][0]] if f["franchises"] else [],
        "companies": f["companies"],
        "game_modes": f["game_modes"],
        "age_ratings": [
            {
                "rating": r.split(":")[1],
                "category": r.split(":")[0],
                "rating_cover_url": "",
            }
            for r in f["age_ratings"]
        ],
        "platforms": [],
        "multiplayer_modes": [],
        "player_count": f["player_count"],
        "expansions": [],
        "dlcs": [],
        "remasters": [],
        "remakes": [],
        "expanded_games": [],
        "ports": [],
        "similar_games": [
            {
                "id": rng.randint(1, 300000),
                "name": make_title(rng),
                "slug": slugify(make_title(rng)),
                "type": "similar",
                "cover_url": _cover_url(rng),
            }
            for _ in range(rng.randint(0, 4))
        ],
    }


def build_moby_metadata(
    rng: random.Random, f: dict[str, Any], platform: dict[str, Any]
) -> dict[str, Any]:
    return {
        "moby_score": str(round(f["rating"] / 10, 1)),
        "genres": f["genres"],
        "alternate_titles": [f["title"].split(":")[0]],
        "platforms": (
            [{"moby_id": platform["moby_id"], "name": platform["name"]}]
            if platform.get("moby_id")
            else []
        ),
    }


def build_ss_metadata(rng: random.Random, f: dict[str, Any]) -> dict[str, Any]:
    return {
        "ss_score": str(round(f["rating"] / 10, 1)),
        "first_release_date": f["release_ts"],
        "alternative_names": [f["title"].split(":")[0]],
        "age_ratings": [
            {"rating": r.split(":")[1], "category": r.split(":")[0]}
            for r in f["age_ratings"]
        ],
        "companies": f["companies"],
        "franchises": f["franchises"],
        "game_modes": f["game_modes"],
        "genres": f["genres"],
        "player_count": f["player_count"],
        "box2d_url": f"https://www.screenscraper.fr/image.php?gameid={rng.randint(1, 999999)}",
        "screenshot_url": f"https://www.screenscraper.fr/image.php?gameid={rng.randint(1, 999999)}",
    }


def build_ra_metadata(rng: random.Random, f: dict[str, Any]) -> dict[str, Any]:
    n = rng.randint(0, 12)
    achievements = []
    for i in range(n):
        badge = str(rng.randint(10000, 99999))
        achievements.append(
            {
                "ra_id": rng.randint(1, 500000),
                "title": f"{rng.choice(['First', 'Master', 'Hidden', 'Speed', 'No Damage'])} {rng.choice(['Blood', 'Run', 'Clear', 'Strike', 'Trophy'])}",
                "description": "Complete a hidden in-game objective.",
                "points": rng.choice([1, 2, 3, 5, 10, 25, 50, 100]),
                "num_awarded": rng.randint(0, 50000),
                "num_awarded_hardcore": rng.randint(0, 10000),
                "badge_id": badge,
                "badge_url_lock": f"https://media.retroachievements.org/Badge/{badge}_lock.png",
                "badge_path_lock": "",
                "badge_url": f"https://media.retroachievements.org/Badge/{badge}.png",
                "badge_path": "",
                "display_order": i,
                "type": rng.choice(["progression", "win_condition", "missable", ""]),
            }
        )
    return {
        "first_release_date": f["release_ts"],
        "genres": f["genres"][:1],
        "companies": f["companies"],
        "achievements": achievements,
    }


def build_launchbox_metadata(rng: random.Random, f: dict[str, Any]) -> dict[str, Any]:
    return {
        "first_release_date": f["release_ts"],
        "max_players": f["max_players"],
        "release_type": "Released",
        "cooperative": f["max_players"] > 1 and rng.random() < 0.5,
        "youtube_video_id": rand_hex(rng, 6),
        "community_rating": round(f["rating"] / 10, 1),
        "community_rating_count": rng.randint(0, 5000),
        "wikipedia_url": f"https://en.wikipedia.org/wiki/{f['slug'].replace('-', '_')}",
        "esrb": f["age_ratings"][0].split(":")[1] if f["age_ratings"] else "",
        "genres": f["genres"],
        "companies": f["companies"],
        "images": [
            {"url": _cover_url(rng), "type": "Box - Front", "region": f["region"]}
        ],
    }


def build_hasheous_metadata(rng: random.Random) -> dict[str, Any]:
    return {
        "tosec_match": rng.random() < 0.3,
        "mame_arcade_match": rng.random() < 0.1,
        "mame_mess_match": rng.random() < 0.1,
        "nointro_match": rng.random() < 0.6,
        "redump_match": rng.random() < 0.4,
        "whdload_match": False,
        "ra_match": rng.random() < 0.3,
        "fbneo_match": rng.random() < 0.1,
        "puredos_match": False,
    }


def build_hltb_metadata(rng: random.Random, f: dict[str, Any]) -> dict[str, Any]:
    base = rng.randint(2, 60) * 3600
    return {
        "main_story": base,
        "main_story_count": rng.randint(10, 8000),
        "main_plus_extra": int(base * 1.5),
        "main_plus_extra_count": rng.randint(10, 5000),
        "completionist": int(base * 2.5),
        "completionist_count": rng.randint(5, 3000),
        "all_styles": int(base * 1.7),
        "all_styles_count": rng.randint(20, 10000),
        "release_year": f["year"],
        "review_score": int(f["rating"]),
        "review_count": rng.randint(0, 2000),
    }


def build_flashpoint_metadata(rng: random.Random, f: dict[str, Any]) -> dict[str, Any]:
    return {
        "franchises": f["franchises"],
        "companies": f["companies"],
        "source": None,
        "genres": f["genres"],
        "first_release_date": str(f["release_ts"]),
        "game_modes": f["game_modes"],
        "status": rng.choice(["Playable", "Partial", "Hacked"]),
        "version": "1.0",
        "language": f["languages"][0],
        "notes": None,
    }


# ---------------------------------------------------------------------------
# Generation.
# ---------------------------------------------------------------------------


def rand_past(rng: random.Random, now: datetime, max_days: int = 730) -> datetime:
    return now - timedelta(days=rng.randint(0, max_days), seconds=rng.randint(0, 86400))


def bulk_insert(conn, model, rows: list[dict[str, Any]], chunk: int = 5000) -> None:
    if not rows:
        return
    table = model.__table__
    for i in range(0, len(rows), chunk):
        conn.execute(table.insert(), rows[i : i + chunk])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--roms",
        type=int,
        default=100_000,
        help="Number of roms to generate (default: 100000)",
    )
    parser.add_argument(
        "--platforms",
        type=int,
        default=40,
        help="Number of platforms to seed (default: 40)",
    )
    parser.add_argument(
        "--users", type=int, default=12, help="Number of users to seed (default: 12)"
    )
    parser.add_argument(
        "--collections",
        type=int,
        default=40,
        help="Number of user collections (default: 40)",
    )
    parser.add_argument(
        "--play-sessions",
        type=int,
        default=20_000,
        help="Number of play sessions (default: 20000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
        help="Roms generated and inserted per transaction",
    )
    parser.add_argument(
        "--seed", type=int, default=1337, help="RNG seed for reproducible output"
    )
    parser.add_argument(
        "--password", default="password", help="Plain password for every seeded user"
    )
    parser.add_argument(
        "--user-prefix",
        default="loadtest",
        help="Prefix for seeded usernames (kept unique by id)",
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete existing rows from target tables first",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build rows in memory but do not write to the DB",
    )
    parser.add_argument(
        "--images",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate mosaic PNG covers/screenshots on disk (default: on)",
    )
    parser.add_argument(
        "--resources-path",
        default=RESOURCES_BASE_PATH,
        help="Base dir for generated images (default: config RESOURCES_BASE_PATH)",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)  # nosec B311 - fake data, not security-sensitive
    # Separate stream for image pixels so rom rows stay identical with or
    # without --images (image draws never perturb the main rng sequence).
    img_rng = random.Random(args.seed ^ 0x53A17)  # nosec B311 - fake data
    now = datetime.now(timezone.utc)
    pool = build_platform_pool()
    if args.platforms > len(pool):
        args.platforms = len(pool)
    platforms = rng.sample(pool, k=args.platforms)
    # Zipf-ish weights so a few platforms dominate the library, like prod.
    weights = sorted((rng.random() ** 2 for _ in platforms), reverse=True)

    print(
        f"Seeding {args.roms:,} roms across {len(platforms)} platforms and {args.users} users (seed={args.seed})."
    )
    if args.dry_run:
        print("DRY RUN: nothing will be written.")

    from sqlalchemy import event, func, select

    from handler.auth import auth_handler
    from handler.database.base_handler import sync_engine

    # Pin every connection to UTC so the random historical timestamps we
    # generate never land in a local DST gap that TIMESTAMP columns reject.
    @event.listens_for(sync_engine, "connect")
    def _session_utc(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        try:
            try:
                cur.execute("SET time_zone = '+00:00'")  # MySQL/MariaDB
            except Exception:
                cur.execute("SET TIME ZONE 'UTC'")  # PostgreSQL
        finally:
            cur.close()

    pw_hash = auth_handler.get_password_hash(args.password)

    # ----- decide starting primary keys (offset past any existing rows) -----
    id_tables = {
        "platforms": Platform,
        "users": User,
        "firmware": Firmware,
        "roms": Rom,
        "rom_files": RomFile,
        "saves": Save,
        "states": State,
        "screenshots": Screenshot,
        "rom_notes": RomNote,
        "rom_user": RomUser,
        "collections": Collection,
        "smart_collections": SmartCollection,
        "sync_sessions": SyncSession,
        "play_sessions": PlaySession,
        "client_tokens": ClientToken,
    }
    starts = {name: 1 for name in id_tables}
    if not args.dry_run:
        with sync_engine.connect() as conn:
            if args.wipe:
                _wipe(conn)
                conn.commit()
            for name, model in id_tables.items():
                current = conn.execute(select(func.max(model.__table__.c.id))).scalar()
                starts[name] = (current or 0) + 1
    ids = Ids(starts)

    counts: dict[str, int] = {k: 0 for k in id_tables}
    counts.update({"devices": 0, "collections_roms": 0, "device_save_sync": 0})
    # Tracks the last standalone rom per platform so a fraction of later roms
    # can reuse its igdb_id, surfacing them as regional siblings via the view.
    sibling_seed: dict[int, dict[str, Any]] = {}

    # ----------------------------- platforms -------------------------------
    platform_rows = []
    for p in platforms:
        pid = ids.take("platforms")
        p["id"] = pid
        platform_rows.append(
            {
                "id": pid,
                "name": p["name"],
                "slug": p["slug"],
                "fs_slug": p["slug"],
                "igdb_id": p["igdb_id"],
                "moby_id": p["moby_id"],
                "ss_id": p["ss_id"],
                "igdb_slug": p["slug"],
                "category": p["category"],
                "generation": p["generation"],
                "family_name": p["family_name"],
                "family_slug": p["family_slug"],
                "url": p["url"],
                "url_logo": p["url_logo"],
                "aspect_ratio": "2 / 3",
                "missing_from_fs": False,
                "created_at": now,
                "updated_at": now,
            }
        )

    # ------------------------------- users ---------------------------------
    user_rows = []
    user_ids: list[int] = []
    for i in range(args.users):
        uid = ids.take("users")
        user_ids.append(uid)
        # Suffix with the assigned id so usernames/emails never collide with
        # rows already in the target database.
        if i == 0:
            username, role = f"{args.user_prefix}_admin_{uid}", Role.ADMIN
        elif i <= 2:
            username, role = f"{args.user_prefix}_editor_{uid}", Role.EDITOR
        else:
            username, role = f"{args.user_prefix}_viewer_{uid}", Role.VIEWER
        created = rand_past(rng, now)
        user_rows.append(
            {
                "id": uid,
                "username": username,
                "hashed_password": pw_hash,
                "email": f"{username}@example.com",
                "enabled": True,
                "role": role,
                "avatar_path": "",
                "last_login": rand_past(rng, now, 30),
                "last_active": rand_past(rng, now, 7),
                "ra_username": "",
                "ra_progression": {},
                "ui_settings": {
                    "theme": rng.choice(["dark", "light"]),
                    "uiVersion": rng.choice(["v1", "v2"]),
                },
                "created_at": created,
                "updated_at": created,
            }
        )

    # ------------------------------ devices --------------------------------
    device_rows = []
    user_devices: dict[int, list[str]] = {uid: [] for uid in user_ids}
    token_rows = []
    for uid in user_ids:
        for _ in range(rng.randint(1, 3)):
            did = rand_hex(rng, 16)
            user_devices[uid].append(did)
            plat, client, ver = rng.choice(DEVICE_CLIENTS)
            seen = rand_past(rng, now, 30)
            device_rows.append(
                {
                    "id": did,
                    "user_id": uid,
                    "name": f"{plat} device",
                    "platform": plat,
                    "client": client,
                    "client_version": ver,
                    "ip_address": f"192.168.{rng.randint(0, 255)}.{rng.randint(2, 254)}",
                    "mac_address": ":".join(rand_hex(rng, 1) for _ in range(6)),
                    "hostname": f"host-{rand_hex(rng, 3)}",
                    "client_device_identifier": rand_hex(rng, 8),
                    "sync_mode": rng.choice(list(SyncMode)),
                    "sync_enabled": True,
                    "sync_config": None,
                    "last_seen": seen,
                    "created_at": rand_past(rng, now),
                    "updated_at": seen,
                }
            )
        tid = ids.take("client_tokens")
        token_rows.append(
            {
                "id": tid,
                "user_id": uid,
                "name": "default token",
                "hashed_token": rand_hex(rng, 32),
                "scopes": "me.read roms.read assets.read assets.write",
                "expires_at": None,
                "last_used_at": rand_past(rng, now, 5),
                "device_id": user_devices[uid][0] if user_devices[uid] else None,
                "created_at": rand_past(rng, now),
                "updated_at": now,
            }
        )

    # ------------------------------ firmware -------------------------------
    firmware_rows = []
    for p in platforms:
        for _ in range(rng.randint(0, 4)):
            fid = ids.take("firmware")
            fname = f"{p['slug']}_bios_{rand_hex(rng, 2)}.bin"
            parts = compute_file_name_parts(fname)
            firmware_rows.append(
                {
                    "id": fid,
                    "platform_id": p["id"],
                    "file_name": fname,
                    "file_name_no_tags": parts.no_tags,
                    "file_name_no_ext": parts.no_ext,
                    "file_extension": parts.extension,
                    "file_path": f"{p['slug']}/bios",
                    "file_size_bytes": rng.randint(1024, 4 * 1024 * 1024),
                    "crc_hash": rand_hex(rng, 4),
                    "md5_hash": rand_hex(rng, 16),
                    "sha1_hash": rand_hex(rng, 20),
                    "is_verified": rng.random() < 0.7,
                    "missing_from_fs": False,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    if not args.dry_run:
        with sync_engine.begin() as conn:
            bulk_insert(conn, Platform, platform_rows)
            bulk_insert(conn, User, user_rows)
            bulk_insert(conn, Device, device_rows)
            bulk_insert(conn, ClientToken, token_rows)
            bulk_insert(conn, Firmware, firmware_rows)
    counts["platforms"] = len(platform_rows)
    counts["users"] = len(user_rows)
    counts["devices"] = len(device_rows)
    counts["client_tokens"] = len(token_rows)
    counts["firmware"] = len(firmware_rows)

    # -------------------------------- roms ---------------------------------
    rom_id_base = starts["roms"]
    images_written = 0
    if args.images:
        print(f"Writing cover/screenshot PNGs under {args.resources_path}")
    t0 = time.time()
    for batch_start in range(0, args.roms, args.batch_size):
        batch_end = min(batch_start + args.batch_size, args.roms)
        rom_rows, file_rows, ru_rows = [], [], []
        save_rows, state_rows, shot_rows, note_rows = [], [], [], []
        dss_rows: list[dict[str, Any]] = []

        for _ in range(batch_start, batch_end):
            platform = rng.choices(platforms, weights=weights, k=1)[0]
            rid = ids.take("roms")

            # Some roms are a different region/revision of a prior game on the
            # same platform: reuse its facts + igdb_id so the sibling view links
            # them, exactly like a real multi-region library.
            seed = sibling_seed.get(platform["id"])
            is_sibling = seed is not None and rng.random() < 0.07
            if seed and is_sibling:
                f = dict(seed["facts"])
                f["region"] = rng.choice(REGIONS)
                f["revision"] = (
                    f"Rev {rng.randint(1, 3)}" if rng.random() < 0.3 else None
                )
            else:
                f = make_facts(rng, platform)
            ext = rng.choice(platform["extensions"])

            tags = f" ({f['region']})"
            if f["revision"]:
                tags += f" ({f['revision']})"
            fs_name = f"{f['title']}{tags}.{ext}"[:445]
            parts = compute_file_name_parts(fs_name)
            multi_disc = rng.random() < 0.08
            size = rng.randint(256 * 1024, 8 * 1024 * 1024 * 1024)
            created = rand_past(rng, now)
            hashable = ext not in ("iso", "cso", "wbfs")

            # Provider presence is sparse and overlapping, like a real scan.
            has_igdb = is_sibling or rng.random() < 0.72
            has_moby = rng.random() < 0.45
            has_ss = rng.random() < 0.55
            has_ra = hashable and rng.random() < 0.30
            has_lb = rng.random() < 0.40
            has_hash = rng.random() < 0.35
            has_hltb = rng.random() < 0.30
            has_fp = platform["slug"] in ("flash", "browser") or rng.random() < 0.05
            igdb_id = (
                seed["igdb_id"]
                if seed and is_sibling
                else (rng.randint(1, 300000) if has_igdb else None)
            )
            if not is_sibling and igdb_id is not None:
                sibling_seed[platform["id"]] = {"igdb_id": igdb_id, "facts": f}

            # Cover art + screenshots: write real mosaic PNGs to the resources
            # tree and point the path columns at them, or leave them empty.
            if args.images:
                n_shots = rng.randint(0, 4)
                path_cover_s, path_cover_l, path_screenshots = generate_rom_images(
                    img_rng, args.resources_path, platform["id"], rid, n_shots
                )
                images_written += 2 + n_shots
            else:
                path_cover_s = path_cover_l = ""
                path_screenshots = []

            rom_rows.append(
                {
                    "id": rid,
                    "platform_id": platform["id"],
                    "igdb_id": igdb_id,
                    "moby_id": rng.randint(1, 200000) if has_moby else None,
                    "ss_id": rng.randint(1, 200000) if has_ss else None,
                    "ra_id": rng.randint(1, 30000) if has_ra else None,
                    "launchbox_id": rng.randint(1, 100000) if has_lb else None,
                    "hasheous_id": rng.randint(1, 100000) if has_hash else None,
                    "hltb_id": rng.randint(1, 100000) if has_hltb else None,
                    "sgdb_id": None,
                    "tgdb_id": None,
                    "flashpoint_id": rand_hex(rng, 8) if has_fp else None,
                    "gamelist_id": None,
                    "libretro_id": None,
                    "fs_name": fs_name,
                    "fs_name_no_tags": parts.no_tags,
                    "fs_name_no_ext": parts.no_ext,
                    "fs_extension": parts.extension,
                    "fs_path": f"{platform['slug']}/roms",
                    "fs_size_bytes": size,
                    "name": f["title"],
                    "name_sort_key": compute_name_sort_key(f["title"]),
                    "slug": f["slug"],
                    "summary": f["summary"],
                    "igdb_metadata": build_igdb_metadata(rng, f) if has_igdb else {},
                    "moby_metadata": (
                        build_moby_metadata(rng, f, platform) if has_moby else {}
                    ),
                    "ss_metadata": build_ss_metadata(rng, f) if has_ss else {},
                    "ra_metadata": build_ra_metadata(rng, f) if has_ra else {},
                    "launchbox_metadata": (
                        build_launchbox_metadata(rng, f) if has_lb else {}
                    ),
                    "hasheous_metadata": (
                        build_hasheous_metadata(rng) if has_hash else {}
                    ),
                    "hltb_metadata": build_hltb_metadata(rng, f) if has_hltb else {},
                    "flashpoint_metadata": (
                        build_flashpoint_metadata(rng, f) if has_fp else {}
                    ),
                    "gamelist_metadata": {},
                    "manual_metadata": {},
                    "path_cover_s": path_cover_s,
                    "path_cover_l": path_cover_l,
                    "url_cover": "",
                    "path_manual": "",
                    "url_manual": "",
                    "path_screenshots": path_screenshots,
                    "url_screenshots": [],
                    "revision": f["revision"],
                    "version": None,
                    "regions": [f["region"]],
                    "languages": f["languages"],
                    "tags": [],
                    "crc_hash": rand_hex(rng, 4) if hashable else None,
                    "md5_hash": rand_hex(rng, 16) if hashable else None,
                    "sha1_hash": rand_hex(rng, 20) if hashable else None,
                    "ra_hash": rand_hex(rng, 16) if has_ra else None,
                    "missing_from_fs": rng.random() < 0.02,
                    "created_at": created,
                    "updated_at": created,
                }
            )

            # Rom files: one per disc, plus the occasional manual.
            n_files = rng.randint(2, 4) if multi_disc else 1
            for disc in range(n_files):
                fid = ids.take("rom_files")
                if n_files > 1:
                    file_name = f"{f['title']} (Disc {disc + 1}).{ext}"
                    fsize = size // n_files
                else:
                    file_name, fsize = fs_name, size
                file_rows.append(
                    {
                        "id": fid,
                        "rom_id": rid,
                        "file_name": file_name,
                        "file_path": (
                            f"{platform['slug']}/roms/{f['slug']}"
                            if multi_disc
                            else f"{platform['slug']}/roms"
                        ),
                        "file_size_bytes": fsize,
                        "last_modified": created.timestamp(),
                        "crc_hash": rand_hex(rng, 4) if hashable else None,
                        "md5_hash": rand_hex(rng, 16) if hashable else None,
                        "sha1_hash": rand_hex(rng, 20) if hashable else None,
                        "ra_hash": rand_hex(rng, 16) if has_ra else None,
                        "chd_sha1_hash": rand_hex(rng, 20) if ext == "chd" else None,
                        "archive_members": None,
                        "category": RomFileCategory.GAME,
                        "audio_meta": None,
                        "missing_from_fs": False,
                        "created_at": created,
                        "updated_at": created,
                    }
                )
            if rng.random() < 0.15:
                fid = ids.take("rom_files")
                man_name = f"{f['title']} (Manual).pdf"
                file_rows.append(
                    {
                        "id": fid,
                        "rom_id": rid,
                        "file_name": man_name,
                        "file_path": f"{platform['slug']}/roms/{f['slug']}",
                        "file_size_bytes": rng.randint(50_000, 5_000_000),
                        "last_modified": created.timestamp(),
                        "crc_hash": None,
                        "md5_hash": None,
                        "sha1_hash": None,
                        "ra_hash": None,
                        "chd_sha1_hash": None,
                        "archive_members": None,
                        "category": RomFileCategory.MANUAL,
                        "audio_meta": None,
                        "missing_from_fs": False,
                        "created_at": created,
                        "updated_at": created,
                    }
                )

            # Per-user playthrough state for a random subset.
            interacted = rng.sample(
                user_ids,
                k=min(
                    len(user_ids),
                    rng.choices([0, 1, 2, 3], weights=[40, 35, 15, 10])[0],
                ),
            )
            for idx, uid in enumerate(interacted):
                ruid = ids.take("rom_user")
                played = rand_past(rng, now, 120) if rng.random() < 0.7 else None
                ru_rows.append(
                    {
                        "id": ruid,
                        "rom_id": rid,
                        "user_id": uid,
                        "is_main_sibling": idx == 0,
                        "last_played": played,
                        "backlogged": rng.random() < 0.2,
                        "now_playing": rng.random() < 0.05,
                        "hidden": rng.random() < 0.03,
                        "rating": rng.randint(0, 10),
                        "difficulty": rng.randint(0, 10),
                        "completion": rng.randint(0, 100),
                        "status": (
                            rng.choice(list(RomUserStatus))
                            if rng.random() < 0.6
                            else None
                        ),
                        "created_at": created,
                        "updated_at": played or created,
                    }
                )

                # Saves / states / screenshots belong to a user who played.
                if rng.random() < 0.35:
                    for _ in range(rng.randint(1, 3)):
                        sid = ids.take("saves")
                        emu = rng.choice(EMULATORS)
                        sname = f"{f['title']}.{rng.choice(SAVE_EXTENSIONS)}"
                        sparts = compute_file_name_parts(sname)
                        dev = (
                            rng.choice(user_devices[uid]) if user_devices[uid] else None
                        )
                        save_rows.append(
                            {
                                "id": sid,
                                "rom_id": rid,
                                "user_id": uid,
                                "file_name": sname,
                                "file_name_no_tags": sparts.no_tags,
                                "file_name_no_ext": sparts.no_ext,
                                "file_extension": sparts.extension,
                                "file_path": f"users/{uid}/saves/{platform['slug']}/{rid}/{emu}",
                                "file_size_bytes": rng.randint(1024, 8 * 1024 * 1024),
                                "emulator": emu,
                                "slot": rng.choice(["1", "2", "3", "auto", None]),
                                "content_hash": rand_hex(rng, 16),
                                "origin_device_id": dev,
                                "is_public": rng.random() < 0.1,
                                "missing_from_fs": False,
                                "created_at": created,
                                "updated_at": created,
                            }
                        )
                        if dev and rng.random() < 0.6:
                            dss_rows.append(
                                {
                                    "device_id": dev,
                                    "save_id": sid,
                                    "last_synced_at": rand_past(rng, now, 10),
                                    "is_untracked": False,
                                    "created_at": created,
                                    "updated_at": now,
                                }
                            )
                if rng.random() < 0.30:
                    for _ in range(rng.randint(1, 4)):
                        stid = ids.take("states")
                        emu = rng.choice(EMULATORS)
                        stname = f"{f['title']}.{rng.choice(STATE_EXTENSIONS)}"
                        stparts = compute_file_name_parts(stname)
                        state_rows.append(
                            {
                                "id": stid,
                                "rom_id": rid,
                                "user_id": uid,
                                "file_name": stname,
                                "file_name_no_tags": stparts.no_tags,
                                "file_name_no_ext": stparts.no_ext,
                                "file_extension": stparts.extension,
                                "file_path": f"users/{uid}/states/{platform['slug']}/{rid}/{emu}",
                                "file_size_bytes": rng.randint(
                                    64 * 1024, 32 * 1024 * 1024
                                ),
                                "emulator": emu,
                                "is_public": rng.random() < 0.1,
                                "missing_from_fs": False,
                                "created_at": created,
                                "updated_at": created,
                            }
                        )
                if rng.random() < 0.40:
                    for _ in range(rng.randint(1, 5)):
                        scid = ids.take("screenshots")
                        scname = f"{f['title']}-{rand_hex(rng, 3)}.png"
                        scparts = compute_file_name_parts(scname)
                        shot_rows.append(
                            {
                                "id": scid,
                                "rom_id": rid,
                                "user_id": uid,
                                "file_name": scname,
                                "file_name_no_tags": scparts.no_tags,
                                "file_name_no_ext": scparts.no_ext,
                                "file_extension": scparts.extension,
                                "file_path": f"users/{uid}/screenshots/{platform['slug']}/{rid}",
                                "file_size_bytes": rng.randint(
                                    20 * 1024, 4 * 1024 * 1024
                                ),
                                "is_gallery": rng.random() < 0.5,
                                "is_public": rng.random() < 0.2,
                                "missing_from_fs": False,
                                "created_at": created,
                                "updated_at": created,
                            }
                        )
                if rng.random() < 0.05:
                    nid = ids.take("rom_notes")
                    note_rows.append(
                        {
                            "id": nid,
                            "rom_id": rid,
                            "user_id": uid,
                            "title": f"Notes #{idx}",
                            "content": "Remember the boss pattern on stage 3.",
                            "is_public": rng.random() < 0.3,
                            "tags": rng.sample(
                                ["tip", "bug", "secret", "todo"], k=rng.randint(0, 2)
                            ),
                            "created_at": created,
                            "updated_at": created,
                        }
                    )

        if not args.dry_run:
            with sync_engine.begin() as conn:
                bulk_insert(conn, Rom, rom_rows)
                bulk_insert(conn, RomFile, file_rows)
                bulk_insert(conn, RomUser, ru_rows)
                bulk_insert(conn, Save, save_rows)
                bulk_insert(conn, State, state_rows)
                bulk_insert(conn, Screenshot, shot_rows)
                bulk_insert(conn, RomNote, note_rows)
                bulk_insert(conn, DeviceSaveSync, dss_rows)

        counts["roms"] += len(rom_rows)
        counts["rom_files"] += len(file_rows)
        counts["rom_user"] += len(ru_rows)
        counts["saves"] += len(save_rows)
        counts["states"] += len(state_rows)
        counts["screenshots"] += len(shot_rows)
        counts["rom_notes"] += len(note_rows)
        counts["device_save_sync"] += len(dss_rows)

        done = batch_end
        rate = done / max(time.time() - t0, 1e-6)
        print(f"  roms {done:,}/{args.roms:,}  ({rate:,.0f}/s)", flush=True)

    rom_id_last = ids.take("roms") - 1  # next free id - 1 == last assigned
    all_rom_ids = range(rom_id_base, rom_id_last + 1)

    # ----------------------------- collections -----------------------------
    coll_rows, coll_rom_rows, smart_rows = [], [], []
    for c in range(args.collections):
        cid = ids.take("collections")
        owner = rng.choice(user_ids)
        sample_n = rng.randint(10, min(500, len(all_rom_ids)))
        members = rng.sample(list(all_rom_ids), k=sample_n)
        created = rand_past(rng, now)
        coll_rows.append(
            {
                "id": cid,
                "name": f"{rng.choice(['Favorites', 'Backlog', 'Co-op Night', 'Speedruns', 'RPG Marathon', 'Childhood'])} {c}",
                "description": "An auto-generated test collection.",
                "is_public": rng.random() < 0.4,
                "is_favorite": c == 0,
                "path_cover_l": "",
                "path_cover_s": "",
                "url_cover": "",
                "user_id": owner,
                "created_at": created,
                "updated_at": created,
            }
        )
        for rid in members:
            coll_rom_rows.append(
                {
                    "collection_id": cid,
                    "rom_id": rid,
                    "created_at": created,
                    "updated_at": created,
                }
            )

    for _s in range(max(1, args.collections // 8)):
        sid = ids.take("smart_collections")
        sample_n = rng.randint(5, min(200, len(all_rom_ids)))
        members = rng.sample(list(all_rom_ids), k=sample_n)
        genre = rng.choice(GENRES)
        smart_rows.append(
            {
                "id": sid,
                "name": f"All {genre}",
                "description": f"Every {genre} game.",
                "is_public": rng.random() < 0.5,
                "rom_count": len(members),
                "rom_ids": members,
                "path_covers_small": [],
                "path_covers_large": [],
                "filter_criteria": {"genres": [genre]},
                "user_id": rng.choice(user_ids),
                "created_at": now,
                "updated_at": now,
            }
        )

    # --------------------------- sync sessions -----------------------------
    sync_rows = []
    all_device_ids = [(uid, d) for uid, ds in user_devices.items() for d in ds]
    for _ in range(min(len(all_device_ids) * 2, 2000)):
        uid, dev = rng.choice(all_device_ids)
        ssid = ids.take("sync_sessions")
        started = rand_past(rng, now, 30)
        planned = rng.randint(0, 50)
        completed = rng.randint(0, planned)
        sync_rows.append(
            {
                "id": ssid,
                "device_id": dev,
                "user_id": uid,
                "status": rng.choice(list(SyncSessionStatus)),
                "initiated_at": started,
                "completed_at": started + timedelta(seconds=rng.randint(1, 600)),
                "operations_planned": planned,
                "operations_completed": completed,
                "operations_failed": planned - completed,
                "error_message": None,
                "created_at": started,
                "updated_at": now,
            }
        )

    # ---------------------------- play sessions ----------------------------
    play_rows = []
    rom_id_list = list(all_rom_ids)
    for _ in range(args.play_sessions):
        uid = rng.choice(user_ids)
        dev = rng.choice(user_devices[uid]) if user_devices[uid] else None
        psid = ids.take("play_sessions")
        start = rand_past(rng, now, 180)
        dur = rng.randint(60_000, 4 * 3600_000)
        play_rows.append(
            {
                "id": psid,
                "user_id": uid,
                "device_id": dev,
                "rom_id": rng.choice(rom_id_list),
                "sync_session_id": None,
                "save_slot": rng.choice(["1", "2", "auto", None]),
                "start_time": start,
                "end_time": start + timedelta(milliseconds=dur),
                "duration_ms": dur,
                "created_at": start,
                "updated_at": start,
            }
        )

    if not args.dry_run:
        with sync_engine.begin() as conn:
            bulk_insert(conn, Collection, coll_rows)
            bulk_insert(conn, CollectionRom, coll_rom_rows)
            bulk_insert(conn, SmartCollection, smart_rows)
            bulk_insert(conn, SyncSession, sync_rows)
            bulk_insert(conn, PlaySession, play_rows)
    counts["collections"] = len(coll_rows)
    counts["collections_roms"] = len(coll_rom_rows)
    counts["smart_collections"] = len(smart_rows)
    counts["sync_sessions"] = len(sync_rows)
    counts["play_sessions"] = len(play_rows)

    # ------------------------------- report --------------------------------
    elapsed = time.time() - t0
    print("\nDone in %.1fs. Row counts:" % elapsed)
    for name in sorted(counts):
        print(f"  {name:<20} {counts[name]:>12,}")
    if args.images:
        print(f"  {'images (png)':<20} {images_written:>12,}")
    if not args.dry_run and user_rows:
        print(
            f"\nLogin with username '{user_rows[0]['username']}' "
            "and the password passed via --password (default: 'password')."
        )
    return 0


def _wipe(conn) -> None:
    """Delete all rows from the tables this script populates (FK-safe order)."""
    from sqlalchemy import text

    # roms_metadata and sibling_roms are views, so they are intentionally
    # absent: deleting their underlying roms clears them.
    tables = [
        "play_sessions",
        "device_save_sync",
        "sync_sessions",
        "client_tokens",
        "collections_roms",
        "smart_collections",
        "collections",
        "rom_notes",
        "rom_user",
        "screenshots",
        "states",
        "saves",
        "rom_files",
        "roms",
        "firmware",
        "devices",
        "users",
        "platforms",
    ]
    print("Wiping existing rows from %d tables..." % len(tables))
    for t in tables:
        # nosec B608 - table names are from the hardcoded list above, not user input
        conn.execute(text(f"DELETE FROM {t}"))  # nosec B608


if __name__ == "__main__":
    raise SystemExit(main())

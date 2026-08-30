#!/usr/bin/env python3
"""Seed a small soundtrack library so the jukebox can be exercised by hand.

Creates a few platforms, games (with game genres and release years) and
soundtrack files carrying track metadata, which is what the /api/music
endpoints and the v2 Jukebox read.

Run from the backend directory, pointed at a throwaway database:

    DB_NAME=romm_dev uv run tools/seed_soundtracks.py

This is a TEST tool: never point it at a real library.
"""

from __future__ import annotations

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from handler.database import (  # noqa: E402
    db_platform_handler,
    db_rom_handler,
    db_user_handler,
)
from models.platform import Platform  # noqa: E402
from models.rom import Rom, RomFile, RomFileCategory, TrackMeta  # noqa: E402
from models.user import Role  # noqa: E402

PLATFORMS = [
    ("genesis", "Sega Genesis"),
    ("snes", "Super Nintendo"),
    ("psx", "PlayStation"),
]

GAMES = [
    ("Sonic the Hedgehog", "genesis", 1991, ["Platform", "Action"], "Nakamura"),
    ("Streets of Rage", "genesis", 1991, ["Beat 'em up"], "Koshiro"),
    ("Chrono Trigger", "snes", 1995, ["Role-playing (RPG)"], "Mitsuda"),
    ("Super Metroid", "snes", 1994, ["Platform", "Adventure"], "Yamamoto"),
    ("Final Fantasy VII", "psx", 1997, ["Role-playing (RPG)"], "Uematsu"),
    ("Castlevania SotN", "psx", 1997, ["Platform", "Adventure"], "Yamane"),
]

TRACK_NAMES = [
    "Opening",
    "Main Theme",
    "Field",
    "Battle",
    "Boss",
    "Ending",
    "Credits",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tracks-per-game", type=int, default=5, help="Soundtrack files per game."
    )
    args = parser.parse_args()

    rng = random.Random(1991)
    users = db_user_handler.get_users()
    admin = next((u for u in users if u.role == Role.ADMIN), None) or next(
        iter(users), None
    )
    if admin is None:
        raise SystemExit("No users found — create one before seeding.")

    by_slug: dict[str, Platform] = {}
    for slug, name in PLATFORMS:
        existing = db_platform_handler.get_platform_by_fs_slug(slug)
        by_slug[slug] = existing or db_platform_handler.add_platform(
            Platform(name=name, slug=slug, fs_slug=slug)
        )

    created = 0
    for name, slug, year, genres, artist in GAMES:
        platform = by_slug[slug]
        rom = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=name,
                slug=name.lower().replace(" ", "-"),
                fs_name=f"{name}.zip",
                fs_name_no_tags=name,
                fs_name_no_ext=name,
                fs_extension="zip",
                fs_path=f"{slug}/roms",
                manual_metadata={"genres": genres},
            )
        )
        db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin.id)
        for index in range(args.tracks_per_game):
            title = TRACK_NAMES[index % len(TRACK_NAMES)]
            db_rom_handler.add_rom_file(
                RomFile(
                    rom_id=rom.id,
                    file_name=f"{index + 1:02d} - {title}.mp3",
                    file_path=f"{rom.fs_path}/{name}/soundtrack",
                    file_size_bytes=rng.randint(2_000_000, 8_000_000),
                    category=RomFileCategory.SOUNDTRACK,
                    track_meta=TrackMeta(
                        rom_id=rom.id,
                        title=title,
                        artist=artist,
                        album=f"{name} OST",
                        genre="Game",
                        year=year,
                        track=index + 1,
                        duration_seconds=float(rng.randint(60, 240)),
                    ),
                )
            )
            created += 1

    print(f"Seeded {len(GAMES)} games and {created} soundtrack tracks.")


if __name__ == "__main__":
    main()

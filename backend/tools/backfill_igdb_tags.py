#!/usr/bin/env python3
"""Backfill IGDB keywords, themes and player perspectives into existing ROMs.

These three fields were never requested by the scanner, so a library matched
before they were added carries none of them. Re-scanning to pick them up would
re-fetch every field for every game one at a time; this asks only for what is
missing and batches it, so a 12k-game library is a few dozen requests rather
than twelve thousand.

Run from the backend directory, with IGDB credentials in the environment:

    uv run tools/backfill_igdb_tags.py --dry-run     # report coverage only
    uv run tools/backfill_igdb_tags.py               # write to roms.igdb_metadata
    uv run tools/backfill_igdb_tags.py --limit 500   # sample, for evaluating

Reads the database configured by the usual env vars. Point it at a copy of
your library, not production: it rewrites `roms.igdb_metadata`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Allow running as `python3 tools/backfill_igdb_tags.py` from backend/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select  # noqa: E402

from handler.database.base_handler import sync_session  # noqa: E402
from handler.metadata import meta_igdb_handler  # noqa: E402
from models.rom import Rom  # noqa: E402
from utils.context import initialize_context  # noqa: E402

# IGDB caps a single response at 500 rows.
BATCH_SIZE = 500

TAG_FIELDS = ("id", "keywords.name", "themes.name", "player_perspectives.name")
TAG_KEYS = ("keywords", "themes", "player_perspectives")


def load_igdb_ids(limit: int | None) -> dict[int, int]:
    """IGDB id -> one ROM id, for every matched game in the library."""
    stmt = select(Rom.igdb_id, Rom.id).where(Rom.igdb_id.is_not(None))
    if limit:
        stmt = stmt.limit(limit)

    with sync_session.begin() as session:
        return {igdb_id: rom_id for igdb_id, rom_id in session.execute(stmt).all()}


def report_coverage() -> None:
    with sync_session.begin() as session:
        rows = session.execute(
            select(Rom.igdb_metadata).where(Rom.igdb_id.is_not(None))
        ).all()

    total = len(rows)
    have = {key: 0 for key in TAG_KEYS}
    for (metadata,) in rows:
        for key in TAG_KEYS:
            if metadata and metadata.get(key):
                have[key] += 1

    print(f"IGDB-matched roms: {total:,}")
    for key in TAG_KEYS:
        share = (have[key] / total * 100) if total else 0
        print(f"  with {key:<20} {have[key]:>7,}  ({share:.1f}%)")


async def fetch_tags(igdb_ids: list[int]) -> dict[int, dict[str, list[str]]]:
    """Ask IGDB for just the three tag fields, in batches of BATCH_SIZE."""
    results: dict[int, dict[str, list[str]]] = {}

    for start in range(0, len(igdb_ids), BATCH_SIZE):
        chunk = igdb_ids[start : start + BATCH_SIZE]
        where = f"id = ({','.join(str(i) for i in chunk)})"

        games = await meta_igdb_handler.igdb_service.list_games(
            fields=TAG_FIELDS, where=where, limit=BATCH_SIZE
        )

        for game in games:
            game_id = game.get("id")
            if game_id is None:
                continue
            results[game_id] = {
                key: [
                    entry.get("name", "")
                    for entry in (game.get(key) or [])
                    if entry.get("name")
                ]
                for key in TAG_KEYS
            }

        done = min(start + BATCH_SIZE, len(igdb_ids))
        print(f"  fetched {done:,}/{len(igdb_ids):,}")

    return results


def merge_tags(
    rom_by_igdb_id: dict[int, int], tags: dict[int, dict[str, list[str]]]
) -> int:
    """Merge the fetched tags into each ROM's existing igdb_metadata blob."""
    written = 0

    with sync_session.begin() as session:
        for igdb_id, values in tags.items():
            rom_id = rom_by_igdb_id.get(igdb_id)
            if rom_id is None:
                continue

            rom = session.get(Rom, rom_id)
            if rom is None:
                continue

            # Replace rather than merge: IGDB is the authority for these keys,
            # and an empty list is a meaningful "this game has no keywords".
            metadata = dict(rom.igdb_metadata or {})
            metadata.update(values)
            rom.igdb_metadata = metadata
            written += 1

    return written


@initialize_context()
async def main_async(args: argparse.Namespace) -> int:
    print("Coverage before:")
    report_coverage()

    # Coverage is a pure database read, so --dry-run works without credentials.
    if args.dry_run:
        return 0

    if not meta_igdb_handler.is_enabled():
        print("\nIGDB is not enabled: set IGDB_CLIENT_ID and IGDB_CLIENT_SECRET.")
        return 1

    rom_by_igdb_id = load_igdb_ids(args.limit)
    print(f"\nFetching tags for {len(rom_by_igdb_id):,} IGDB ids...")

    tags = await fetch_tags(sorted(rom_by_igdb_id))
    written = merge_tags(rom_by_igdb_id, tags)
    print(f"\nUpdated {written:,} roms.")

    print("\nCoverage after:")
    report_coverage()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report current coverage and stop"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Only backfill this many roms"
    )
    args = parser.parse_args()

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

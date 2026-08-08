#!/usr/bin/env python3
"""Print what the recommendations engine actually produces, for eyeballing.

Recommendation quality is a judgement call that tests cannot make, so this
dumps the index in a readable form: for each sampled game, its own metadata
facets followed by its top neighbours, their scores and the reasons behind
them. Reading twenty of these tells you whether the weights are sane far
faster than clicking through the UI.

Run from the backend directory:

    uv run tools/inspect_recommendations.py --build          # build, then sample
    uv run tools/inspect_recommendations.py --sample 20
    uv run tools/inspect_recommendations.py --name "Super Metroid"
    uv run tools/inspect_recommendations.py --platform snes
    uv run tools/inspect_recommendations.py --feed myusername
    uv run tools/inspect_recommendations.py --stats

Reads the database configured by the usual env vars (DB_HOST, DB_NAME, ...).
Point it at a copy of your library, not production: --build rewrites the
`rom_similarity` table.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from collections import Counter
from typing import Any

# Allow running as `python3 tools/inspect_recommendations.py` from backend/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import distinct, func, select  # noqa: E402

from handler.database import (  # noqa: E402
    db_recommendation_handler,
    db_rom_handler,
    db_user_handler,
)
from handler.database.base_handler import sync_session  # noqa: E402
from handler.recommendation import FeedBuilder, SimilarityBuilder  # noqa: E402
from models.platform import Platform  # noqa: E402
from models.recommendation import RomSimilarity  # noqa: E402
from models.rom import Rom, RomMetadata  # noqa: E402

NAME_WIDTH = 42
FACET_ORDER = ("collection", "franchise", "company", "genre", "game_mode", "decade")


class RomInfo:
    """The display fields for one ROM, resolved in a single query."""

    def __init__(self, rom_id: int, name: str, platform: str) -> None:
        self.rom_id = rom_id
        self.name = name
        self.platform = platform

    def label(self) -> str:
        return f"{truncate(self.name, NAME_WIDTH):<{NAME_WIDTH}} ({self.platform})"


def truncate(value: str, width: int) -> str:
    value = value or "?"
    return value if len(value) <= width else value[: width - 1] + "…"


def load_rom_info(rom_ids: list[int]) -> dict[int, RomInfo]:
    if not rom_ids:
        return {}

    stmt = (
        select(Rom.id, Rom.name, Rom.fs_name_no_tags, Platform.slug)
        .join(Platform, Platform.id == Rom.platform_id)
        .where(Rom.id.in_(rom_ids))
    )
    with sync_session.begin() as session:
        return {
            row[0]: RomInfo(row[0], row[1] or row[2], row[3])
            for row in session.execute(stmt).all()
        }


def load_facets(rom_id: int) -> dict[str, list[str]]:
    stmt = select(
        RomMetadata.genres,
        RomMetadata.franchises,
        RomMetadata.collections,
        RomMetadata.companies,
        RomMetadata.game_modes,
    ).where(RomMetadata.rom_id == rom_id)

    with sync_session.begin() as session:
        row = session.execute(stmt).first()

    if row is None:
        return {}

    return {
        "genres": row[0] or [],
        "franchises": row[1] or [],
        "collections": row[2] or [],
        "companies": row[3] or [],
        "game_modes": row[4] or [],
    }


def format_reasons(reasons: list[dict[str, Any]]) -> str:
    if not reasons:
        return "-"
    return " · ".join(
        (
            f"{reason.get('facet')}:{reason.get('value')}"
            if reason.get("value")
            else str(reason.get("facet"))
        )
        for reason in reasons
    )


def indexed_rom_ids(platform_slug: str | None) -> list[int]:
    """Every ROM that has at least one outgoing edge."""
    stmt = select(distinct(RomSimilarity.rom_id))
    if platform_slug:
        stmt = (
            stmt.join(Rom, Rom.id == RomSimilarity.rom_id)
            .join(Platform, Platform.id == Rom.platform_id)
            .where(Platform.slug == platform_slug)
        )

    with sync_session.begin() as session:
        return [row[0] for row in session.execute(stmt).all()]


def find_rom_ids_by_name(needle: str, limit: int) -> list[int]:
    stmt = (
        select(Rom.id)
        .where(Rom.name.ilike(f"%{needle}%"))
        .order_by(Rom.name_sort_key.asc())
        .limit(limit)
    )
    with sync_session.begin() as session:
        return [row[0] for row in session.execute(stmt).all()]


def print_rom(rom_id: int, info: dict[int, RomInfo], limit: int) -> None:
    source = info.get(rom_id)
    print()
    print("=" * 78)
    print(source.label() if source else f"rom {rom_id}")

    facets = load_facets(rom_id)
    summary = " · ".join(
        f"{key}={', '.join(values)}" for key, values in facets.items() if values
    )
    print(f"  {summary or 'no metadata facets'}")
    print("-" * 78)

    edges = db_recommendation_handler.get_similar_rom_edges(rom_id, limit=limit)
    if not edges:
        print("  (no neighbours -- unmatched metadata, or the index is not built)")
        return

    neighbour_info = load_rom_info([edge.rom_id for edge in edges])
    for edge in edges:
        neighbour = neighbour_info.get(edge.rom_id)
        label = neighbour.label() if neighbour else f"rom {edge.rom_id}"
        print(f"  {edge.score:>6.3f}  {label}  {format_reasons(edge.reasons)}")


def print_feed(username: str, limit: int) -> int:
    user = db_user_handler.get_user_by_username(username)
    if user is None:
        print(f"No user named {username!r}")
        return 1

    print()
    print("=" * 78)
    print(f"Personalised feed for {username}")
    print("-" * 78)

    feed = FeedBuilder(user.id).build(limit=limit)
    if not feed:
        print("  (empty -- no play history and no rated games in the library)")
        return 0

    info = load_rom_info([item.rom.id for item in feed])
    for item in feed:
        entry = info.get(item.rom.id)
        label = entry.label() if entry else f"rom {item.rom.id}"
        why = (
            f"because you played {item.seed_rom_name}"
            if item.seed_rom_name
            else format_reasons(item.reasons)
        )
        print(f"  {item.score:>6.3f}  {label}  {why}")

    return 0


def print_stats() -> None:
    with sync_session.begin() as session:
        total_roms = session.scalar(select(func.count()).select_from(Rom)) or 0
        edges = session.scalar(select(func.count()).select_from(RomSimilarity)) or 0
        covered = (
            session.scalar(select(func.count(distinct(RomSimilarity.rom_id)))) or 0
        )
        score_bounds = session.execute(
            select(
                func.min(RomSimilarity.score),
                func.avg(RomSimilarity.score),
                func.max(RomSimilarity.score),
            )
        ).first()
        reason_rows = session.execute(select(RomSimilarity.reasons).limit(20_000)).all()

    print()
    print("=" * 78)
    print("Index health")
    print("-" * 78)
    print(f"  roms in library      {total_roms:>10,}")
    print(
        f"  roms with neighbours {covered:>10,}"
        f"  ({(covered / total_roms * 100 if total_roms else 0):.1f}% coverage)"
    )
    print(f"  edges                {edges:>10,}")
    if covered:
        print(f"  avg edges per rom    {edges / covered:>10.1f}")
    if score_bounds and score_bounds[0] is not None:
        print(
            f"  score min/avg/max    "
            f"{score_bounds[0]:.3f} / {float(score_bounds[1]):.3f} / {score_bounds[2]:.3f}"
        )

    facet_counts: Counter[str] = Counter()
    for (reasons,) in reason_rows:
        for reason in reasons or ():
            facet_counts[str(reason.get("facet"))] += 1

    if facet_counts:
        print()
        print("  Why games were matched (sampled):")
        total_reasons = sum(facet_counts.values())
        for facet, count in facet_counts.most_common():
            share = count / total_reasons * 100
            bar = "█" * max(1, round(share / 2))
            print(f"    {facet:<12} {share:>5.1f}%  {bar}")

    # A library whose matches are nearly all one weak facet is the signal that
    # the metadata is too thin for the content signal to say anything.
    if facet_counts:
        top_facet, top_count = facet_counts.most_common(1)[0]
        if top_count / sum(facet_counts.values()) > 0.8:
            print()
            print(
                f"  NOTE: {top_facet} accounts for over 80% of matches. Expect weak "
                "recommendations until more metadata is scraped."
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Rebuild the similarity index before inspecting",
    )
    parser.add_argument(
        "--sample", type=int, default=10, help="Random games to show (default: 10)"
    )
    parser.add_argument(
        "--limit", type=int, default=8, help="Neighbours per game (default: 8)"
    )
    parser.add_argument("--rom", type=int, action="append", help="Inspect this rom id")
    parser.add_argument("--name", help="Inspect games whose name matches this text")
    parser.add_argument("--platform", help="Restrict the random sample to this slug")
    parser.add_argument("--feed", help="Show the personalised feed for this username")
    parser.add_argument("--stats", action="store_true", help="Show index health only")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for sampling")
    args = parser.parse_args()

    if args.build:
        print("Building similarity index...")
        stats = SimilarityBuilder().build()
        print(
            f"  indexed {stats.roms_indexed:,} roms, wrote {stats.edges_written:,} edges, "
            f"skipped {stats.roms_without_metadata:,} without usable metadata"
        )

    if args.stats:
        print_stats()
        return 0

    if args.feed:
        return print_feed(args.feed, args.limit)

    rom_ids: list[int] = list(args.rom or [])
    if args.name:
        found = find_rom_ids_by_name(args.name, args.sample)
        if not found:
            print(f"No games matching {args.name!r}")
            return 1
        rom_ids.extend(found)

    if not rom_ids:
        candidates = indexed_rom_ids(args.platform)
        if not candidates:
            print(
                "No indexed games found. Run with --build first "
                "(or check --platform is a real slug)."
            )
            return 1
        rng = random.Random(args.seed)  # nosec B311 - sampling for display only
        rom_ids = rng.sample(candidates, min(args.sample, len(candidates)))

    info = load_rom_info(rom_ids)
    for rom_id in rom_ids:
        print_rom(rom_id, info, args.limit)

    print()
    print_stats()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

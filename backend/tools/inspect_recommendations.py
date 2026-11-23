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
    uv run tools/inspect_recommendations.py --sample 40 --seed 7 --report out.html

Reads the database configured by the usual env vars (DB_HOST, DB_NAME, ...).
Point it at a copy of your library, not production: --build rewrites the
`rom_similarity` table.
"""

from __future__ import annotations

import argparse
import html
import os
import random
import shlex
import sys
from collections import Counter
from typing import Any, NamedTuple

# Allow running as `python3 tools/inspect_recommendations.py` from backend/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import distinct, func, select  # noqa: E402

# Imported ahead of everything else that reaches `decorators.database`, which
# imports back out of this package: whichever of the two loads second resolves,
# and the app only works because it always initialises this one first.
from handler.database import (  # noqa: E402
    db_recommendation_handler,
    db_user_handler,
)

# isort: split
from handler.auth.permissions import (  # noqa: E402
    ResolvedPermissions,
    resolve_permissions,
)
from handler.database.base_handler import sync_session  # noqa: E402
from handler.recommendation import (  # noqa: E402
    SimilarityBuilder,
    recommended_roms,
    similar_roms,
)
from models.platform import Platform  # noqa: E402
from models.recommendation import RomSimilarity  # noqa: E402
from models.rom import Rom, RomMetadata  # noqa: E402

NAME_WIDTH = 42


class RomInfo:
    """The display fields for one ROM, resolved in a single query."""

    def __init__(self, name: str, platform: str) -> None:
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
            row[0]: RomInfo(row[1] or row[2], row[3])
            for row in session.execute(stmt).all()
        }


def load_facets(rom_id: int) -> dict[str, list[str]]:
    stmt = select(
        RomMetadata.genres,
        RomMetadata.franchises,
        RomMetadata.collections,
        RomMetadata.companies,
        RomMetadata.game_modes,
        RomMetadata.keywords,
        RomMetadata.themes,
        RomMetadata.player_perspectives,
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
        "keywords": row[5] or [],
        "themes": row[6] or [],
        "perspectives": row[7] or [],
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


# No request behind a CLI run, and the point is to see the whole index.
_UNRESTRICTED = ResolvedPermissions(
    is_admin=True,
    user_id=None,
    grants=frozenset(),
    hidden_platform_ids=frozenset(),
    hidden_rom_ids=frozenset(),
)


class Neighbour(NamedTuple):
    score: float
    rom_id: int
    reasons: list[dict[str, Any]]


def neighbours_of(rom_id: int, limit: int, capped: bool) -> list[Neighbour]:
    """What a surface would render, through the same path the endpoint uses.

    `capped=False` reads the stored edges straight back instead, which is how
    you see what the series cap is actually removing.
    """
    if capped:
        return [
            Neighbour(item.score, item.rom.id, item.reasons)
            for item in similar_roms(rom_id, limit=limit, permissions=_UNRESTRICTED)
        ]

    return [
        Neighbour(edge.score, edge.rom_id, edge.reasons)
        for edge in db_recommendation_handler.get_similar_rom_edges(rom_id, limit=limit)
    ]


def print_rom(
    rom_id: int, info: dict[int, RomInfo], limit: int, capped: bool = True
) -> None:
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

    edges = neighbours_of(rom_id, limit, capped)
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

    feed = recommended_roms(
        user.id,
        limit=limit,
        permissions=resolve_permissions(user),
        refresh=True,
    )
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


def gather_stats() -> dict[str, Any]:
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

    facet_counts: Counter[str] = Counter()
    for (reasons,) in reason_rows:
        for reason in reasons or ():
            facet_counts[str(reason.get("facet"))] += 1

    return {
        "total_roms": total_roms,
        "edges": edges,
        "covered": covered,
        "coverage": (covered / total_roms * 100) if total_roms else 0.0,
        "avg_edges": (edges / covered) if covered else 0.0,
        "score_bounds": score_bounds,
        "facet_counts": facet_counts,
    }


def print_stats() -> None:
    stats = gather_stats()
    total_roms = stats["total_roms"]
    edges = stats["edges"]
    covered = stats["covered"]
    score_bounds = stats["score_bounds"]
    facet_counts = stats["facet_counts"]

    print()
    print("=" * 78)
    print("Index health")
    print("-" * 78)
    print(f"  roms in library      {total_roms:>10,}")
    print(
        f"  roms with neighbours {covered:>10,}"
        f"  ({stats['coverage']:.1f}% coverage)"
    )
    print(f"  edges                {edges:>10,}")
    if covered:
        print(f"  avg edges per rom    {stats['avg_edges']:>10.1f}")
    if score_bounds and score_bounds[0] is not None:
        print(
            f"  score min/avg/max    "
            f"{score_bounds[0]:.3f} / {float(score_bounds[1]):.3f} / {score_bounds[2]:.3f}"
        )

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


REPORT_CSS = """
:root { color-scheme: light dark; --bg: #fff; --fg: #1a1a1a; --dim: #666;
        --line: #e3e3e3; --card: #fafafa; --accent: #2f6f4f; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #131316; --fg: #e8e8ea; --dim: #9a9aa2; --line: #2a2a30;
          --card: #1b1b20; --accent: #6fcf97; }
}
* { box-sizing: border-box; }
body { margin: 0 auto; padding: 2rem 1.25rem 4rem; max-width: 60rem; background: var(--bg);
       color: var(--fg); font: 15px/1.55 ui-sans-serif, system-ui, sans-serif; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
h2 { font-size: 1.05rem; margin: 0 0 .1rem; }
.sub { color: var(--dim); font-size: .85rem; margin: 0 0 2rem; }
.health { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
          gap: .75rem; margin: 0 0 1rem; }
.health div { background: var(--card); border: 1px solid var(--line);
              border-radius: .5rem; padding: .6rem .75rem; }
.health b { display: block; font-size: 1.2rem; font-variant-numeric: tabular-nums; }
.health span { color: var(--dim); font-size: .75rem; text-transform: uppercase;
               letter-spacing: .04em; }
.game { border: 1px solid var(--line); border-radius: .5rem; margin: 0 0 1rem;
        overflow: hidden; }
.game > header { background: var(--card); padding: .7rem .9rem;
                 border-bottom: 1px solid var(--line); }
.plat { color: var(--dim); font-weight: 400; font-size: .85rem; }
.facets { color: var(--dim); font-size: .8rem; margin: .2rem 0 0; }
table { width: 100%; border-collapse: collapse; }
td { padding: .4rem .9rem; border-top: 1px solid var(--line); vertical-align: top; }
tr:first-child td { border-top: 0; }
.score { font-variant-numeric: tabular-nums; color: var(--accent); width: 4.5rem;
         font-weight: 600; }
.why { color: var(--dim); font-size: .8rem; }
.none { padding: .7rem .9rem; color: var(--dim); font-size: .85rem; }
.bars { margin: 0 0 2rem; }
.bars tr td { border: 0; padding: .15rem .5rem .15rem 0; }
.bar { background: var(--accent); height: .55rem; border-radius: .3rem; display: block; }
footer { color: var(--dim); font-size: .8rem; margin-top: 2.5rem;
         border-top: 1px solid var(--line); padding-top: 1rem; }
"""


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def write_report(
    path: str,
    rom_ids: list[int],
    info: dict[int, RomInfo],
    limit: int,
    capped: bool,
    command: str,
) -> None:
    """Write the sampled games to a self-contained HTML page.

    The terminal output is for the person running the tool; this is for
    sending to someone who has not got the library.
    """
    stats = gather_stats()
    out: list[str] = [
        "<!doctype html><html lang=en><head><meta charset=utf-8>",
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>RomM recommendations sample</title>",
        f"<style>{REPORT_CSS}</style></head><body>",
        "<h1>RomM recommendations sample</h1>",
        f"<p class=sub>{len(rom_ids)} games, "
        f"{'capped as the UI renders them' if capped else 'raw index, uncapped'}. "
        f"Reproduce with <code>{esc(command)}</code></p>",
        "<div class=health>",
        f"<div><span>Library</span><b>{stats['total_roms']:,}</b></div>",
        f"<div><span>Coverage</span><b>{stats['coverage']:.1f}%</b></div>",
        f"<div><span>Edges</span><b>{stats['edges']:,}</b></div>",
        f"<div><span>Edges per game</span><b>{stats['avg_edges']:.1f}</b></div>",
        "</div>",
    ]

    facet_counts = stats["facet_counts"]
    if facet_counts:
        total = sum(facet_counts.values())
        out.append("<table class=bars>")
        for facet, count in facet_counts.most_common():
            share = count / total * 100
            out.append(
                f"<tr><td class=why>{esc(facet)}</td>"
                f"<td class=why>{share:.1f}%</td>"
                f"<td style='width:60%'><span class=bar "
                f"style='width:{share:.1f}%'></span></td></tr>"
            )
        out.append("</table>")

    for rom_id in rom_ids:
        source = info.get(rom_id)
        name = esc(source.name if source else f"rom {rom_id}")
        platform = esc(source.platform if source else "?")
        facets = load_facets(rom_id)
        summary = " · ".join(
            f"{key}={', '.join(values)}" for key, values in facets.items() if values
        )
        out.append(
            f"<section class=game><header><h2>{name} "
            f"<span class=plat>({platform})</span></h2>"
            f"<p class=facets>{esc(summary) or 'no metadata facets'}</p></header>"
        )

        edges = neighbours_of(rom_id, limit, capped)
        if not edges:
            out.append("<p class=none>No neighbours.</p></section>")
            continue

        neighbour_info = load_rom_info([edge.rom_id for edge in edges])
        out.append("<table>")
        for edge in edges:
            neighbour = neighbour_info.get(edge.rom_id)
            label = esc(neighbour.name if neighbour else f"rom {edge.rom_id}")
            plat = esc(neighbour.platform if neighbour else "?")
            out.append(
                f"<tr><td class=score>{edge.score:.3f}</td>"
                f"<td>{label} <span class=plat>({plat})</span></td>"
                f"<td class=why>{esc(format_reasons(edge.reasons))}</td></tr>"
            )
        out.append("</table></section>")

    out.append(
        "<footer>Games are sampled at random from the indexed library, not chosen. "
        "Pass the same <code>--seed</code> against your own library to generate "
        "the equivalent page for a shelf this tool has never seen.</footer>"
    )
    out.append("</body></html>")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out))

    print(f"\nWrote {path}")


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
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Show the uncapped index instead of what the UI would render",
    )
    parser.add_argument(
        "--report",
        metavar="PATH",
        help="Also write the sample to a self-contained HTML page",
    )
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
        print_rom(rom_id, info, args.limit, capped=not args.raw)

    print()
    print_stats()

    if args.report:
        # The report path is whatever the reader chooses, so it is replaced
        # rather than echoed: the point of the line is the sampling flags.
        flags: list[str] = []
        skip_next = False
        for arg in sys.argv[1:]:
            if skip_next:
                skip_next = False
                continue
            if arg == "--report":
                skip_next = True
                continue
            if arg.startswith("--report="):
                continue
            flags.append(arg)

        write_report(
            args.report,
            rom_ids,
            info,
            args.limit,
            capped=not args.raw,
            command=shlex.join(
                ["uv", "run", "tools/inspect_recommendations.py", *flags]
                + ["--report", "out.html"]
            ),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

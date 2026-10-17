#!/usr/bin/env python3
"""Time the two statements behind one gallery window, with EXPLAIN (ANALYZE).

A window fetch runs two statements: one picks the page's ids, the next loads
those rows. This builds both the way GET /api/roms does and prints each one's
execution time plus the plan nodes that spend the most of it, so a change to
the grouped query can be compared before and after without the browser.

Read-only: it opens a READ ONLY transaction and only runs EXPLAIN on SELECTs.
PostgreSQL only. Run from the backend directory:

    uv run tools/explain_gallery_query.py
    uv run tools/explain_gallery_query.py --offset 90000 --repeat 3
    uv run tools/explain_gallery_query.py --work-mem 32MB --plan
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Any

# Allow running as `python3 tools/explain_gallery_query.py` from backend/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import Select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from handler.database import db_rom_handler  # noqa: E402
from handler.database.base_handler import sync_session  # noqa: E402
from handler.database.rom_filters import RomFilterParams  # noqa: E402
from models.rom import Rom  # noqa: E402

TOP_NODES = 5


def _compile(session: Session, statement: Select[Any]) -> str:
    """The statement as SQL with its values inlined, ready for EXPLAIN."""
    dialect = session.get_bind().dialect
    return str(
        statement.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
    )


def _explain(session: Session, sql: str) -> dict[str, Any]:
    """Run EXPLAIN (ANALYZE, BUFFERS) and return the plan document."""
    row: Any = session.execute(
        text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}")
    ).scalar_one()
    document = json.loads(row) if isinstance(row, str) else row
    plan: dict[str, Any] = document[0]
    return plan


def _own_times(node: dict[str, Any], out: list[tuple[float, str]]) -> float:
    """Collect each node's own time (its time minus its children's); return its total."""
    total = float(node.get("Actual Total Time", 0.0)) * float(
        node.get("Actual Loops", 1)
    )
    children = sum(_own_times(child, out) for child in node.get("Plans", []))
    label = node["Node Type"]
    if "Relation Name" in node:
        label += f" on {node['Relation Name']}"
    if "Index Name" in node:
        label += f" using {node['Index Name']}"
    out.append((total - children, label))
    return total


def _report(name: str, plans: list[dict[str, Any]], show_plan: bool) -> float:
    times = [plan["Execution Time"] for plan in plans]
    print(f"\n{name}")
    print(
        f"  execution  min {min(times):.1f} ms   median {statistics.median(times):.1f} ms"
        f"   ({len(times)} runs)"
    )
    nodes: list[tuple[float, str]] = []
    _own_times(plans[-1]["Plan"], nodes)
    for own, label in sorted(nodes, reverse=True)[:TOP_NODES]:
        print(f"    {own:8.1f} ms  {label}")
    if show_plan:
        print(json.dumps(plans[-1]["Plan"], indent=2))
    return float(statistics.median(times))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--order-by", default="name")
    parser.add_argument("--order-dir", default="asc")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=72)
    parser.add_argument(
        "--ungrouped",
        action="store_true",
        help="Leave siblings uncollapsed, to see the cost grouping adds.",
    )
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument(
        "--work-mem", help="Session work_mem for the run, e.g. 32MB (an experiment)."
    )
    parser.add_argument("--plan", action="store_true", help="Print the last full plan.")
    args = parser.parse_args()

    filters = RomFilterParams(group_by_meta_id=not args.ungrouped)
    unfiltered_query, sort_key = db_rom_handler.get_roms_query(
        user_id=args.user_id, order_by=args.order_by, order_dir=args.order_dir
    )
    # The same flags the endpoint passes for a window without `with_files`.
    query = db_rom_handler.filter_roms(
        query=unfiltered_query,
        filters=filters,
        sort_key=sort_key,
        order_by=args.order_by,
        order_dir=args.order_dir,
        user_id=args.user_id,
        include_file_stats=True,
        include_siblings=False,
        include_notes=False,
    )

    with sync_session.begin() as session:
        if session.get_bind().dialect.name != "postgresql":
            print("This tool runs on PostgreSQL only.", file=sys.stderr)
            return 1
        session.execute(text("SET TRANSACTION READ ONLY"))
        if args.work_mem:
            session.execute(
                text("SELECT set_config('work_mem', :v, true)"), {"v": args.work_mem}
            )
        database: str = session.execute(text("SELECT current_database()")).scalar_one()
        print(
            f"database {database}, user {args.user_id}, order {args.order_by} "
            f"{args.order_dir}, window {args.offset}+{args.limit}, "
            f"grouping {'off' if args.ungrouped else 'on'}"
        )

        ids_statement = (
            query.with_only_columns(Rom.id).offset(args.offset).limit(args.limit)
        )
        page_ids = list(session.scalars(ids_statement).all())
        if not page_ids:
            print("The window is empty: is the database seeded?", file=sys.stderr)
            return 1

        ids_sql = _compile(session, ids_statement)
        ids_plans = [_explain(session, ids_sql) for _ in range(args.repeat)]
        total = _report("1. page ids", ids_plans, args.plan)

        load_statement = query.where(Rom.id.in_(page_ids)).order_by(None)
        load_sql = _compile(session, load_statement)
        load_plans = [_explain(session, load_sql) for _ in range(args.repeat)]
        total += _report("2. load rows by id", load_plans, args.plan)

        print(f"\nboth statements, median total: {total:.1f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Time the statements behind one gallery window, with EXPLAIN (ANALYZE).

A window fetch picks the page's ids, then loads those rows plus one follow-up
query per eager-loaded relationship. This runs them the way GET /api/roms does
for the given user, then prints each one's execution time and the plan nodes
that spend the most of it, so a change to the grouped query can be compared
before and after without the browser.

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
import re
import statistics
import sys
from collections.abc import Callable
from typing import Any

# Allow running as `python3 tools/explain_gallery_query.py` from backend/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import event, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from handler.database import db_rom_handler, db_user_handler  # noqa: E402

# Imported after handler.database, which it would otherwise import half-built.
from handler.auth.permissions import resolve_permissions  # noqa: E402  # isort: skip
from handler.database.base_handler import sync_session  # noqa: E402
from handler.database.rom_filters import RomFilterParams  # noqa: E402
from models.rom import Rom  # noqa: E402

TOP_NODES = 5
SELECTED_TABLE = re.compile(r"^\s*SELECT\s+(\w+)\.", re.IGNORECASE)

Captured = tuple[str, Any]


def _capture(session: Session, run: Callable[[], object]) -> list[Captured]:
    """Every (statement, parameters) the driver receives while `run` executes."""
    captured: list[Captured] = []

    def record(*args: Any) -> None:
        # (conn, cursor, statement, parameters, context, executemany)
        captured.append((args[2], args[3]))

    connection = session.connection()
    event.listen(connection, "before_cursor_execute", record)
    try:
        run()
    finally:
        event.remove(connection, "before_cursor_execute", record)
    return captured


def _explain(session: Session, captured: Captured) -> dict[str, Any]:
    """Run EXPLAIN (ANALYZE, BUFFERS) on a captured statement and return the plan."""
    statement, parameters = captured
    row: Any = (
        session.connection()
        .exec_driver_sql(
            f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {statement}", parameters
        )
        .scalar_one()
    )
    document = json.loads(row) if isinstance(row, str) else row
    plan: dict[str, Any] = document[0]
    return plan


def _own_times(
    node: dict[str, Any], out: list[tuple[float, str]], processes: int = 1
) -> float:
    """Collect each node's own time (its time minus its children's); return its total."""
    # Under a Gather, loops count every worker while times average per loop,
    # so dividing by the process count keeps the total in wall-clock terms.
    loops = float(node.get("Actual Loops", 1))
    total = float(node.get("Actual Total Time", 0.0)) * loops / processes
    if node["Node Type"] in ("Gather", "Gather Merge"):
        processes = int(node.get("Workers Launched", 0)) + 1
    children = sum(_own_times(child, out, processes) for child in node.get("Plans", []))
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


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {number}")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument(
        "--order-by", default="", help="Empty is the endpoint's default (relevance)."
    )
    parser.add_argument("--order-dir", default="asc")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=72)
    parser.add_argument(
        "--ungrouped",
        action="store_true",
        help="Leave siblings uncollapsed, to see the cost grouping adds.",
    )
    parser.add_argument(
        "--filters",
        default="{}",
        help='RomFilterParams as JSON, e.g. \'{"search_term": "astral"}\' or \'{"genres": ["Sport"]}\'.',
    )
    parser.add_argument("--repeat", type=_positive_int, default=3)
    parser.add_argument(
        "--work-mem", help="Session work_mem for the run, e.g. 32MB (an experiment)."
    )
    parser.add_argument("--plan", action="store_true", help="Print the last full plan.")
    args = parser.parse_args()

    # JSON overrides the grouped default; --ungrouped overrides both.
    params = {"group_by_meta_id": True, **json.loads(args.filters)}
    if args.ungrouped:
        params["group_by_meta_id"] = False
    filters = RomFilterParams(**params)
    # The endpoint lowercases both before building the query.
    order_by = args.order_by.lower()
    order_dir = args.order_dir.lower()
    user = db_user_handler.get_user(args.user_id)
    if user is None:
        print(f"No user with id {args.user_id}.", file=sys.stderr)
        return 1
    visibility = resolve_permissions(user).rom_visibility
    unfiltered_query, sort_key = db_rom_handler.get_roms_query(
        user_id=args.user_id,
        order_by=order_by,
        order_dir=order_dir,
        search_term=filters.search_term,
    )
    query = db_rom_handler.filter_roms(
        query=unfiltered_query,
        filters=filters,
        sort_key=sort_key,
        order_by=order_by,
        order_dir=order_dir,
        user_id=args.user_id,
        include_related=False,
        visibility=visibility,
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
            f"database {database}, user {args.user_id}, "
            f"order {order_by or 'default'} "
            f"{order_dir}, window {args.offset}+{args.limit}, "
            f"grouping {'off' if args.ungrouped else 'on'}, filters {args.filters}"
        )

        ids_statement = (
            query.with_only_columns(Rom.id).offset(args.offset).limit(args.limit)
        )
        page_ids: list[int] = []
        captured = _capture(
            session, lambda: page_ids.extend(session.scalars(ids_statement).all())
        )
        if not page_ids:
            print("The window is empty: is the database seeded?", file=sys.stderr)
            return 1

        load_statement = db_rom_handler.get_page_rows_query(
            page_ids, visibility=visibility, include_file_stats=True
        )
        rows, *loaders = _capture(
            session, lambda: session.scalars(load_statement).all()
        )
        steps = [("1. page ids", captured[0]), ("2. load rows by id", rows)]
        for index, loader in enumerate(loaders, start=1):
            table = SELECTED_TABLE.search(loader[0])
            label = table.group(1) if table else "?"
            steps.append((f"2.{index} eager load of {label}", loader))

        total = 0.0
        for name, statement in steps:
            plans = [_explain(session, statement) for _ in range(args.repeat)]
            total += _report(name, plans, args.plan)

        print(f"\nall {len(steps)} statements, median total: {total:.1f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

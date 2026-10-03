"""Regenerate handler/easyrpg/rtp_table.json from EasyRPG Player's RTP table."""

import json
import re
import sys
from pathlib import Path

from handler.easyrpg import normalize_name

ROW_RE = re.compile(r"^\s*\{(.*)\},\s*$")
CELL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|nullptr')
OUTPUT = Path(__file__).parent.parent / "handler" / "easyrpg" / "rtp_table.json"
USAGE = "usage: uv run python -m tools.generate_easyrpg_rtp_table <Player>/src/rtp_table.cpp"


def parse_rows(source: str) -> dict[str, list[list[str]]]:
    table: dict[str, list[list[str]]] = {}
    seen: set[tuple[str, ...]] = set()
    for line in source.splitlines():
        match = ROW_RE.match(line)
        if not match:
            continue
        cells = [m.group(1) for m in CELL_RE.finditer(match.group(1))]
        # Category and name tables have a single column.
        if len(cells) < 3 or cells[0] is None:
            continue
        category, *names = cells
        aliases = list(dict.fromkeys(normalize_name(name) for name in names if name))
        key = (category, *aliases)
        if key in seen:
            continue
        seen.add(key)
        table.setdefault(category, []).append(aliases)
    return table


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(USAGE)
    table = parse_rows(Path(sys.argv[1]).read_text(encoding="utf-8"))
    OUTPUT.write_text(
        json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {sum(len(rows) for rows in table.values())} rows to {OUTPUT}")


if __name__ == "__main__":
    main()

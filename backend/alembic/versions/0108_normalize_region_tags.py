"""Collapse region tags onto their canonical spelling

``parse_tags`` only normalized regions written as a shortcode. A region written
as a name was stored with whatever casing the filename used, and a "Reg-"
prefixed code that was not in the shortcode table was stored verbatim, so one
library could hold "USA", "usa", "Usa" and "US" as four separate values. Each
became its own entry in the filter dropdowns and its own bucket in the platform
stats. The parser now resolves every spelling to a canonical name; this rewrites
the rows scanned before it did.

``roms_facets.regions`` mirrors ``roms.regions`` through the triggers added in
0100, so updating ``roms`` is enough to fix the dropdowns too.

Revision ID: 0108_normalize_region_tags
Revises: 0107_roms_dedup_cover_index
Create Date: 2026-08-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0108_normalize_region_tags"
down_revision = "0107_roms_dedup_cover_index"
branch_labels = None
depends_on = None

# Frozen copy of the resolver in handler/filesystem/base_handler.py. Inlined so
# later edits to that table can't retroactively change what this migration did.
_CANONICAL_REGIONS = (
    "Australia",
    "Asia",
    "Brazil",
    "Canada",
    "China",
    "Europe",
    "France",
    "Finland",
    "Germany",
    "Greece",
    "Holland",
    "Hong Kong",
    "Italy",
    "Japan",
    "Korea",
    "Netherlands",
    "Norway",
    "Public Domain",
    "Russia",
    "Spain",
    "Sweden",
    "Taiwan",
    "USA",
    "England",
    "Unknown",
    "Unlicensed",
    "World",
)

_REGION_ALIASES = {
    "A": "Australia",
    "AS": "Asia",
    "B": "Brazil",
    "BRA": "Brazil",
    "C": "Canada",
    "CH": "China",
    "CHN": "China",
    "E": "Europe",
    "EU": "Europe",
    "EUR": "Europe",
    "F": "France",
    "FN": "Finland",
    "G": "Germany",
    "GLOBAL": "World",
    "GR": "Greece",
    "H": "Holland",
    "HK": "Hong Kong",
    "I": "Italy",
    "J": "Japan",
    "JP": "Japan",
    "K": "Korea",
    "NL": "Netherlands",
    "NO": "Norway",
    "PD": "Public Domain",
    "R": "Russia",
    "S": "Spain",
    "SW": "Sweden",
    "T": "Taiwan",
    "U": "USA",
    "UK": "England",
    "UNK": "Unknown",
    "UNL": "Unlicensed",
    "US": "USA",
    "W": "World",
    "WR": "World",
}

_REGION_BY_ALIAS = {
    **{name.lower(): name for name in _CANONICAL_REGIONS},
    **{alias.lower(): name for alias, name in _REGION_ALIASES.items()},
}

# Minimal projections; the real models carry much more.
_roms = sa.table(
    "roms",
    sa.column("id", sa.Integer),
    sa.column("regions", CustomJSON()),
)

# Smart collections match their saved region list against `roms.regions` with
# JSON containment, so a criteria value left as "US" would match nothing once
# the rows above become "USA". Rewriting both keeps saved collections working.
_smart_collections = sa.table(
    "smart_collections",
    sa.column("id", sa.Integer),
    sa.column("filter_criteria", CustomJSON()),
)


def _normalize(regions: list) -> list[str]:
    """Canonicalize a region list, dropping duplicates but keeping order."""
    normalized: list[str] = []
    for region in regions:
        if not isinstance(region, str):
            continue
        # Unknown values are kept as-is: a bare code we don't recognize is
        # still the only region information that ROM has.
        resolved = _REGION_BY_ALIAS.get(region.strip().lower(), region)
        if resolved not in normalized:
            normalized.append(resolved)
    return normalized


def _execute_in_chunks(connection, statement, updates: list[dict]) -> None:
    for chunk_start in range(0, len(updates), 1000):
        connection.execute(statement, updates[chunk_start : chunk_start + 1000])


def _upgrade_roms(connection) -> None:
    rows = connection.execute(
        sa.select(_roms.c.id, _roms.c.regions).where(_roms.c.regions.is_not(None))
    ).fetchall()

    updates = []
    for rom_id, regions in rows:
        if not isinstance(regions, list):
            continue
        normalized = _normalize(regions)
        if normalized != regions:
            updates.append({"rom_id": rom_id, "new_regions": normalized})

    if not updates:
        return

    # Per-row values rule out a CASE expression, and the JSON bind keeps the
    # dialect differences (JSON vs JSONB) inside the type.
    _execute_in_chunks(
        connection,
        sa.update(_roms)
        .where(_roms.c.id == sa.bindparam("rom_id"))
        .values(regions=sa.bindparam("new_regions", type_=CustomJSON())),
        updates,
    )


def _upgrade_smart_collections(connection) -> None:
    rows = connection.execute(
        sa.select(_smart_collections.c.id, _smart_collections.c.filter_criteria)
    ).fetchall()

    updates = []
    for collection_id, criteria in rows:
        if not isinstance(criteria, dict) or not isinstance(
            criteria.get("regions"), list
        ):
            continue
        normalized = _normalize(criteria["regions"])
        if normalized != criteria["regions"]:
            updates.append(
                {
                    "collection_id": collection_id,
                    "new_criteria": {**criteria, "regions": normalized},
                }
            )

    if not updates:
        return

    _execute_in_chunks(
        connection,
        sa.update(_smart_collections)
        .where(_smart_collections.c.id == sa.bindparam("collection_id"))
        .values(filter_criteria=sa.bindparam("new_criteria", type_=CustomJSON())),
        updates,
    )


def upgrade() -> None:
    connection = op.get_bind()

    _upgrade_roms(connection)
    _upgrade_smart_collections(connection)


def downgrade() -> None:
    # The pre-normalization spellings came from filenames that were not
    # recorded, so the old values can't be reconstructed. A rescan rebuilds
    # them under whichever parser is in place.
    pass

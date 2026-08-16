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

# Both spellings of the criteria key. Early versions stored a single value
# under `selected_region`, and `get_smart_collection_criteria` still reads it.
_CRITERIA_KEYS = ("regions", "selected_region")

# Rows held in memory at once. The roms pass walks the table by id rather than
# materializing it, so a large library can't balloon startup memory.
_BATCH_SIZE = 1000


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


def _normalize_criteria(criteria: dict) -> dict | None:
    """Canonicalize a criteria blob, or return None if nothing changed.

    Handles both the list-valued key and the scalar `selected_*` one, keeping
    each value's original shape so the reader sees what it expects.
    """
    updated = dict(criteria)
    changed = False

    for key in _CRITERIA_KEYS:
        value = updated.get(key)
        if isinstance(value, list):
            normalized: list | str = _normalize(value)
        elif isinstance(value, str):
            resolved = _normalize([value])
            normalized = resolved[0] if resolved else value
        else:
            continue

        if normalized != value:
            updated[key] = normalized
            changed = True

    return updated if changed else None


def _upgrade_roms(connection) -> None:
    # Walked by id in batches: a library can hold millions of rows, and this
    # runs at startup.
    statement = (
        sa.update(_roms).where(_roms.c.id == sa.bindparam("rom_id"))
        # Per-row values rule out a CASE expression, and the JSON bind keeps
        # the dialect differences (JSON vs JSONB) inside the type.
        .values(regions=sa.bindparam("new_regions", type_=CustomJSON()))
    )

    last_id = -1
    while True:
        rows = connection.execute(
            sa.select(_roms.c.id, _roms.c.regions)
            .where(_roms.c.regions.is_not(None), _roms.c.id > last_id)
            .order_by(_roms.c.id)
            .limit(_BATCH_SIZE)
        ).fetchall()

        if not rows:
            return

        last_id = rows[-1][0]

        updates = []
        for rom_id, regions in rows:
            if not isinstance(regions, list):
                continue
            normalized = _normalize(regions)
            if normalized != regions:
                updates.append({"rom_id": rom_id, "new_regions": normalized})

        if updates:
            connection.execute(statement, updates)


def _upgrade_smart_collections(connection) -> None:
    # Not batched: one row per user-created collection, so this is tens of rows.
    rows = connection.execute(
        sa.select(_smart_collections.c.id, _smart_collections.c.filter_criteria)
    ).fetchall()

    updates = []
    for collection_id, criteria in rows:
        if not isinstance(criteria, dict):
            continue
        normalized_criteria = _normalize_criteria(criteria)
        if normalized_criteria is not None:
            updates.append(
                {"collection_id": collection_id, "new_criteria": normalized_criteria}
            )

    if not updates:
        return

    connection.execute(
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

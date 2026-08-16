"""Collapse language tags onto their canonical spelling

The language half of what 0108 fixed for regions: ``parse_tags`` normalized a
language written as a shortcode but stored one written as a name with whatever
casing the filename used, so "English" and "english" became two filter entries.
The parser now resolves both, and every shortcode regardless of case; this
rewrites the rows scanned before it did.

``roms_facets.languages`` mirrors ``roms.languages`` through the triggers added
in 0100, so updating ``roms`` is enough.

Revision ID: 0109_normalize_language_tags
Revises: 0108_normalize_region_tags
Create Date: 2026-08-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0109_normalize_language_tags"
down_revision = "0108_normalize_region_tags"
branch_labels = None
depends_on = None

# Frozen copy of the LANGUAGES table in handler/filesystem/base_handler.py.
# Inlined so later edits to that table can't retroactively change what this
# migration did.
_LANGUAGES = (
    ("Ar", "Arabic"),
    ("Da", "Danish"),
    ("De", "German"),
    ("El", "Greek"),
    ("En", "English"),
    ("Es", "Spanish"),
    ("Fi", "Finnish"),
    ("Fr", "French"),
    ("It", "Italian"),
    ("Ja", "Japanese"),
    ("Ko", "Korean"),
    ("Nl", "Dutch"),
    ("No", "Norwegian"),
    ("Pl", "Polish"),
    ("Pt", "Portuguese"),
    ("Ru", "Russian"),
    ("Sr", "Serbian"),
    ("Sv", "Swedish"),
    ("Zh", "Chinese"),
    ("nolang", "No Language"),
)

# Names only, which is complete: the old parser resolved shortcodes to a name
# before storing, so every value here is already a name, just possibly in the
# filename's casing. Mapping codes as well would also mean guessing at "No",
# which reads as Norwegian in this column and Norway in `regions`.
_LANGUAGE_BY_NAME = {name.lower(): name for _, name in _LANGUAGES}

# Minimal projections; the real models carry much more.
_roms = sa.table(
    "roms",
    sa.column("id", sa.Integer),
    sa.column("languages", CustomJSON()),
)

# Smart collections match their saved language list against `roms.languages`
# with JSON containment, so a criteria value left as "english" would match
# nothing once the rows above become "English".
_smart_collections = sa.table(
    "smart_collections",
    sa.column("id", sa.Integer),
    sa.column("filter_criteria", CustomJSON()),
)

# Both spellings of the criteria key. Early versions stored a single value
# under `selected_language`, and `get_smart_collection_criteria` still reads it.
_CRITERIA_KEYS = ("languages", "selected_language")

# Rows held in memory at once. The roms pass walks the table by id rather than
# materializing it, so a large library can't balloon startup memory.
_BATCH_SIZE = 1000


def _normalize(languages: list) -> list[str]:
    """Canonicalize a language list, dropping duplicates but keeping order."""
    normalized: list[str] = []
    for language in languages:
        if not isinstance(language, str):
            continue
        resolved = _LANGUAGE_BY_NAME.get(language.strip().lower(), language)
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
        .values(languages=sa.bindparam("new_languages", type_=CustomJSON()))
    )

    last_id = -1
    while True:
        rows = connection.execute(
            sa.select(_roms.c.id, _roms.c.languages)
            .where(_roms.c.languages.is_not(None), _roms.c.id > last_id)
            .order_by(_roms.c.id)
            .limit(_BATCH_SIZE)
        ).fetchall()

        if not rows:
            return

        last_id = rows[-1][0]

        updates = []
        for rom_id, languages in rows:
            if not isinstance(languages, list):
                continue
            normalized = _normalize(languages)
            if normalized != languages:
                updates.append({"rom_id": rom_id, "new_languages": normalized})

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

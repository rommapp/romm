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


def _execute_in_chunks(connection, statement, updates: list[dict]) -> None:
    for chunk_start in range(0, len(updates), 1000):
        connection.execute(statement, updates[chunk_start : chunk_start + 1000])


def _upgrade_roms(connection) -> None:
    rows = connection.execute(
        sa.select(_roms.c.id, _roms.c.languages).where(_roms.c.languages.is_not(None))
    ).fetchall()

    updates = []
    for rom_id, languages in rows:
        if not isinstance(languages, list):
            continue
        normalized = _normalize(languages)
        if normalized != languages:
            updates.append({"rom_id": rom_id, "new_languages": normalized})

    if not updates:
        return

    # Per-row values rule out a CASE expression, and the JSON bind keeps the
    # dialect differences (JSON vs JSONB) inside the type.
    _execute_in_chunks(
        connection,
        sa.update(_roms)
        .where(_roms.c.id == sa.bindparam("rom_id"))
        .values(languages=sa.bindparam("new_languages", type_=CustomJSON())),
        updates,
    )


def _upgrade_smart_collections(connection) -> None:
    rows = connection.execute(
        sa.select(_smart_collections.c.id, _smart_collections.c.filter_criteria)
    ).fetchall()

    updates = []
    for collection_id, criteria in rows:
        if not isinstance(criteria, dict) or not isinstance(
            criteria.get("languages"), list
        ):
            continue
        normalized = _normalize(criteria["languages"])
        if normalized != criteria["languages"]:
            updates.append(
                {
                    "collection_id": collection_id,
                    "new_criteria": {**criteria, "languages": normalized},
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

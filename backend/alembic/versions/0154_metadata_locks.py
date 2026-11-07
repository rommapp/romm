"""Store metadata lock snapshots and project locked facets

Revision ID: 0154_metadata_locks
Revises: 0153_play_permissions
Create Date: 2026-09-15 00:00:00.000000

"""

from alembic import op

from utils.database import is_postgresql
from utils.roms_columns import (
    ROMS_METADATA_VIEW_COLUMNS,
    VIEW,
    ensure_roms_columns,
    roms_metadata_view_sql,
)

revision = "0154_metadata_locks"
down_revision = "0153_play_permissions"
branch_labels = None
depends_on = None

_LOCKED_ARRAY_FIELDS = (
    "genres",
    "franchises",
    "collections",
    "companies",
    "game_modes",
    "age_ratings",
)
_FACET_FIELDS = (*_LOCKED_ARRAY_FIELDS, "player_count")
VIRTUAL_COLLECTION_FIELDS = (
    ("genre", "genres", "generated_genres"),
    ("franchise", "franchises", "generated_franchises"),
    ("collection", "collections", "generated_collections"),
    ("company", "companies", "generated_companies"),
    ("mode", "game_modes", "generated_game_modes"),
    ("publisher", None, "generated_publishers"),
    ("developer", None, "generated_developers"),
)
_VIRTUAL_COLLECTION_LOCK_KEYS = tuple(
    field for _, field, _ in VIRTUAL_COLLECTION_FIELDS if field is not None
) + ("cover",)
_VIRTUAL_COLLECTION_COLUMNS = (
    "rom_id, type, name, path_cover_s, path_cover_l, created_at, updated_at"
)
_VIRTUAL_COLLECTION_NAME_MAX_LENGTH = 400


def _locked_array_value(pg: bool, field: str, generated: str) -> str:
    if pg:
        return (
            f"CASE WHEN NEW.metadata_locks ? '{field}' "
            f"THEN NEW.metadata_locks -> '{field}' ELSE NEW.{generated} END"
        )
    return (
        f"CASE WHEN JSON_CONTAINS_PATH(NEW.metadata_locks, 'one', '$.{field}') "
        f"THEN JSON_EXTRACT(NEW.metadata_locks, '$.{field}') "
        f"ELSE NEW.{generated} END"
    )


def _locked_facet_value(pg: bool, field: str, generated: str) -> str:
    if field in _LOCKED_ARRAY_FIELDS:
        return _locked_array_value(pg, field, generated)
    if pg:
        return (
            f"CASE WHEN NEW.metadata_locks ? '{field}' "
            f"THEN NEW.metadata_locks ->> '{field}' ELSE NEW.{generated} END"
        )
    value = f"JSON_UNQUOTE(JSON_EXTRACT(NEW.metadata_locks, '$.{field}'))"
    return (
        f"CASE WHEN JSON_CONTAINS_PATH(NEW.metadata_locks, 'one', '$.{field}') "
        f"THEN NULLIF({value}, 'null') ELSE NEW.{generated} END"
    )


def _facet_sync_sql(pg: bool, *, insert: bool = False) -> str:
    assignments = ",\n        ".join(
        f"{field} = {_locked_facet_value(pg, field, f'generated_{field}')}"
        for field in _FACET_FIELDS
    )
    if pg:
        keys = ", ".join(f"'{field}'" for field in _FACET_FIELDS)
        return f"""
CREATE OR REPLACE FUNCTION romm_sync_locked_facets() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.metadata_locks ?| ARRAY[{keys}] THEN
        UPDATE roms_facets SET
        {assignments}
        WHERE rom_id = NEW.id;
    END IF;
    RETURN NULL;
END $$
"""

    paths = ", ".join(f"'$.{field}'" for field in _FACET_FIELDS)
    timing = "INSERT" if insert else "UPDATE"
    trigger = (
        "zz_roms_facets_locked_after_insert"
        if insert
        else "zz_roms_facets_locked_after_update"
    )
    legacy = "roms_facets_after_insert" if insert else "roms_facets_after_update"
    return f"""
CREATE TRIGGER {trigger} AFTER {timing} ON roms
FOR EACH ROW FOLLOWS {legacy}
BEGIN
    IF JSON_CONTAINS_PATH(NEW.metadata_locks, 'one', {paths}) THEN
        UPDATE roms_facets SET
        {assignments}
        WHERE rom_id = NEW.id;
    END IF;
END
"""


def _array_for_virtual_collection(pg: bool, field: str | None, generated: str) -> str:
    value = (
        f"NEW.{generated}"
        if field is None
        else _locked_array_value(pg, field, generated)
    )
    if pg:
        return (
            f"CASE WHEN jsonb_typeof({value}) = 'array' "
            f"THEN {value} ELSE '[]'::jsonb END"
        )
    return value


def _virtual_collection_rows(pg: bool) -> str:
    cover_small = (
        "CASE WHEN NEW.metadata_locks ? 'cover' "
        "THEN NEW.metadata_locks -> 'cover' ->> 'small' ELSE NEW.path_cover_s END"
        if pg
        else "CASE WHEN JSON_CONTAINS_PATH(NEW.metadata_locks, 'one', '$.cover') "
        "THEN CASE WHEN JSON_TYPE(JSON_EXTRACT(NEW.metadata_locks, '$.cover.small')) = 'NULL' "
        "THEN NULL ELSE JSON_UNQUOTE(JSON_EXTRACT(NEW.metadata_locks, '$.cover.small')) END "
        "ELSE NEW.path_cover_s END"
    )
    cover_large = (
        "CASE WHEN NEW.metadata_locks ? 'cover' "
        "THEN NEW.metadata_locks -> 'cover' ->> 'large' ELSE NEW.path_cover_l END"
        if pg
        else "CASE WHEN JSON_CONTAINS_PATH(NEW.metadata_locks, 'one', '$.cover') "
        "THEN CASE WHEN JSON_TYPE(JSON_EXTRACT(NEW.metadata_locks, '$.cover.large')) = 'NULL' "
        "THEN NULL ELSE JSON_UNQUOTE(JSON_EXTRACT(NEW.metadata_locks, '$.cover.large')) END "
        "ELSE NEW.path_cover_l END"
    )
    branches = []
    for type_, field, generated in VIRTUAL_COLLECTION_FIELDS:
        value = _array_for_virtual_collection(pg, field, generated)
        if pg:
            source = f"jsonb_array_elements_text({value}) AS j(value)"
        else:
            source = f"JSON_TABLE({value}, '$[*]' COLUMNS (value TEXT PATH '$')) j"
        branches.append(
            f"SELECT DISTINCT NEW.id, '{type_}', "
            f"LEFT(j.value, {_VIRTUAL_COLLECTION_NAME_MAX_LENGTH}), "
            f"{cover_small}, {cover_large}, NOW(), NOW()\n"
            f"FROM {source}\n"
            "WHERE j.value IS NOT NULL AND j.value != ''"
        )
    return "\nUNION ALL\n".join(branches)


def _virtual_collection_has_lock(pg: bool, row: str) -> str:
    if pg:
        keys = ", ".join(f"'{field}'" for field in _VIRTUAL_COLLECTION_LOCK_KEYS)
        return f"COALESCE({row}.metadata_locks ?| ARRAY[{keys}], FALSE)"
    paths = ", ".join(f"'$.{field}'" for field in _VIRTUAL_COLLECTION_LOCK_KEYS)
    return f"COALESCE(JSON_CONTAINS_PATH({row}.metadata_locks, 'one', {paths}), 0)"


def _virtual_collection_update_condition(pg: bool) -> str:
    sources = tuple(source for _, _, source in VIRTUAL_COLLECTION_FIELDS) + (
        "path_cover_s",
        "path_cover_l",
    )
    if pg:
        lock_changes = [
            f"NEW.metadata_locks -> '{field}' IS DISTINCT FROM "
            f"OLD.metadata_locks -> '{field}'"
            for field in _VIRTUAL_COLLECTION_LOCK_KEYS
        ]
        source_changes = [
            f"NEW.{source} IS DISTINCT FROM OLD.{source}" for source in sources
        ]
    else:
        lock_changes = [
            f"NOT (JSON_EXTRACT(NEW.metadata_locks, '$.{field}') <=> "
            f"JSON_EXTRACT(OLD.metadata_locks, '$.{field}'))"
            for field in _VIRTUAL_COLLECTION_LOCK_KEYS
        ]
        source_changes = [f"NOT (NEW.{source} <=> OLD.{source})" for source in sources]
    return (
        f"({' OR '.join(lock_changes)}) OR (({' OR '.join(source_changes)}) AND "
        f"({_virtual_collection_has_lock(pg, 'OLD')} OR "
        f"{_virtual_collection_has_lock(pg, 'NEW')}))"
    )


def _virtual_collection_rebuild_sql(pg: bool) -> str:
    insert = "INSERT INTO" if pg else "INSERT IGNORE INTO"
    conflict = "\nON CONFLICT DO NOTHING" if pg else ""
    return (
        "DELETE FROM virtual_collection_roms WHERE rom_id = NEW.id;\n"
        f"{insert} virtual_collection_roms ({_VIRTUAL_COLLECTION_COLUMNS})\n"
        f"{_virtual_collection_rows(pg)}{conflict};"
    )


def _virtual_collection_trigger_sql(pg: bool) -> str:
    rebuild = _virtual_collection_rebuild_sql(pg)
    if pg:
        return f"""
CREATE OR REPLACE FUNCTION romm_sync_locked_virtual_collections() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF {_virtual_collection_has_lock(True, "NEW")} THEN
            {rebuild}
        END IF;
    ELSIF {_virtual_collection_update_condition(True)} THEN
        {rebuild}
    END IF;
    RETURN NULL;
END $$
"""
    return f"""
CREATE TRIGGER zz_virtual_collection_roms_locked_after_update AFTER UPDATE ON roms
FOR EACH ROW FOLLOWS virtual_collection_roms_au
BEGIN
    IF {_virtual_collection_update_condition(False)} THEN
        {rebuild}
    END IF;
END
"""


def _virtual_collection_insert_trigger_sql() -> str:
    return f"""
CREATE TRIGGER zz_virtual_collection_roms_locked_after_insert AFTER INSERT ON roms
FOR EACH ROW FOLLOWS virtual_collection_roms_ai
BEGIN
    IF {_virtual_collection_has_lock(False, "NEW")} THEN
        {_virtual_collection_rebuild_sql(False)}
    END IF;
END
"""


def _install_lock_triggers(pg: bool) -> None:
    if pg:
        op.execute(_facet_sync_sql(True))
        op.execute("DROP TRIGGER IF EXISTS zz_roms_facets_locked_after_update ON roms")
        op.execute("DROP TRIGGER IF EXISTS zz_roms_facets_locked_after_insert ON roms")
        op.execute("DROP TRIGGER IF EXISTS zz_roms_facets_locked_after_write ON roms")
        op.execute(
            "CREATE TRIGGER zz_roms_facets_locked_after_write AFTER INSERT OR UPDATE ON roms "
            "FOR EACH ROW EXECUTE FUNCTION romm_sync_locked_facets()"
        )
        op.execute(_virtual_collection_trigger_sql(True))
        op.execute(
            "DROP TRIGGER IF EXISTS zz_virtual_collection_roms_locked_after_update ON roms"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS zz_virtual_collection_roms_locked_after_insert ON roms"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS zz_virtual_collection_roms_locked_after_write ON roms"
        )
        op.execute(
            "CREATE TRIGGER zz_virtual_collection_roms_locked_after_write "
            "AFTER INSERT OR UPDATE ON roms FOR EACH ROW "
            "EXECUTE FUNCTION romm_sync_locked_virtual_collections()"
        )
        return

    op.execute("DROP TRIGGER IF EXISTS zz_roms_facets_locked_after_update")
    op.execute("DROP TRIGGER IF EXISTS zz_roms_facets_locked_after_insert")
    op.execute(_facet_sync_sql(False, insert=True))
    op.execute(_facet_sync_sql(False))
    op.execute("DROP TRIGGER IF EXISTS zz_virtual_collection_roms_locked_after_update")
    op.execute("DROP TRIGGER IF EXISTS zz_virtual_collection_roms_locked_after_insert")
    op.execute(_virtual_collection_insert_trigger_sql())
    op.execute(_virtual_collection_trigger_sql(False))


def _drop_lock_triggers(pg: bool) -> None:
    if pg:
        for trigger in (
            "zz_roms_facets_locked_after_update",
            "zz_roms_facets_locked_after_insert",
            "zz_roms_facets_locked_after_write",
            "zz_virtual_collection_roms_locked_after_update",
            "zz_virtual_collection_roms_locked_after_insert",
            "zz_virtual_collection_roms_locked_after_write",
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON roms")
        op.execute("DROP FUNCTION IF EXISTS romm_sync_locked_facets()")
        op.execute("DROP FUNCTION IF EXISTS romm_sync_locked_virtual_collections()")
    else:
        for trigger in (
            "zz_roms_facets_locked_after_update",
            "zz_roms_facets_locked_after_insert",
            "zz_virtual_collection_roms_locked_after_update",
            "zz_virtual_collection_roms_locked_after_insert",
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {trigger}")


def upgrade() -> None:
    connection = op.get_bind()
    pg = is_postgresql(connection)

    ensure_roms_columns(connection)
    op.execute(f"DROP VIEW IF EXISTS {VIEW}")
    op.execute(
        roms_metadata_view_sql(pg, ROMS_METADATA_VIEW_COLUMNS, with_locks=True)
    )
    _install_lock_triggers(pg)


def downgrade() -> None:
    connection = op.get_bind()
    pg = is_postgresql(connection)

    _drop_lock_triggers(pg)
    op.execute(f"DROP VIEW IF EXISTS {VIEW}")
    op.execute(roms_metadata_view_sql(pg, ROMS_METADATA_VIEW_COLUMNS, with_locks=False))
    with op.batch_alter_table("roms") as batch_op:
        batch_op.drop_column("metadata_locks", if_exists=True)

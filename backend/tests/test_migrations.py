"""Guard the models against drifting away from the migrated schema.

The test database is built from the migrations, so an index declared in one but
not the other goes unnoticed until autogenerate proposes dropping it.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import alembic.config
import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import DefaultClause, FetchedValue, Table, UniqueConstraint
from sqlalchemy.sql.schema import NULL_UNSPECIFIED

import models
from handler.database.base_handler import sync_engine
from models.base import BaseModel
from models.rom import FULL_PATH_HASH_LENGTH, Rom, compute_full_path_hash
from utils.database import (
    AUTOGENERATE_EXEMPT_INDEX_NAMES,
    POSTGRESQL_FK_INDEXES,
    SORTABLE_NULLABLE_ROM_COLUMNS,
    exact_collation,
    full_path_digest_sql,
    has_column,
    is_mariadb,
    is_postgresql,
    rom_desc_index_name,
    rom_sort_index_name,
    rom_unset_flag_column,
)
from utils.roms_columns import (
    FULL_PATH_HASH_COLUMN,
    HLTB_MAIN_STORY_COLUMN,
    ROMS_METADATA_VIEW_COLUMNS,
    STEAM_FED_COLUMNS,
    STEAM_METADATA_COLUMN,
    drop_roms_columns,
    ensure_roms_columns,
    has_server_default,
    rebuild_generated_columns,
    steam_fed_columns,
)

# `compare_metadata` yields flat tuples for schema-level diffs, and a list of
# tuples for column-level ones. Only these two name an index.
INDEX_DIFF_OPS = frozenset({"add_index", "remove_index"})


def _leading_columns(table: Table) -> set[str]:
    """Names of the columns a lookup on this table can start from."""
    groups = [list(table.primary_key.columns)]
    groups += [list(index.columns) for index in table.indexes]
    groups += [
        list(constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    return {columns[0].name for columns in groups if columns}


def test_no_index_drift_between_models_and_migrations():
    """Every migrated index is declared on its model, and vice versa.

    A failure names the index: declare it in the model's `__table_args__`, or in
    `AUTOGENERATE_EXEMPT_INDEX_NAMES` if it is dialect-specific.
    """
    models.load_all_models()

    with sync_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        drift = [
            f"{diff[0]}: {diff[1].name} on {diff[1].table.name}"
            for diff in compare_metadata(context, BaseModel.metadata)
            if not isinstance(diff, list)
            and diff[0] in INDEX_DIFF_OPS
            and diff[1].name not in AUTOGENERATE_EXEMPT_INDEX_NAMES
        ]

    assert drift == []


def test_no_column_drift_between_models_and_migrations():
    """Every mapped column exists in the migrated schema with the same nullability."""
    models.load_all_models()

    with sync_engine.connect() as connection:
        inspector = sa.inspect(connection)
        # A view reflects every column as nullable, whatever the model says.
        views = set(inspector.get_view_names())
        drift = []
        for table in BaseModel.metadata.sorted_tables:
            if table.name in views:
                continue
            reflected = {
                column["name"]: column["nullable"]
                for column in inspector.get_columns(table.name)
            }
            for column in table.columns:
                if column.name not in reflected:
                    drift.append(f"missing: {table.name}.{column.name}")
                elif column.nullable != reflected[column.name]:
                    drift.append(
                        f"nullable: {table.name}.{column.name} "
                        f"model={column.nullable} db={reflected[column.name]}"
                    )

    assert drift == []


def _is_database_filled(value: object) -> bool:
    # `DefaultClause` is a literal default the ORM could write itself.
    return isinstance(value, FetchedValue) and not isinstance(value, DefaultClause)


def test_database_filled_columns_declare_their_nullability():
    """Every database-filled column passes `nullable=`, or autogenerate never compares it."""
    models.load_all_models()

    undeclared = [
        f"{table.name}.{column.name}"
        for table in BaseModel.metadata.sorted_tables
        for column in table.columns
        if any(
            _is_database_filled(value)
            for value in (column.server_default, column.server_onupdate)
        )
        # The same private flag alembic's `_nullability_might_be_unset` reads.
        and column._user_defined_nullable is NULL_UNSPECIFIED
    ]

    assert undeclared == []


def test_postgresql_fk_indexes_cover_every_unindexed_foreign_key():
    """`POSTGRESQL_FK_INDEXES` holds exactly the foreign keys that need it.

    MariaDB and MySQL index a foreign key implicitly unless its column already
    leads an index; PostgreSQL does not.
    """
    models.load_all_models()

    expected = {
        (table.name, f"ix_{table.name}_{column}", column)
        for table in BaseModel.metadata.tables.values()
        for constraint in table.foreign_key_constraints
        for column in [c.name for c in constraint.columns]
        if len(constraint.columns) == 1 and column not in _leading_columns(table)
    }

    assert expected == set(POSTGRESQL_FK_INDEXES)


@pytest.mark.parametrize(
    "fs_path,fs_name",
    [
        ("roms/nes", "Game (USA).zip"),
        ("roms/nes/Hacks & Tra'nslations", "Zelda [T-Eng].nes"),
        ("roms/nes/Ünïcøde", "Pokémon Édition Rouge.gb"),
        ("", ""),
        (None, None),
    ],
)
def test_the_migrated_full_path_digest_matches_the_models(
    fs_path: str | None, fs_name: str | None
):
    """0126 backfills `full_path_hash` in SQL; the app writes it from Python.

    A mismatch would make every pre-existing rom look new to the unique index.
    """
    with sync_engine.connect() as connection:
        digest = connection.execute(
            sa.text(
                f"SELECT {full_path_digest_sql(connection)} FROM "
                "(SELECT :fs_path AS fs_path, :fs_name AS fs_name) AS one_rom"
            ),
            {"fs_path": fs_path, "fs_name": fs_name},
        ).scalar_one()

    assert digest == compute_full_path_hash(fs_path, fs_name)


def _load_migration(filename: str) -> ModuleType:
    """Import a revision by file name, which no package path can reach."""
    path = Path(__file__).parent.parent / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    return migration


# Columns by nullability and indexes by (columns, uniqueness).
TableSchema = tuple[
    dict[str, bool], dict[str | None, tuple[tuple[str | None, ...], bool]]
]


def _schema_of(connection: sa.Connection, table: str) -> TableSchema:
    inspector = sa.inspect(connection)
    return (
        {column["name"]: column["nullable"] for column in inspector.get_columns(table)},
        {
            index["name"]: (tuple(index["column_names"]), bool(index["unique"]))
            for index in inspector.get_indexes(table)
        },
    )


def _replay(connection: sa.Connection, filename: str) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        _load_migration(filename).upgrade()


# None of these is touched by a later revision, so replaying one over the
# migrated schema has to leave that schema exactly as it found it.
@pytest.mark.parametrize(
    "filename,table",
    [
        ("0111_physical_roms.py", "roms"),
        ("0120_container_adoptions.py", "streaming_container_adoptions"),
        ("0122_rom_similarity.py", "rom_similarity"),
        ("0123_recommendation_metadata.py", "roms"),
        ("0126_unique_rom_full_path.py", "roms"),
        ("0128_hltb_main_story_column.py", "roms"),
        ("0130_notifications.py", "notifications"),
        ("0131_notification_channels.py", "notification_channels"),
        ("0132_audit_events.py", "audit_events"),
        ("0135_drop_play_session_sync_link.py", "play_sessions"),
        ("0136_deleted_assets.py", "deleted_assets"),
        ("0138_exact_save_slots.py", "saves"),
        ("0139_device_save_sync_baseline.py", "device_save_sync"),
    ],
)
def test_a_revision_replayed_over_the_migrated_schema_is_a_no_op(
    filename: str, table: str
):
    with sync_engine.begin() as connection:
        before = _schema_of(connection, table)
        _replay(connection, filename)

        assert _schema_of(connection, table) == before


def test_the_play_session_sync_link_revision_reverses_and_replays():
    """0135 drops a column whose constraint each dialect handles differently.

    MariaDB and MySQL index the foreign key themselves and refuse to drop the
    column while it stands; PostgreSQL takes both with the column and needs the
    index 0124 made. Each step is guarded, so both directions replay.
    """
    migration = _load_migration("0135_drop_play_session_sync_link.py")

    with sync_engine.begin() as connection:
        before = _schema_of(connection, "play_sessions")
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            assert has_column(connection, "play_sessions", "sync_session_id")

            migration.downgrade()
            migration.upgrade()
            migration.upgrade()

        assert not has_column(connection, "play_sessions", "sync_session_id")
        assert _schema_of(connection, "play_sessions") == before


def _slot_collations(connection: sa.Connection) -> dict[str, str | None]:
    inspector = sa.inspect(connection)
    collations = {}
    for table in ("saves", "deleted_assets"):
        [slot_type] = [
            column["type"]
            for column in inspector.get_columns(table)
            if column["name"] == "slot"
        ]
        assert isinstance(slot_type, sa.String)
        collations[table] = slot_type.collation
    return collations


def test_save_slots_are_compared_exactly():
    """Both slot columns match as sync negotiation pairs them in Python."""
    with sync_engine.connect() as connection:
        expected = exact_collation(connection)
        assert _slot_collations(connection) == {
            "saves": expected,
            "deleted_assets": expected,
        }


def test_the_exact_save_slots_revision_reverses_and_replays():
    migration = _load_migration("0138_exact_save_slots.py")

    with sync_engine.begin() as connection:
        exact = exact_collation(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            if exact is not None:
                assert _slot_collations(connection)["saves"] != exact

            migration.downgrade()
            migration.upgrade()
            migration.upgrade()

        assert _slot_collations(connection)["saves"] == exact


def test_the_exact_save_slots_revision_fixes_an_early_deleted_assets_table():
    """A deleted_assets slot left with the table's folding collation is made exact."""
    migration = _load_migration("0138_exact_save_slots.py")

    with sync_engine.begin() as connection:
        exact = exact_collation(connection)
        if exact is None:
            pytest.skip("PostgreSQL compares slots exactly already")
        with Operations.context(MigrationContext.configure(connection)) as op:
            op.alter_column(
                "deleted_assets",
                "slot",
                existing_type=sa.String(length=255),
                type_=sa.String(length=255),
                existing_nullable=False,
            )
            assert _slot_collations(connection)["deleted_assets"] != exact

            migration.upgrade()

        assert _slot_collations(connection)["deleted_assets"] == exact


def test_the_exact_save_slots_revision_rebuilds_no_table_already_exact():
    """A replay after a run that died partway skips the collations it finished."""
    migration = _load_migration("0138_exact_save_slots.py")
    statements: list[str] = []

    with sync_engine.begin() as connection:

        @sa.event.listens_for(connection, "before_cursor_execute")
        def _record(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
            if re.match(r"ALTER TABLE \S+ MODIFY", statement.lstrip(), re.I):
                statements.append(statement)

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

    assert statements == []


def test_the_rom_similarity_revision_fills_in_a_missing_index():
    """0122 meets its own table on a replay, with only some of its indexes.

    Alembic issues those as their own statements after the table, so a run can
    die between them.
    """
    migration = _load_migration("0122_rom_similarity.py")
    name, _ = migration.INDEXES[0]

    with sync_engine.begin() as connection:
        before = _schema_of(connection, migration.TABLE)
        with Operations.context(MigrationContext.configure(connection)) as operations:
            # The other one backs a foreign key, which MariaDB will not let go.
            operations.drop_index(name, table_name=migration.TABLE)
            migration.upgrade()

        assert _schema_of(connection, migration.TABLE) == before


def test_the_memory_card_revision_replays_under_the_one_that_prunes_it():
    """0119 re-creates the index 0125 drops, so the pair has to replay together.

    A real upgrade always runs 0125 after 0119; this pins that the second pass
    still lands on the same schema.
    """
    with sync_engine.begin() as connection:
        before = _schema_of(connection, "memory_card_versions")
        _replay(connection, "0119_memory_cards.py")
        _replay(connection, "0125_drop_redundant_indexes.py")

        assert _schema_of(connection, "memory_card_versions") == before


def test_the_full_path_hash_migration_resumes_an_interrupted_run(rom: Rom):
    """0126 finishes a run that died right after its ADD COLUMN.

    That run leaves the column with no digest, no NOT NULL and neither index.
    """
    migration = _load_migration("0126_unique_rom_full_path.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)) as operations:
            migration.downgrade()
            operations.add_column(
                "roms",
                sa.Column(
                    migration.COLUMN_NAME, sa.String(length=FULL_PATH_HASH_LENGTH)
                ),
            )
            migration.upgrade()

        columns, indexes = _schema_of(connection, "roms")
        digest = connection.execute(
            sa.text(
                f"SELECT {migration.COLUMN_NAME} FROM roms WHERE id = :rom_id"
            ),  # nosec B608
            {"rom_id": rom.id},
        ).scalar_one()

    assert not columns[migration.COLUMN_NAME]
    assert indexes[migration.UNIQUE_INDEX_NAME][1]
    assert not indexes[migration.LOOKUP_INDEX_NAME][1]
    assert digest == compute_full_path_hash(rom.fs_path, rom.fs_name)


def test_the_hltb_migration_resumes_an_interrupted_run():
    """0128 keeps the generated column it already added and builds its index."""
    migration = _load_migration("0128_hltb_main_story_column.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)) as operations:
            operations.drop_index(migration.INDEX_NAME, table_name="roms")
            migration.upgrade()

        _, indexes = _schema_of(connection, "roms")

    assert migration.INDEX_NAME in indexes


def test_has_column_reflects_the_migrated_schema():
    """The guard every replayed column add is skipped by."""
    with sync_engine.connect() as connection:
        assert has_column(connection, "roms", "generated_publishers")
        assert not has_column(connection, "roms", "no_such_column")


def _roms_alters(connection: sa.Connection) -> list[str]:
    """Record every ALTER TABLE roms the connection issues from here on."""
    statements: list[str] = []

    @sa.event.listens_for(connection, "before_cursor_execute")
    def _record(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        if re.match(r"ALTER TABLE roms\b", statement.lstrip(), re.IGNORECASE):
            statements.append(statement)

    return statements


def _generation_expressions(connection: sa.Connection) -> dict[str, str]:
    """The expression behind every generated column on `roms`."""
    return {
        column["name"]: column["computed"]["sqltext"]
        for column in sa.inspect(connection).get_columns("roms")
        if column.get("computed")
    }


def test_the_roms_columns_helper_leaves_a_migrated_table_alone():
    """Every revision calls it, so all but the first must cost nothing."""
    with sync_engine.begin() as connection:
        before = _schema_of(connection, "roms")
        alters = _roms_alters(connection)

        ensure_roms_columns(connection)

        assert _schema_of(connection, "roms") == before
        assert alters == []


def test_the_roms_columns_helper_adds_every_missing_column_at_once():
    """A stored and a generated column missing together cost one table copy."""
    hltb = _load_migration("0128_hltb_main_story_column.py")

    with sync_engine.begin() as connection:
        before = _schema_of(connection, "roms")
        with Operations.context(MigrationContext.configure(connection)) as operations:
            operations.drop_index(hltb.INDEX_NAME, table_name="roms")
            operations.drop_column("roms", "upc")
            operations.drop_column("roms", HLTB_MAIN_STORY_COLUMN)
        alters = _roms_alters(connection)

        ensure_roms_columns(connection)
        # 0128 owns the index, so its replay finishes the schema.
        _replay(connection, "0128_hltb_main_story_column.py")

        assert _schema_of(connection, "roms") == before
        assert len(alters) == 1


def test_the_roms_columns_helper_rebuilds_a_narrowed_sort_index():
    """PostgreSQL drops a `_sort` index with its column; MariaDB narrows it."""
    # `roms_metadata` does not project this one, so PostgreSQL lets it go
    # without the view being dropped first.
    column = HLTB_MAIN_STORY_COLUMN
    spanned = (rom_unset_flag_column(column), column, "id")

    with sync_engine.begin() as connection:
        connection.execute(sa.text(f"ALTER TABLE roms DROP COLUMN {column}"))
        assert _schema_of(connection, "roms")[1].get(rom_sort_index_name(column)) != (
            spanned,
            False,
        )

        ensure_roms_columns(connection)
        # 0128 owns the value column's own index, so its replay finishes the schema.
        _replay(connection, "0128_hltb_main_story_column.py")

        assert _schema_of(connection, "roms")[1][rom_sort_index_name(column)] == (
            spanned,
            False,
        )


def test_dropping_the_roms_columns_takes_the_sort_indexes_with_them():
    """A descending sort index reads an inherited column, so nothing else drops it."""
    # Those indexes are PostgreSQL's alone, and only its DDL rolls back, which
    # is what keeps this teardown out of the schema the other tests share.
    with sync_engine.connect() as connection:
        if not is_postgresql(connection):
            pytest.skip("descending sort indexes are PostgreSQL-only")

        transaction = connection.begin()
        try:
            descending = {
                rom_desc_index_name(column) for column in SORTABLE_NULLABLE_ROM_COLUMNS
            }
            assert descending <= set(_schema_of(connection, "roms")[1])

            drop_roms_columns(connection)

            assert descending & set(_schema_of(connection, "roms")[1]) == set()
        finally:
            transaction.rollback()


def test_the_roms_columns_helper_redefines_a_column_that_predates_steam():
    """0123 taught the metadata chains to read Steam; an older table is rebuilt."""
    with sync_engine.begin() as connection:
        pg = is_postgresql(connection)
        before = _schema_of(connection, "roms")
        genres = next(
            column
            for column in steam_fed_columns(pg, with_steam=False)
            if column.name == "generated_genres"
        )
        rebuild_generated_columns(
            connection,
            add=[genres],
            drop=[],
            view_columns=ROMS_METADATA_VIEW_COLUMNS,
        )
        assert (
            STEAM_METADATA_COLUMN
            not in _generation_expressions(connection)["generated_genres"]
        )
        alters = _roms_alters(connection)

        ensure_roms_columns(connection)

        assert _schema_of(connection, "roms") == before
        assert len(alters) == 1
        expressions = _generation_expressions(connection)
        for column in STEAM_FED_COLUMNS:
            assert STEAM_METADATA_COLUMN in expressions[column]
        assert sa.inspect(connection).has_table("roms_metadata")


def _roms_schema(
    connection: sa.Connection,
) -> tuple[TableSchema, dict[str, str], list[str]]:
    """`_schema_of` plus every generated expression and what the view projects."""
    view = sa.inspect(connection).get_columns("roms_metadata")
    return (
        _schema_of(connection, "roms"),
        _generation_expressions(connection),
        [column["name"] for column in view],
    )


def test_the_first_roms_columns_revision_downgrades_to_the_schema_it_found():
    """0108 adds every later revision's column, so alone it has to take them all back."""
    migration = _load_migration("0126_unique_rom_full_path.py")

    alembic.config.main(argv=["downgrade", "0107_roms_dedup_cover_index"])
    try:
        with sync_engine.connect() as connection:
            before = _roms_schema(connection)

        alembic.config.main(argv=["upgrade", "0108_roms_primary_region"])
        # 0126 creates this before it is stamped, so a run that died right
        # after leaves it for the downgrade to meet.
        with sync_engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)) as ops:
                ops.create_index(
                    migration.UNIQUE_INDEX_NAME,
                    "roms",
                    ["platform_id", FULL_PATH_HASH_COLUMN],
                    unique=True,
                )
        alembic.config.main(argv=["downgrade", "0107_roms_dedup_cover_index"])

        with sync_engine.connect() as connection:
            after = _roms_schema(connection)
    finally:
        alembic.config.main(argv=["upgrade", "head"])

    assert after == before


def test_the_roms_columns_helper_puts_back_a_view_a_run_lost():
    """A run that died between the ALTER and the CREATE VIEW replays to the view."""
    with sync_engine.begin() as connection:
        connection.execute(sa.text("DROP VIEW roms_metadata"))
        alters = _roms_alters(connection)

        ensure_roms_columns(connection)

        assert sa.inspect(connection).has_table("roms_metadata")
        assert alters == []


def test_the_roms_columns_helper_drops_a_digest_default_a_run_left_behind():
    """MariaDB fills the digest through a DEFAULT the run removes right after."""
    with sync_engine.begin() as connection:
        if not is_mariadb(connection):
            pytest.skip("only MariaDB gives the column a default")
        connection.execute(
            sa.text(
                f"ALTER TABLE roms ALTER COLUMN {FULL_PATH_HASH_COLUMN} SET DEFAULT ''"
            )
        )
        assert has_server_default(connection, FULL_PATH_HASH_COLUMN)
        alters = _roms_alters(connection)

        ensure_roms_columns(connection)

        assert not has_server_default(connection, FULL_PATH_HASH_COLUMN)
        assert len(alters) == 1


def test_the_roms_columns_helper_fills_the_full_path_digest_where_it_can(rom: Rom):
    """MariaDB gets the digest in the same copy; the others leave it to 0126."""
    migration = _load_migration("0126_unique_rom_full_path.py")

    with sync_engine.begin() as connection:
        before = _schema_of(connection, "roms")
        with Operations.context(MigrationContext.configure(connection)) as operations:
            operations.drop_index(migration.UNIQUE_INDEX_NAME, table_name="roms")
            operations.drop_column("roms", FULL_PATH_HASH_COLUMN)

            ensure_roms_columns(connection)

            columns, _ = _schema_of(connection, "roms")
            assert columns[FULL_PATH_HASH_COLUMN] is not is_mariadb(connection)
            assert not has_server_default(connection, FULL_PATH_HASH_COLUMN)
            if is_mariadb(connection):
                digest = connection.execute(
                    sa.text(
                        f"SELECT {FULL_PATH_HASH_COLUMN} FROM roms WHERE id = :rom_id"  # nosec B608
                    ),
                    {"rom_id": rom.id},
                ).scalar_one()
                assert digest == compute_full_path_hash(rom.fs_path, rom.fs_name)

            migration.upgrade()

        assert _schema_of(connection, "roms") == before


@pytest.mark.parametrize(
    "drop_column",
    [False, True],
    ids=["died before the index", "died before the column"],
)
def test_the_state_disc_file_migration_resumes_an_interrupted_run(drop_column: bool):
    """0121 completes whatever a run that died partway left behind.

    Nothing else in the schema references these, so the interrupted states can
    be built for real: the foreign key and index missing, or all three.
    """
    migration = _load_migration("0121_state_disc_file.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)) as operations:
            # The foreign key goes first: MariaDB refuses to drop a column it
            # still needs, and an index it still sits on.
            operations.drop_constraint(
                "fk_states_disc_file_id", "states", type_="foreignkey"
            )
            operations.drop_index("ix_states_disc_file_id", table_name="states")
            if drop_column:
                operations.drop_column("states", "disc_file_id")

            migration.upgrade()

        inspector = sa.inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("states")}
        index = inspector.has_index("states", "ix_states_disc_file_id")
        foreign_keys = {key["name"] for key in inspector.get_foreign_keys("states")}

    assert "disc_file_id" in columns
    assert index
    assert "fk_states_disc_file_id" in foreign_keys


def _is_system_sql(connection: sa.Connection) -> str:
    # Before 0137 the seeded groups are flagged by `is_system`, after it by a key.
    if has_column(connection, "permission_groups", "system_key"):
        return "system_key IS NOT NULL"
    return "is_system"


def _system_groups(connection: sa.Connection) -> dict[str, str]:
    rows = connection.execute(
        sa.text(
            "SELECT name, description FROM permission_groups "
            f"WHERE {_is_system_sql(connection)}"
        )
    )
    return {name: description for name, description in rows}


def _system_keys(connection: sa.Connection) -> dict[str, str]:
    rows = connection.execute(
        sa.text(
            "SELECT system_key, name FROM permission_groups "
            "WHERE system_key IS NOT NULL"
        )
    )
    return {key: name for key, name in rows}


GROUP_RENAME = _load_migration("0137_rename_system_groups.py")


def _upgrade_group_rename(connection: sa.Connection) -> None:
    # MariaDB commits the column DDL implicitly, so tests restore head by hand
    # rather than rolling back.
    with Operations.context(MigrationContext.configure(connection)):
        GROUP_RENAME.upgrade()
    connection.commit()


def test_the_group_rename_round_trips_the_seeded_groups():
    with sync_engine.connect() as connection:
        renamed = _system_groups(connection)
        try:
            with Operations.context(MigrationContext.configure(connection)):
                GROUP_RENAME.downgrade()
            legacy = _system_groups(connection)
        finally:
            _upgrade_group_rename(connection)
        replayed = _system_groups(connection)
        keys = _system_keys(connection)
        flag_dropped = not has_column(connection, "permission_groups", "is_system")

    assert set(renamed) == {"Viewer", "Editor"}
    assert set(legacy) == {"Viewer (legacy)", "Editor (legacy)"}
    assert "pre-upgrade" in legacy["Viewer (legacy)"]
    assert replayed == renamed
    assert keys == {"viewer": "Viewer", "editor": "Editor"}
    assert flag_dropped


def test_the_group_rename_leaves_admin_changes_alone():
    """A taken name skips that group, and an edited description survives."""
    with sync_engine.connect() as connection:
        try:
            with Operations.context(MigrationContext.configure(connection)):
                GROUP_RENAME.downgrade()
            legacy = _system_groups(connection)
            connection.execute(
                sa.text(
                    "INSERT INTO permission_groups "
                    "(name, description, is_default, is_system, created_at, updated_at) "
                    "VALUES ('Viewer', '', false, false, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                sa.text(
                    "UPDATE permission_groups SET description = 'Custom' "
                    "WHERE name = 'Editor (legacy)'"
                )
            )
            _upgrade_group_rename(connection)
            groups = _system_groups(connection)
            keys = _system_keys(connection)
        finally:
            _, _, _, _, editor_description = GROUP_RENAME.RENAMES[1]
            connection.execute(
                sa.text(
                    "DELETE FROM permission_groups "
                    f"WHERE name = 'Viewer' AND NOT ({_is_system_sql(connection)})"
                )
            )
            connection.execute(
                sa.text(
                    "UPDATE permission_groups SET description = :description "
                    f"WHERE {_is_system_sql(connection)} AND description = 'Custom'"
                ),
                {"description": editor_description},
            )
            _upgrade_group_rename(connection)

    assert groups == {
        "Viewer (legacy)": legacy["Viewer (legacy)"],
        "Editor": "Custom",
    }
    assert keys == {"viewer": "Viewer (legacy)", "editor": "Editor"}

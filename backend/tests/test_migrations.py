"""Guard the models against drifting away from the migrated schema.

The test database is built from the migrations, so an index declared in one but
not the other goes unnoticed until autogenerate proposes dropping it.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Table, UniqueConstraint

import models
from handler.database.base_handler import sync_engine
from models.base import BaseModel
from models.rom import compute_full_path_hash
from utils.database import (
    AUTOGENERATE_EXEMPT_INDEX_NAMES,
    POSTGRESQL_FK_INDEXES,
    full_path_digest_sql,
    has_column,
    is_postgresql,
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
    ],
)
def test_the_migrated_full_path_digest_matches_the_models(fs_path: str, fs_name: str):
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


@pytest.mark.parametrize(
    "table,column,expected",
    [
        ("roms", "generated_publishers", True),
        ("roms_facets", "developers", True),
        ("states", "disc_file_id", True),
        ("roms", "no_such_column", False),
    ],
)
def test_has_column_reflects_the_migrated_schema(
    table: str, column: str, expected: bool
):
    """The guard every replayed column add is skipped by."""
    with sync_engine.connect() as connection:
        assert has_column(connection, table, column) is expected


def test_the_publisher_split_column_add_replays():
    """0112's generated columns are added once, however often it runs.

    A run that dies on its trigger DDL (error 1419 on a binlog-enabled server
    without SUPER) leaves these committed, and the replay used to die on the
    duplicate column rather than resuming at the triggers.
    """
    migration = _load_migration("0112_publisher_developer_split.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration._add_generated_columns(is_postgresql(connection))

        assert has_column(connection, "roms", "generated_publishers")
        assert has_column(connection, "roms", "generated_developers")


def test_the_state_disc_file_migration_replays():
    """0121 touches only its own column, index and foreign key, so it replays whole."""
    migration = _load_migration("0121_state_disc_file.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        inspector = sa.inspect(connection)
        column = has_column(connection, "states", "disc_file_id")
        index = inspector.has_index("states", "ix_states_disc_file_id")
        foreign_keys = {key["name"] for key in inspector.get_foreign_keys("states")}

    assert column
    assert index
    assert "fk_states_disc_file_id" in foreign_keys

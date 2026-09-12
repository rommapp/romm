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
from sqlalchemy.engine.interfaces import ReflectedColumn, ReflectedIndex

import models
from handler.database.base_handler import sync_engine
from models.base import BaseModel
from models.rom import FULL_PATH_HASH_LENGTH, Rom, compute_full_path_hash
from utils.database import (
    AUTOGENERATE_EXEMPT_INDEX_NAMES,
    POSTGRESQL_FK_INDEXES,
    full_path_digest_sql,
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


def _roms_indexes(connection: sa.Connection) -> dict[str, ReflectedIndex]:
    return {
        index["name"]: index for index in sa.inspect(connection).get_indexes("roms")
    }


def _roms_column(connection: sa.Connection, name: str) -> ReflectedColumn:
    return next(
        column
        for column in sa.inspect(connection).get_columns("roms")
        if column["name"] == name
    )


# MySQL/MariaDB auto-commit each DDL statement, so the next start replays a
# revision over the leftovers of the run that died partway through it.
@pytest.mark.parametrize(
    "filename",
    ["0126_unique_rom_full_path.py", "0128_hltb_main_story_column.py"],
)
def test_a_migration_replayed_over_a_migrated_schema_is_a_no_op(filename: str):
    """Neither revision's ADD COLUMN fires again on a schema that has the column."""
    migration = _load_migration(filename)

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        columns = {
            column["name"] for column in sa.inspect(connection).get_columns("roms")
        }

    assert migration.COLUMN_NAME in columns


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

        indexes = _roms_indexes(connection)
        column = _roms_column(connection, migration.COLUMN_NAME)
        digest = connection.execute(
            sa.text("SELECT full_path_hash FROM roms WHERE id = :rom_id"),
            {"rom_id": rom.id},
        ).scalar_one()

    assert not column["nullable"]
    assert indexes[migration.UNIQUE_INDEX_NAME]["unique"]
    assert not indexes[migration.LOOKUP_INDEX_NAME]["unique"]
    assert digest == compute_full_path_hash(rom.fs_path, rom.fs_name)


def test_the_hltb_migration_resumes_an_interrupted_run():
    """0128 keeps the generated column it already added and builds its index."""
    migration = _load_migration("0128_hltb_main_story_column.py")

    with sync_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)) as operations:
            operations.drop_index(migration.INDEX_NAME, table_name="roms")
            migration.upgrade()

        indexes = _roms_indexes(connection)

    assert migration.INDEX_NAME in indexes
